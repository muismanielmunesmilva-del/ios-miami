"""Stage XNU mockfs and SHA-256 fixes for a RAM-only first process."""
import hashlib
from pathlib import Path
import subprocess

PATCHES = ('0021-sweet-mockfs-ramdisk-root.patch',
           '0022-sweet-ramdisk-root-without-iomedia.patch',
           '0023-sweet-builtin-sha256-for-libkern.patch',
           '0024-sweet-mockfs-virtual-ramdisk-io.patch',
           '0025-sweet-builtin-amfi-no-entitlements.patch')


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
    # No CoreEntitlements parser is available. Accept only signatures without
    # an entitlements object or raw XML/DER entitlements; never silently ignore
    # requested privileges. The normal CodeDirectory/page checks still run.
    provider = tree / 'bsd/kern/miami_amfi.c'
    text = provider.read_text()
    text = text.replace('#include <sys/systm.h>', '#include <sys/systm.h>\n#include <sys/ubc_internal.h>')
    old = '\t/* Leave the blob without an entitlements context: it has none. */\n\treturn KERN_SUCCESS;'
    new = '''\t/* This bring-up provider cannot parse or grant entitlements. */
\tif (os_entitlements || !code_signing_blob ||
\t    code_signing_blob->csb_entitlements ||
\t    code_signing_blob->csb_entitlements_blob ||
\t    code_signing_blob->csb_der_entitlements_blob) {
\t\treturn KERN_DENIED;
\t}
\treturn KERN_SUCCESS;'''
    if text.count(old) != 1:
        raise ValueError('AMFI no-entitlements adaptation no longer matches')
    provider.write_text(text.replace(old, new))
    return {'filesystem': 'XNU mockfs: RAM executable as /sbin/launchd, devfs mountpoint',
            'root_argument': 'rd=md0', 'physical_storage_driver_added': False,
            'sha256': 'existing XNU ccsha256_ltc_di for legacy SHA256/code-signing page hashes',
            'amfi': 'built-in deny-all queries; reject XML/DER entitlements and existing objects',
            'amfi_source_sha256': hashlib.sha256(provider.read_bytes()).hexdigest(),
            'patches': records}
