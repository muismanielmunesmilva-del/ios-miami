#!/usr/bin/env python3
"""Insert the required target preparation hook into the pinned build helper."""
import argparse
from pathlib import Path
import subprocess

PIN = '663906528d1cd5ea8fde7de6f16de73db9511549'


def configure(root):
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != PIN:
        raise ValueError('Unexpected darwin-xnu-build commit')
    path = root / 'build.sh'
    text = path.read_text()
    old = '    get_xnu\n    patches\n'
    if text.count(old) != 1:
        raise ValueError('Helper preparation hook anchor changed')
    text = text.replace(old, '    get_xnu\n    python3 --version\n    python3 "${MIAMI_PORT_ROOT}/miami/xnu/prepare.py" "${WORK_DIR}/xnu" --pthread "${WORK_DIR}/pthread" --bearssl "${WORK_DIR}/bearssl"\n    patches\n')
    old = 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"'
    if text.count(old) != 1:
        raise ValueError('libfirehose arm64 build anchor changed')
    text = text.replace(old, 'ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"')
    # Actions already selects and verifies Xcode 16.4. Its installer is not a
    # build dependency, and Homebrew no longer ships Intel xcodes bottles.
    old = ' || [ ! -x "$(command -v xcodes)" ]'
    if text.count(old) != 1:
        raise ValueError('Xcode installer dependency anchor changed')
    text = text.replace(old, '')
    old = 'install_deps() {\n'
    if text.count(old) != 1:
        raise ValueError('Dependency function anchor changed')
    text = text.replace(old, old + '    if [ ! -d "${DEVELOPER_DIR:-}" ]; then\n'
                        '        error "MIAMI requires a preinstalled, selected Xcode"\n'
                        '        exit 1\n    fi\n')
    old = 'if compgen -G "/Applications/Xcode*.app" >/dev/null; then'
    if text.count(old) != 1:
        raise ValueError('Installed Xcode detection anchor changed')
    text = text.replace(old, 'if [ -d "${DEVELOPER_DIR}" ]; then')
    old = '    build_libdispatch\n'
    if text.count(old) != 1:
        raise ValueError('Installed-header preflight anchor changed')
    text = text.replace(old, old + '    test -f "${FAKEROOT_DIR}/System/Library/Frameworks/Kernel.framework/Versions/A/PrivateHeaders/sys/pthread_shims.h"\n'
                        '    test -f "$(xcrun --sdk macosx --show-sdk-path)/usr/include/TargetConditionals.h"\n')
    path.write_bytes(text.encode('utf-8'))
    print('Pinned helper configured: required MIAMI staging and plain arm64 firehose')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('helper_tree', type=Path)
    configure(parser.parse_args().helper_tree.resolve())
