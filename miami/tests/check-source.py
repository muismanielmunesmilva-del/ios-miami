#!/usr/bin/env python3
"""Exercise staging on fresh pinned checkouts and compile the actual early
console as Darwin arm64 C with minimal declarations for external kernel APIs.
This is not a replacement for compiling XNU with its generated headers.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def check(source, helper):
    run(sys.executable, ROOT / 'xnu/configure-helper.py', helper)
    configured = (helper / 'build.sh').read_text()
    assert configured.count('python3 "${MIAMI_PORT_ROOT}/miami/xnu/prepare.py"') == 1
    assert configured.index('    get_xnu\n') < configured.index('    python3 "${MIAMI_PORT_ROOT}') < configured.index('    patches\n')
    run('bash', '-n', helper / 'build.sh')
    run(sys.executable, ROOT / 'xnu/prepare.py', source)
    board = (source / 'pexpert/pexpert/arm64/board_config.h').read_text()
    target = board.split('#ifdef ARM64_BOARD_CONFIG_MIAMI\n', 1)[1].split('#endif', 1)[0]
    assert '#define MAX_CPUS                       1\n' in target
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
    print('PASS: fresh 18-patch MIAMI staging; MAX_CPUS=1; no inherited framebuffer address; '
          'helper hook order; kernelContent sites; actual early console Darwin arm64 compile')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--helper', required=True, type=Path)
    args = parser.parse_args()
    check(args.source.resolve(), args.helper.resolve())
