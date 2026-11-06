#!/usr/bin/env python3
"""Exercise staging on fresh pinned checkouts and compile the actual early
console as Darwin arm64 C with minimal declarations for external kernel APIs.
This is not a replacement for compiling XNU with its generated headers.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xnu'))
import mkadt
import pthread_component


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def check(source, helper, pthread, bearssl):
    run(sys.executable, ROOT / 'xnu/configure-helper.py', helper)
    configured = (helper / 'build.sh').read_text()
    assert configured.count('python3 "${MIAMI_PORT_ROOT}/miami/xnu/prepare.py"') == 1
    assert configured.index('    get_xnu\n') < configured.index('    python3 "${MIAMI_PORT_ROOT}') < configured.index('    patches\n')
    run('bash', '-n', helper / 'build.sh')
    # Run the actual helper dependency function with all build tools present,
    # selected Xcode, no xcodes installer, and a brew stub that must not run.
    with tempfile.TemporaryDirectory(prefix='miami-selected-xcode-') as folder:
        temp = Path(folder)
        tools = temp / 'bin'
        tools.mkdir()
        developer = temp / 'Xcode.app/Contents/Developer'
        developer.mkdir(parents=True)
        for name in ('jq', 'gum', 'cmake', 'ninja', 'xcode-select'):
            target = tools / name
            target.write_text('#!/bin/sh\nexit 0\n')
            target.chmod(0o755)
        target = tools / 'brew'
        target.write_text('#!/bin/sh\necho "Unexpected installer attempt" >&2\nexit 42\n')
        target.chmod(0o755)
        first = configured.index('install_deps() {\n')
        last = configured.index('\n}\n', first) + len('\n}\n')
        script = temp / 'dependencies.sh'
        script.write_text('set -eu\ninfo() { :; }\nerror() { echo "$*" >&2; }\nBUILDKC=0\n' +
                          configured[first:last] + '\ninstall_deps\n')
        subprocess.run(['bash', str(script)], check=True,
                       env={**os.environ, 'PATH': str(tools) + ':/usr/bin:/bin',
                            'DEVELOPER_DIR': str(developer)})
    run(sys.executable, ROOT / 'xnu/prepare.py', source, '--pthread', pthread, '--bearssl', bearssl)
    run(sys.executable, ROOT / 'tests/check-panic.py', source)
    run(sys.executable, ROOT / 'tests/check-aes.py', source)
    run(sys.executable, ROOT / 'tests/check-sha256.py', source)
    assert 'fifo mockfs fs_compression' in (source / 'config/MASTER.arm64.miami').read_text()
    nodes = (source / 'bsd/miscfs/mockfs/mockfs_fsnode.c').read_text()
    assert '*fsnpp = kalloc_type(struct mockfs_fsnode,' in nodes
    assert 'kfree_type(struct mockfs_fsnode, fsnp);' in nodes
    assert 'memdev_info.mi_mdev && memdev_info.mi_phys' in (source / 'bsd/miscfs/mockfs/mockfs_vfsops.c').read_text()
    shims = (source / 'bsd/pthread/pthread_shims.c').read_text()
    assert 'panic("pthread kernel extension not loaded (function table is NULL).");' in shims
    assert 'MIAMI PTHREAD: kernel initialization complete' in shims
    init = (source / 'bsd/miami_pthread/kern/miami_pthread_init.c').read_text()
    assert 'pthread_kext_register((pthread_functions_t)&pthread_internal_functions, &pthread_kern);' in init
    adapter = (source / 'bsd/miami_pthread/miami_pthread_register.c').read_text()
    assert 'STARTUP(EARLY_BOOT, STARTUP_RANK_MIDDLE, miami_pthread_register)' in adapter
    assert 'pthread_start(NULL, NULL)' in adapter
    assert 'pthread_functions != &pthread_internal_functions' in adapter
    assert '-I$(FAKEROOT_DIR)/$(KPINCDIR)' in (source / 'bsd/conf/Makefile.template').read_text()
    assert '-isystem $(SDKROOT)/usr/include' in (source / 'bsd/conf/Makefile.template').read_text()
    assert '\npthread_callbacks_t pthread_kern;' not in init
    assert '\ncurrent_uthread(void)\n{' not in init
    files = (source / 'bsd/conf/files.arm64').read_text()
    assert all(name in files for name in pthread_component.SOURCES.values())
    board = (source / 'pexpert/pexpert/arm64/board_config.h').read_text()
    target = board.split('#ifdef ARM64_BOARD_CONFIG_MIAMI\n', 1)[1].split('#endif', 1)[0]
    assert '#define MAX_CPUS                       1\n' in target
    tree = mkadt.build(seed=bytes(64))
    cpus = next(n for n in tree.children if n.name == 'cpus')
    assert len(cpus.children) == 1
    cpu_compatibles = cpus.children[0].prop('compatible').split(b'\0')
    assert mkadt.BOOT_CPU_COMPAT.encode() in cpu_compatibles
    catalog = (source / 'iokit/KernelConfigTables.cpp').read_text()
    assert "'IONameMatch'     = '%s';" % mkadt.BOOT_CPU_COMPAT in catalog
    assert "'IONameMatch'     = 'qcom,kryo470';" not in catalog
    cpu_driver = (source / 'iokit/Kernel/arm/SweetCPU.cpp').read_text()
    assert '"Cortex-A55"' in cpu_driver
    assert 'topology->num_cpus != 1' in cpu_driver
    assert 'SGI1 self-test timed out' in cpu_driver
    assert not (source / 'bsd/dev/miami_ufs.c').exists()
    assert not (source / 'bsd/dev/miami_usb.c').exists()
    for name in ('osfmk/arm64/start.s', 'osfmk/arm64/arm_vm_init.c', 'osfmk/arm64/miami_early.c'):
        assert '0x9c000000' not in (source / name).read_text().lower()
    server = (source / 'iokit/Kernel/IOUserServer.cpp').read_text()
    assert server.count('rpc.kernelContent = message;') == 3
    assert '.kernelContent = message };' in server
    with tempfile.TemporaryDirectory(prefix='miami-early-c-') as folder:
        temp = Path(folder)
        (temp / 'pexpert/arm64').mkdir(parents=True)
        (temp / 'kern').mkdir()
        (temp / 'pexpert/arm64/board_config.h').write_text('#define MIAMI 1\n')
        (temp / 'kern/misc_protos.h').write_text(
            '#include <stdarg.h>\nvoid _doprnt(const char *, va_list *, void (*)(char), int);\n')
        resource = subprocess.check_output(['clang', '-print-resource-dir'], text=True).strip()
        run('clang', '-target', 'arm64-apple-macos13.5', '-ffreestanding', '-nostdinc',
            '-isystem', Path(resource) / 'include', '-I', temp, '-I', source / 'osfmk',
            '-O2', '-Wall', '-Wextra', '-Werror', '-mgeneral-regs-only', '-c',
            source / 'osfmk/arm64/miami_early.c', '-o', temp / 'early.o')
    print('PASS: fresh 18-patch MIAMI staging; MAX_CPUS=1; ADT/IOCPU matching consistent; no inherited framebuffer address; '
          'helper hook order; kernelContent sites; actual early console Darwin arm64 compile')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--helper', required=True, type=Path)
    parser.add_argument('--pthread', required=True, type=Path)
    parser.add_argument('--bearssl', required=True, type=Path)
    args = parser.parse_args()
    check(args.source.resolve(), args.helper.resolve(), args.pthread.resolve(), args.bearssl.resolve())
