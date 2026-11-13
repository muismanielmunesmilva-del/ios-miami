#!/usr/bin/env python3
"""Create a local inspection-only HFS+ image from user-supplied Apple files.

This partial image lacks the iOS shared cache and is not a complete boot root.
It must not be uploaded to CI or flashed to a device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib

import mkhfs

EXPECTED = {
    'launchd': '12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c',
    'dyld': '5806834564fe6462ae981d0915d612b1eb2f6f168822b5d278bee56254933757',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--launchd', required=True, type=Path)
    parser.add_argument('--dyld', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = plistlib.loads(args.manifest.read_bytes())
    if manifest.get('ProductVersion') != '16.7.16' or manifest.get('ProductBuildVersion') != '20H392':
        raise ValueError('Expected iOS 16.7.16 build 20H392 manifest')
    files = {'launchd': args.launchd.read_bytes(), 'dyld': args.dyld.read_bytes()}
    for name, data in files.items():
        if hashlib.sha256(data).hexdigest() != EXPECTED[name]:
            raise ValueError(f'{name} does not match the previously inspected 20H392 artifact')
    image, _ = mkhfs.build_image(files['launchd'], apple_dyld=files['dyld'])
    report = mkhfs.validate_hfs(image, allow_apple=True)
    report.update({'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                   'partial_root': True, 'shared_cache_present': False,
                   'apple_trust_verified': False, 'device_write': False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as output:
        output.write(image)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
