"""Stage XNU mockfs/HFS+ RAM-root handoff, built-in SHA-256, and XML entitlements AMFI."""
import hashlib
from pathlib import Path
import subprocess
import hfs_component

PRE_HFS_PATCHES = ('0021-sweet-mockfs-ramdisk-root.patch',
                   '0022-sweet-ramdisk-root-without-iomedia.patch',
                   '0023-sweet-builtin-sha256-for-libkern.patch',
                   '0024-sweet-mockfs-virtual-ramdisk-io.patch',
                   '0025-sweet-builtin-amfi-no-entitlements.patch')
POST_HFS_PATCHES = ('0035-sweet-amfi-entitlements-platform-binaries.patch',
                    '0036-sweet-amfi-cs-signed.patch')


def apply_patches(tree, names):
    port = Path(__file__).resolve().parents[2]
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)
    records = []
    for name in names:
        original = (port / 'xnu/patches' / name).read_bytes().replace(b'\r\n', b'\n')
        patch = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
        for flags in (['--check'], []):
            subprocess.run(['git', '-C', str(tree), 'apply', *flags,
                            '--whitespace=nowarn', '-'], input=patch, check=True)
        (patch_dir / name.replace('sweet', 'miami')).write_bytes(patch)
        records.append({'name': name, 'input_sha256': hashlib.sha256(original).hexdigest(),
                        'target_sha256': hashlib.sha256(patch).hexdigest()})
    return records


def stage(tree, hfs_source):
    records = apply_patches(tree, PRE_HFS_PATCHES)
    hfs_info = hfs_component.stage(tree, hfs_source)
    records += apply_patches(tree, POST_HFS_PATCHES)
    # Fail closed on unreadable XML entitlements or DER-only signatures:
    # if a signature includes an XML or DER entitlements blob, require a
    # parsed SweetEntitlements object on cs_blob (and valid DER slot hash
    # when a dual XML+DER blob is present). Signatures without entitlements
    # continue with csb_entitlements == NULL.
    provider = tree / 'bsd/kern/miami_amfi.c'
    text = provider.read_text()
    old_attach = '''static void
miami_amfi_attach_entitlements(struct cs_blob *code_signing_blob)
{
\tvoid *xml = NULL;
\tsize_t xml_len = 0;

\tif (csblob_get_entitlements(code_signing_blob, &xml, &xml_len) != 0) {
\t\tprintf("MIAMI AMFI: %s: entitlements do not match the code directory, granting none\\n",
\t\t    csblob_get_identity(code_signing_blob));
\t\treturn;
\t}
\tif (xml == NULL) {
\t\treturn;                 /* no XML entitlements */
\t}
\tvoid *ent = miami_entitlements_create(xml, xml_len);
\tif (ent == NULL) {
\t\tprintf("MIAMI AMFI: %s: unreadable entitlements (%zu bytes), granting none\\n",
\t\t    csblob_get_identity(code_signing_blob), xml_len);
\t\treturn;
\t}
\tif (miami_amfi_debug) {
\t\t/* The test keys only exist in tools/mkinit.py test signatures. */
\t\tprintf("MIAMI AMFI: %s: %u entitlements (test: bool %d string %d array %d)\\n",
\t\t    csblob_get_identity(code_signing_blob), miami_entitlements_count(ent),
\t\t    miami_entitlements_bool(ent, "com.apple.private.miami.test-bool"),
\t\t    miami_entitlements_string(ent, "com.apple.private.miami.test-string", "hello"),
\t\t    miami_entitlements_string(ent, "com.apple.private.miami.test-array", "two"));
\t}
\tcsblob_os_entitlements_set(code_signing_blob, ent);    /* takes a reference */
\tosobject_release(ent);
}

static kern_return_t
miami_amfi_adjust_without_monitor(__unused void *os_entitlements,
    __unused struct cs_blob *code_signing_blob)
{
\t/* Entitlements were attached in miami_amfi_vnode_check_signature. */
\treturn KERN_SUCCESS;
}'''
    new_attach = '''static int
miami_amfi_attach_entitlements(struct cs_blob *code_signing_blob)
{
\tvoid *xml = NULL;
\tsize_t xml_len = 0;
\tconst CS_GenericBlob *der = NULL;
\tsize_t der_len = 0;

\tif (csblob_get_entitlements(code_signing_blob, &xml, &xml_len) != 0 ||
\t    csblob_get_der_entitlements(code_signing_blob, &der, &der_len) != 0) {
\t\tprintf("MIAMI AMFI: %s: entitlements do not match the code directory\\n",
\t\t    csblob_get_identity(code_signing_blob));
\t\treturn EBADEXEC;
\t}
\tif (der != NULL && xml == NULL) {
\t\tprintf("MIAMI AMFI: %s: DER-only entitlements are not supported\\n",
\t\t    csblob_get_identity(code_signing_blob));
\t\treturn EPERM;
\t}
\tif (xml == NULL) {
\t\treturn 0;               /* no entitlements */
\t}
\tvoid *ent = miami_entitlements_create(xml, xml_len);
\tif (ent == NULL) {
\t\tprintf("MIAMI AMFI: %s: unreadable XML entitlements (%zu bytes)\\n",
\t\t    csblob_get_identity(code_signing_blob), xml_len);
\t\treturn EBADEXEC;
\t}
\tif (miami_amfi_debug) {
\t\t/* The test keys only exist in tools/mkinit.py test signatures. */
\t\tprintf("MIAMI AMFI: %s: %u entitlements (test: bool %d string %d array %d)\\n",
\t\t    csblob_get_identity(code_signing_blob), miami_entitlements_count(ent),
\t\t    miami_entitlements_bool(ent, "com.apple.private.miami.test-bool"),
\t\t    miami_entitlements_string(ent, "com.apple.private.miami.test-string", "hello"),
\t\t    miami_entitlements_string(ent, "com.apple.private.miami.test-array", "two"));
\t}
\tcsblob_os_entitlements_set(code_signing_blob, ent);    /* takes a reference */
\tosobject_release(ent);
\treturn 0;
}

static kern_return_t
miami_amfi_adjust_without_monitor(void *os_entitlements,
    struct cs_blob *code_signing_blob)
{
\tif (code_signing_blob == NULL || os_entitlements != code_signing_blob->csb_entitlements) {
\t\treturn KERN_DENIED;
\t}
\tif ((code_signing_blob->csb_entitlements_blob != NULL ||
\t    code_signing_blob->csb_der_entitlements_blob != NULL) &&
\t    os_entitlements == NULL) {
\t\treturn KERN_DENIED;
\t}
\treturn KERN_SUCCESS;
}'''
    if text.count(old_attach) != 1:
        raise ValueError('AMFI attach/adjust anchor changed')
    text = text.replace(old_attach, new_attach)
    old_hook = '''\tif (cs_blob != cs_blob->csb_ro_addr && cs_blob->csb_entitlements == NULL) {
\t\tmiami_amfi_attach_entitlements(cs_blob);
\t}
\treturn 0;'''
    new_hook = '''\tif (cs_blob != cs_blob->csb_ro_addr && cs_blob->csb_entitlements == NULL) {
\t\treturn miami_amfi_attach_entitlements(cs_blob);
\t}
\treturn 0;'''
    if text.count(old_hook) != 1:
        raise ValueError('AMFI vnode_check_signature hook anchor changed')
    text = text.replace(old_hook, new_hook)
    provider.write_bytes(text.encode('utf-8'))
    entitlements_cpp = tree / 'iokit/Kernel/arm/SweetEntitlements.cpp'
    return {'filesystem': 'XNU mockfs (Mach-O RAMDisk) and built-in Apple OSS HFS+ (hfs-627.100.6)',
            'root_argument': 'rd=md0', 'physical_storage_driver_added': False,
            'sha256': 'existing XNU ccsha256_ltc_di for legacy SHA256/code-signing page hashes',
            'amfi': 'built-in XML entitlements (SweetEntitlements OSDictionary) + CS_PLATFORM_BINARY on rootfs + CS_SIGNED; fail-closed on malformed XML or DER-only blobs',
            'amfi_source_sha256': hashlib.sha256(provider.read_bytes()).hexdigest(),
            'entitlements_source_sha256': hashlib.sha256(entitlements_cpp.read_bytes()).hexdigest(),
            'hfs': hfs_info,
            'patches': records}
