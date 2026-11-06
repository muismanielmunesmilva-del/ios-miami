#!/usr/bin/env python3
"""Stage the single-CPU MIAMI kernel on the pinned Apple XNU source.

Runs before the build helper's patches() prelude and header export.
Required port patches and every target edit are fail-fast. No phone access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import mkadt
import pthread_component
import panic_screen

APPLE_COMMIT = '1b191cb58250d0705d8a51287127505aa4bc0789'
PORT = Path(__file__).resolve().parents[2]
CACHE = {}


def git(tree, *args, data=None):
    result = subprocess.run(['git', '-C', str(tree), *args], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'git {args}: {result.stderr.decode()}')
    return result.stdout


def edit(tree, path, before, after, count=1):
    target = tree / path
    text = CACHE.get(target, target.read_text())
    if text.count(before) != count:
        raise ValueError(f'{path}: expected {count} occurrences of {before[:90]!r}')
    CACHE[target] = text.replace(before, after)


def section(tree, path, begin, end, replacement):
    target = tree / path
    text = CACHE.get(target, target.read_text())
    if text.count(begin) != 1:
        raise ValueError(f'{path}: ambiguous section {begin!r}')
    first = text.index(begin)
    last = text.index(end, first) + len(end)
    edit(tree, path, text[first:last], replacement)


def prepare(tree, pthread_source):
    tree = tree.resolve()
    manifest = tree.parent / 'miami-source.json'
    if manifest.exists():
        raise ValueError('Use a fresh Apple checkout; MIAMI staging already recorded')
    if git(tree, 'rev-parse', 'HEAD').decode().strip() != APPLE_COMMIT:
        raise ValueError('Unexpected Apple XNU commit')
    applied = []
    patches = sorted((PORT / 'xnu/patches').glob('*.patch'))
    patches = [p for p in patches if p.name[:4].isdigit() and int(p.name[:4]) <= 18]
    if len(patches) != 18:
        raise ValueError('Expected the 18 initial ios-sweet patches')
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)
    base_manifest = tree.parent / 'miami-base-patches.json'
    for patch in ([] if base_manifest.exists() else patches):
        original = patch.read_bytes().replace(b'\r\n', b'\n')
        target = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
        target = target.replace(b'Redmi Note 10 Pro', b'Motorola Edge 30 Neo')
        target = target.replace(b'xiaomi,miami', b'motorola,miami')
        target = target.replace(b'SM7150', b'SM6375').replace(b'Snapdragon 732G', b'Snapdragon 695')
        git(tree, 'apply', '--check', '--whitespace=nowarn', '-', data=target)
        git(tree, 'apply', '--whitespace=nowarn', '-', data=target)
        (patch_dir / patch.name.replace('sweet', 'miami')).write_bytes(target)
        applied.append({'name': patch.name, 'input_sha256': hashlib.sha256(original).hexdigest(),
                        'target_sha256': hashlib.sha256(target).hexdigest()})
    if base_manifest.exists():
        applied = json.loads(base_manifest.read_text())
    else:
        base_manifest.write_text(json.dumps(applied, indent=2) + '\n')

    edit(tree, 'pexpert/pexpert/arm64/board_config.h',
         '#include <pexpert/arm64/MIAMI.h>\n\n#define MAX_L2_CLINE                   6\n#define MAX_CPUS                       8',
         '#include <pexpert/arm64/MIAMI.h>\n\n#define MAX_L2_CLINE                   6\n#define MAX_CPUS                       1')
    edit(tree, 'pexpert/pexpert/arm64/MIAMI.h',
         'Kryo 470 = Cortex-A76 + Cortex-A55, ARMv8.2, no PAC.',
         'Boot CPU: Cortex-A55 r2p0, ARMv8.2, no PAC; secondary CPUs disabled.')
    # The legacy IOCPU driver must match the CPU nub emitted by our own ADT,
    # rather than the inherited Redmi compatible. Keep its topology/SGI checks.
    edit(tree, 'iokit/KernelConfigTables.cpp',
         "'IONameMatch'     = 'qcom,kryo470';",
         "'IONameMatch'     = '%s';" % mkadt.BOOT_CPU_COMPAT)
    edit(tree, 'iokit/Kernel/arm/SweetCPU.cpp', '"Kryo 470"', '"Cortex-A55"')
    # Xcode 16 iig's additional kernel-only field matches Apple's later IORPC
    # header. Keep old Mach-message validation and populate the field before
    # reaching generated Dispatch methods; all kernel objects rebuild together.
    for path in ('iokit/IOKit/IORPC.h', 'iokit/DriverKit/IORPC.h'):
        edit(tree, path, '\tuint32_t           replySize;\n};',
             '\tuint32_t           replySize;\n#ifdef KERNEL\n'
             '\tIORPCMessage     * kernelContent;\n#endif\n};')
    server = 'iokit/Kernel/IOUserServer.cpp'
    edit(tree, server, '\tmessage = IORPCMessageFromMach(rpc.message, false);',
         '\tmessage = IORPCMessageFromMach(rpc.message, false);\n\trpc.kernelContent = message;', 2)
    edit(tree, server,
         '.sendSize = msgin->msgh.msgh_size, .replySize = replyAlloc };',
         '.sendSize = msgin->msgh.msgh_size, .replySize = replyAlloc, .kernelContent = message };')
    edit(tree, server,
         '\trpc.replySize = ((uint32_t) (sizeof(buffer.buffer) - inSize));    // inSize was checked',
         '\trpc.replySize = ((uint32_t) (sizeof(buffer.buffer) - inSize));    // inSize was checked\n'
         '\trpc.kernelContent = message;')

    # No unvalidated fixed framebuffer write before boot_args are available.
    start = 'osfmk/arm64/start.s'
    edit(tree, start, '.macro MSR_VBAR_EL1_X0',
         (Path(__file__).parent / 'boot-marks.S.inc').read_text() + '\n.macro MSR_VBAR_EL1_X0')
    genassym = 'osfmk/arm64/genassym.c'
    edit(tree, genassym, '\tDECLARE("BA_VIRT_BASE", offsetof(struct boot_args, virtBase));',
         '\tDECLARE("BA_VIRT_BASE", offsetof(struct boot_args, virtBase));\n'
         '\tDECLARE("BA_VIDEO_BASE", offsetof(struct boot_args, Video.v_baseAddr));\n'
         '\tDECLARE("BA_VIDEO_ROW_BYTES", offsetof(struct boot_args, Video.v_rowBytes));')
    edit(tree, start, 'LEXT(start_first_cpu)\n',
         'LEXT(start_first_cpu)\n#if defined(MIAMI)\n\tmiami_boot_mark x0, 1\n#endif\n')
    edit(tree, start, '\tMSR_VBAR_EL1_X0\n\n\n\t// Get the kernel memory parameters',
         '\tMSR_VBAR_EL1_X0\n#if defined(MIAMI)\n\tmiami_boot_mark x20, 2\n#endif\n\n\t// Get the kernel memory parameters')
    edit(tree, start, '\t// Set up exception stack pointer\n',
         '#if defined(MIAMI)\n\tmiami_boot_mark x20, 3\n#endif\n\t// Set up exception stack pointer\n')
    edit(tree, start, '\t/* Ensure TTEs are visible */',
         '#if defined(MIAMI)\n\tmiami_boot_mark x20, 4\n#endif\n\t/* Ensure TTEs are visible */')
    edit(tree, start, '\t// Enable caches, MMU, ROP and JOP\n',
         '#if defined(MIAMI)\n\tmiami_boot_mark x20, 5\n#endif\n\t// Enable caches, MMU, ROP and JOP\n')
    edit(tree, start, '\tMSR_SCTLR_EL1_X0\n\tisb\t\tsy\n',
         '\tMSR_SCTLR_EL1_X0\n\tisb\t\tsy\n#if defined(MIAMI)\n\tmiami_boot_mark x20, 6\n#endif\n')
    edit(tree, start, '\t// Return to arm_init()\n\tret',
         '#if defined(MIAMI)\n\tmiami_boot_mark x0, 7\n#endif\n\t// Return to arm_init()\n\tret')
    section(tree, start, '#if defined(MIAMI)\n\t/* Stage 0:', '#endif\n', '')
    section(tree, start, '#if defined(MIAMI)\n\t/*\n\t * Splash framebuffer:', '#endif\n',
            (Path(__file__).parent / 'bootstrap-splash.S.inc').read_text())
    # Reserve two pages and round the runtime pointer up to 16K. Mach-O's
    # common-symbol placement did not retain the requested 16K alignment in
    # the actual Xcode build; an aligned C declaration alone is insufficient.
    vm = 'osfmk/arm64/arm_vm_init.c'
    edit(tree, vm,
         'SECURITY_READ_ONLY_LATE(uint8_t) bootstrap_pagetables[BOOTSTRAP_TABLE_SIZE] __attribute__((aligned(ARM_PGBYTES)));',
         'SECURITY_READ_ONLY_LATE(uint8_t) bootstrap_pagetables[BOOTSTRAP_TABLE_SIZE] __attribute__((aligned(ARM_PGBYTES)));\n'
         'uint64_t miami_boot_splash_storage[4096] __attribute__((aligned(4096)));')
    section(tree, vm, 'static void\nmiami_early_map_final(void)', '\n}\n',
            (Path(__file__).parent / 'final-splash.c.inc').read_text())
    edit(tree, vm, 'miami_early_relocate(MIAMI_EARLY_FB_VA);',
         'miami_early_relocate(MIAMI_EARLY_FB_VA + args->Video.v_baseAddr - 0x84000000ULL);')
    early = 'osfmk/arm64/miami_early.c'
    edit(tree, early,
         'static volatile uint32_t *early_fb = (volatile uint32_t *)(uintptr_t)0x9c000000;',
         'static volatile uint32_t *early_fb;\nstatic uint32_t early_stride;')
    edit(tree, early, '#define EARLY_STRIDE (4320u / 4)', '#define EARLY_STRIDE early_stride')
    edit(tree, early, 'if (early_disabled)', 'if (!early_fb || early_disabled)')
    edit(tree, early, 'if (early_disabled || stage > 20)', 'if (!early_fb || early_disabled || stage > 20)')
    edit(tree, early, 'if (early_disabled || early_panicking)', 'if (!early_fb || early_disabled || early_panicking)')
    configure = '''
void
miami_early_configure(uint64_t base, uint64_t row_bytes)
{
    if (base < 0x85200000ULL || (base & 3) || row_bytes < 4320 ||
        row_bytes > 8192 || (row_bytes & 3) ||
        base + row_bytes * 2400 > 0x85e00000ULL) {
        early_disabled = 1;
        return;
    }
    early_fb = (volatile uint32_t *)(uintptr_t)base;
    early_stride = (uint32_t)(row_bytes / 4);
}
'''
    edit(tree, early, 'static void\nmiami_early_clear_row(void)', configure + '\nstatic void\nmiami_early_clear_row(void)')
    edit(tree, 'osfmk/arm64/miami_early.h', 'void miami_early_mark(unsigned int stage, const char *label);',
         'void miami_early_configure(uint64_t base, uint64_t row_bytes);\nvoid miami_early_mark(unsigned int stage, const char *label);')
    edit(tree, 'osfmk/arm/arm_init.c', '\tmiami_early_mark(1,',
         '\tmiami_early_configure(args->Video.v_baseAddr, args->Video.v_rowBytes);\n\tmiami_early_mark(1,')
    # The initial loader requires the already-tested SDE autorefresh mode.
    # Both early and serial consoles write Normal-NC splash pages; no XNU
    # clock/DSI/MDP pokes or drivers copied from a different phone.
    for path in (start, vm, early, 'pexpert/arm/pe_serial.c'):
        target = tree / path
        if '0x9c000000' in CACHE.get(target, target.read_text()).lower():
            raise ValueError(f'{path}: SWEET framebuffer address remains')
    panic_screen.stage(tree, edit)
    result = {'apple_commit': APPLE_COMMIT, 'machine': 'MIAMI', 'max_cpus': 1,
              'required_patches': applied, 'splash': ['0x85200000', '0x85e00000'],
              'storage_drivers_staged': False, 'iig_abi': 'kernelContent backport; compile verification pending',
              'panic_screen': 'first panic saved state or generic reason; 18 protected rows'}
    for target, text in CACHE.items():
        target.write_bytes(text.encode('utf-8'))
    result['pthread'] = pthread_component.stage(tree, pthread_source)
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    print(f'MIAMI: {len(applied)} required patches and target edits staged; MAX_CPUS=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apple_tree', type=Path)
    parser.add_argument('--pthread', required=True, type=Path)
    args = parser.parse_args()
    prepare(args.apple_tree, args.pthread.resolve())
