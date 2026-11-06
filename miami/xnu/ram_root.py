"""Stage XNU mockfs and SHA-256 fixes for a RAM-only first process."""
import hashlib
from pathlib import Path
import subprocess

PATCHES = ('0021-sweet-mockfs-ramdisk-root.patch',
           '0022-sweet-ramdisk-root-without-iomedia.patch',
           '0023-sweet-builtin-sha256-for-libkern.patch',
           '0024-sweet-mockfs-virtual-ramdisk-io.patch')


def stage(tree):
    port = Path(__file__).resolve().parents[2]
    records = []
    for name in PATCHES:
        original = (port / 'xnu/patches' / name).read_bytes().replace(b'\r\n', b'\n')
        patch = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
        for flags in (['--check'], []):
            subprocess.run(['git', '-C', str(tree), 'apply', *flags,
                            '--whitespace=nowarn', '-'], input=patch, check=True)
        records.append({'name': name, 'input_sha256': hashlib.sha256(original).hexdigest(),
                        'target_sha256': hashlib.sha256(patch).hexdigest()})
    return {'filesystem': 'XNU mockfs: RAM executable as /sbin/launchd, devfs mountpoint',
            'root_argument': 'rd=md0', 'physical_storage_driver_added': False,
            'sha256': 'existing XNU ccsha256_ltc_di for legacy SHA256/code-signing page hashes',
            'patches': records}
