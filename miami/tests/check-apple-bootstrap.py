"""Test the explicit Apple-compatible HFS mode using generated test files."""
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'userspace'))
import build
import mkhfs

import tempfile
with tempfile.TemporaryDirectory(prefix='miami-apple-root-') as tmp:
    init_path = Path(tmp) / 'init.macho'
    existing = os.environ.get('MIAMI_TEST_INIT')
    if existing:
        init_bytes = Path(existing).read_bytes()
    else:
        build.build(init_path)
        init_bytes = init_path.read_bytes()
    launchd = mkhfs.add_dylinker_command(init_bytes)
    dyld = mkhfs.build_dyld()
    image, _ = mkhfs.build_image(launchd, apple_dyld=dyld)
    report = mkhfs.validate_hfs(image, allow_apple=True)
    assert report['launchd']['sha256'] == mkhfs.inspect_apple_binary(launchd, 2)['sha256']
    assert report['dyld']['sha256'] == mkhfs.inspect_apple_binary(dyld, 7)['sha256']
    broken = bytearray(image)
    broken[5 * mkhfs.BLOCK_SIZE + 1024] ^= 1
    try:
        mkhfs.validate_hfs(broken, allow_apple=True)
    except ValueError:
        pass
    else:
        raise AssertionError('Corrupted executable accepted')
print('PASS: Apple-compatible root validates original binary pages and rejects corruption')
