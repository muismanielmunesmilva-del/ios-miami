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
    text = text.replace(old, '    get_xnu\n    python3 --version\n    python3 "${MIAMI_PORT_ROOT}/miami/xnu/prepare.py" "${WORK_DIR}/xnu"\n    patches\n')
    old = 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"'
    if text.count(old) != 1:
        raise ValueError('libfirehose arm64 build anchor changed')
    text = text.replace(old, 'ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"')
    path.write_bytes(text.encode('utf-8'))
    print('Pinned helper configured: required MIAMI staging and plain arm64 firehose')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('helper_tree', type=Path)
    configure(parser.parse_args().helper_tree.resolve())

