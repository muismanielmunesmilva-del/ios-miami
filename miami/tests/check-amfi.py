"""Execute the actual staged XML-entitlements AMFI and platform-binary policy on the host.

The full kernel build verifies its real Apple ABI and libkern C++ classes; this
harness exercises the staged miami_amfi.c functions directly and verifies that
root-filesystem binaries get CS_SIGNED | CS_PLATFORM_BINARY, valid XML
entitlements are attached and queried, and unreadable XML, hash mismatches, or
DER-only entitlements fail closed.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

tree = Path(sys.argv[1]).resolve()
source = (tree / 'bsd/kern/miami_amfi.c').read_text()
ent_cpp = (tree / 'iokit/Kernel/arm/SweetEntitlements.cpp').read_text()
bsd_init = (tree / 'bsd/kern/bsd_init.c').read_text()

assert 'amfi_interface_register(&miami_amfi);' in source
assert 'STARTUP(EARLY_BOOT, STARTUP_RANK_MIDDLE, miami_amfi_register)' in source
assert 'miami_amfi_policy_register(void)' in source
assert 'miami_amfi_policy_register();' in bsd_init
assert 'miami_sandbox_syscall(' in source
assert 'miami_sandbox_priv_grant(' in source
assert 'mac_policy_register(&miami_sandbox_mac_conf' in source
assert 'class SweetEntitlements : public OSObject' in ent_cpp
assert 'OSUnserializeXML(text, text_len + 1)' in ent_cpp
assert 'miami_entitlements_copy_xml' in ent_cpp

start = source.index('/* The entitlements object of a process\'s main binary, or NULL. */')
end = source.index('static const struct mac_policy_ops miami_amfi_mac_ops')
body = source[start:end]
sb_start = source.index('#define MIAMI_PRIV_LOG_MAX')
sb_end = source.index('static const struct mac_policy_ops miami_sandbox_mac_ops')
sb_body = source[sb_start:sb_end]

harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define __unused __attribute__((unused))
#define __startup_func
#define STARTUP(a, b, c)
typedef int kern_return_t;
typedef int cpu_type_t;
typedef uintptr_t user_addr_t;
typedef void *kauth_cred_t;
typedef uint32_t CEError_t;
typedef void *CEQuery_t;
typedef void *CEQueryContext_t;
enum { KERN_SUCCESS = 0, KERN_NOT_FOUND = 4, KERN_NOT_SUPPORTED = 46, KERN_DENIED = 53 };
enum { EPERM = 1, ENOENT = 2, EBADEXEC = 85 };
#define PRIV_WORK_INTERVAL 14011
#define CS_CDHASH_LEN 20
#define CS_PLATFORM_BINARY 0x04000000U
#define CS_SIGNED 0x20000000U
#define MNT_ROOTFS 0x00004000U
#define OSENTITLEMENTS_INTERFACE_VERSION 1U

typedef struct { uint32_t magic; uint32_t length; char data[]; } CS_GenericBlob;
struct vnode { uint32_t mnt_flags; };
typedef struct vnode *mount_t;
struct label;
struct cs_blob {
    void *csb_ro_addr;
    void *csb_entitlements;
    const CS_GenericBlob *csb_entitlements_blob;
    const CS_GenericBlob *csb_der_entitlements_blob;
    int xml_err;
    int der_err;
};
struct proc { struct cs_blob *blob; };
typedef struct proc *proc_t;

typedef struct {
    void (*OSEntitlements_invalidate)(void *);
    void *(*OSEntitlements_asdict)(void *);
    CEError_t (*OSEntitlements_query)(void *, uint8_t[CS_CDHASH_LEN], CEQuery_t, size_t);
    bool (*OSEntitlements_get_transmuted)(void *, const CS_GenericBlob **);
    bool (*OSEntitlements_get_xml)(void *, CS_GenericBlob **);
    bool (*get_legacy_profile_exemptions)(const uint8_t **, size_t *);
    bool (*get_udid)(const uint8_t **, size_t *);
    void *(*query_context_to_object)(CEQueryContext_t);
    struct {
        uint32_t version;
        kern_return_t (*adjustContextWithMonitor)(void *, CEQueryContext_t, const void *, const char *, uint32_t);
        kern_return_t (*adjustContextWithoutMonitor)(void *, struct cs_blob *);
        kern_return_t (*queryEntitlementBoolean)(const void *, const char *);
        kern_return_t (*queryEntitlementBooleanWithProc)(const proc_t, const char *);
        kern_return_t (*queryEntitlementString)(const void *, const char *, const char *);
        kern_return_t (*queryEntitlementStringWithProc)(const proc_t, const char *, const char *);
        kern_return_t (*copyEntitlementAsOSObject)(const void *, const char *, void **);
        kern_return_t (*copyEntitlementAsOSObjectWithProc)(const proc_t, const char *, void **);
    } OSEntitlements;
} amfi_t;

static uint32_t miami_amfi_debug = 0;
static const amfi_t *registered_amfi = NULL;
static void amfi_interface_register(const amfi_t *a) { registered_amfi = a; }
static void panic(const char *msg) __attribute__((noreturn));
static void panic(const char *msg) { (void)msg; abort(); }
static struct cs_blob *csproc_get_blob(proc_t p) { return p ? p->blob : NULL; }
static void *csblob_os_entitlements_get(struct cs_blob *b) { return b ? b->csb_entitlements : NULL; }
static void csblob_os_entitlements_set(struct cs_blob *b, void *e) { b->csb_entitlements = e; }
static const char *csblob_get_identity(struct cs_blob *b) { (void)b; return "org.miami.init"; }
static mount_t vnode_mount(struct vnode *vp) { return vp; }
static uint32_t vfs_flags(mount_t mp) { return mp->mnt_flags; }
static int proc_pid(struct proc *p) { (void)p; return 1; }
static void proc_name(int pid, char *buf, int size) { (void)pid; snprintf(buf, (size_t)size, "launchd"); }
static void proc_selfname(char *buf, int size) { snprintf(buf, (size_t)size, "launchd"); }
static size_t strlcpy_compat(char *dst, const char *src, size_t sz) {
    size_t n = strlen(src);
    if (sz) { size_t c = n >= sz ? sz - 1 : n; memcpy(dst, src, c); dst[c] = '\0'; }
    return n;
}
#undef strlcpy
#define strlcpy strlcpy_compat

struct fake_ent { int valid; CS_GenericBlob *xml; int ref; };
static struct fake_ent global_ent;

static int csblob_get_entitlements(struct cs_blob *b, void **out, size_t *len) {
    if (b->xml_err) return b->xml_err;
    *out = (void *)b->csb_entitlements_blob;
    *len = b->csb_entitlements_blob ? 64 : 0;
    return 0;
}
static int csblob_get_der_entitlements(struct cs_blob *b, const CS_GenericBlob **out, size_t *len) {
    if (b->der_err) return b->der_err;
    *out = b->csb_der_entitlements_blob;
    *len = b->csb_der_entitlements_blob ? 32 : 0;
    return 0;
}
void *miami_entitlements_create(const CS_GenericBlob *blob, size_t blob_len) {
    if (!blob || blob_len != 64 || blob->magic != 0x7171defaU) return NULL;
    global_ent.valid = 1;
    global_ent.xml = (CS_GenericBlob *)(uintptr_t)blob;
    global_ent.ref = 1;
    return &global_ent;
}
void *miami_entitlements_copy_dict(const void *ent) { return (void *)(uintptr_t)ent; }
bool miami_entitlements_copy_xml(const void *ent, CS_GenericBlob **out) {
    const struct fake_ent *e = ent;
    if (!e || !e->valid) return false;
    *out = e->xml;
    return true;
}
bool miami_entitlements_bool(const void *ent, const char *name) {
    const struct fake_ent *e = ent;
    return e && e->valid && strcmp(name, "com.motorola.miami.pid1") == 0;
}
bool miami_entitlements_string(const void *ent, const char *name, const char *val) {
    const struct fake_ent *e = ent;
    return e && e->valid && strcmp(name, "role") == 0 && strcmp(val, "init") == 0;
}
void *miami_entitlements_copy_object(const void *ent, const char *name) {
    return miami_entitlements_bool(ent, name) ? (void *)0x1234 : NULL;
}
unsigned int miami_entitlements_count(const void *ent) { return ent ? 2 : 0; }
void osobject_release(void *object) { (void)object; }
''' + body + sb_body + r'''
int main(void) {
    miami_amfi_register();
    assert(registered_amfi == &miami_amfi);

    /* 1. Rootfs binary with no entitlements: CS_SIGNED | CS_PLATFORM_BINARY, adjust succeeds. */
    struct vnode root_vp = { .mnt_flags = MNT_ROOTFS };
    struct vnode nonroot_vp = { .mnt_flags = 0 };
    struct cs_blob ro_marker = {0};
    struct cs_blob b = { .csb_ro_addr = &ro_marker };
    unsigned int flags = 0;
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b, &flags, NULL, 0, 0, NULL, NULL) == 0);
    assert(flags == (CS_SIGNED | CS_PLATFORM_BINARY));
    assert(b.csb_entitlements == NULL);
    assert(miami_amfi_adjust_without_monitor(b.csb_entitlements, &b) == KERN_SUCCESS);

    /* 2. Non-root binary gets CS_SIGNED but not CS_PLATFORM_BINARY. */
    flags = 0;
    assert(miami_amfi_vnode_check_signature(&nonroot_vp, NULL, 0, &b, &flags, NULL, 0, 0, NULL, NULL) == 0);
    assert(flags == CS_SIGNED);

    /* 3. Valid XML entitlements are parsed, attached, and queryable via proc & blob. */
    CS_GenericBlob valid_xml = { .magic = 0x7171defaU, .length = 64 };
    struct cs_blob b_xml = { .csb_ro_addr = &ro_marker, .csb_entitlements_blob = &valid_xml };
    flags = 0;
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b_xml, &flags, NULL, 0, 0, NULL, NULL) == 0);
    assert(b_xml.csb_entitlements == &global_ent);
    assert(miami_amfi_adjust_without_monitor(b_xml.csb_entitlements, &b_xml) == KERN_SUCCESS);
    struct proc p = { .blob = &b_xml };
    assert(miami_amfi_query_boolean_with_proc(&p, "com.motorola.miami.pid1") == KERN_SUCCESS);
    assert(miami_amfi_query_boolean_with_proc(&p, "unknown") == KERN_DENIED);
    assert(miami_amfi_query_string_with_proc(&p, "role", "init") == KERN_SUCCESS);
    assert(miami_amfi_query_string_with_proc(&p, "role", "other") == KERN_DENIED);
    CS_GenericBlob *copied_xml = NULL;
    assert(miami_amfi_entitlements_get_xml(b_xml.csb_entitlements, &copied_xml) && copied_xml == &valid_xml);

    /* 4. Dual XML + valid DER entitlements (like stock iOS launchd) succeed. */
    CS_GenericBlob valid_der = { .magic = 0x7172defaU, .length = 32 };
    struct cs_blob b_dual = { .csb_ro_addr = &ro_marker, .csb_entitlements_blob = &valid_xml, .csb_der_entitlements_blob = &valid_der };
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b_dual, &flags, NULL, 0, 0, NULL, NULL) == 0);
    assert(miami_amfi_adjust_without_monitor(b_dual.csb_entitlements, &b_dual) == KERN_SUCCESS);

    /* 5. DER-only entitlements fail closed in both vnode_check_signature and adjust_without_monitor. */
    struct cs_blob b_der_only = { .csb_ro_addr = &ro_marker, .csb_der_entitlements_blob = &valid_der };
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b_der_only, &flags, NULL, 0, 0, NULL, NULL) == EPERM);
    assert(miami_amfi_adjust_without_monitor(b_der_only.csb_entitlements, &b_der_only) == KERN_DENIED);

    /* 6. Unreadable XML entitlements or hash mismatch fail closed. */
    CS_GenericBlob bad_xml = { .magic = 0xdeadbeefU, .length = 64 };
    struct cs_blob b_bad_xml = { .csb_ro_addr = &ro_marker, .csb_entitlements_blob = &bad_xml };
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b_bad_xml, &flags, NULL, 0, 0, NULL, NULL) == EBADEXEC);
    assert(miami_amfi_adjust_without_monitor(b_bad_xml.csb_entitlements, &b_bad_xml) == KERN_DENIED);
    struct cs_blob b_hash_err = { .csb_ro_addr = &ro_marker, .csb_entitlements_blob = &valid_xml, .xml_err = EBADEXEC };
    assert(miami_amfi_vnode_check_signature(&root_vp, NULL, 0, &b_hash_err, &flags, NULL, 0, 0, NULL, NULL) == EBADEXEC);

    /* 7. Permissive Sandbox policy syscalls and privilege grants. */
    assert(miami_sandbox_syscall(&p, 0, 0) == 0);
    assert(miami_sandbox_syscall(&p, 1, 0) == 0);
    assert(miami_sandbox_syscall(&p, 4, 0) == ENOENT);
    assert(miami_sandbox_syscall(&p, 5, 0) == ENOENT);
    assert(miami_sandbox_syscall(&p, 6, 0) == ENOENT);
    assert(miami_sandbox_syscall(&p, 0x43, 0) == ENOENT);
    assert(miami_sandbox_priv_grant(NULL, PRIV_WORK_INTERVAL) == 0);
    assert(miami_sandbox_priv_grant(NULL, 9999) == EPERM);

    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='miami-amfi-check-') as folder:
    path = Path(folder)
    (path / 'check.c').write_text(harness)
    subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', str(path / 'check.c'),
                    '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True)
print('PASS: staged AMFI XML entitlements, CS_PLATFORM_BINARY + CS_SIGNED policy, dual XML+DER support, and fail-closed DER-only/malformed rejection verified')
