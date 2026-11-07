"""Stage Apple's matching pthread kernel implementation for static MIAMI linking.

Apple's macos-135 release manifest pairs this tag with xnu-8796.141.3.
Source bytes come from pinned Git objects; no userspace implementation is built.
"""
import hashlib
from pathlib import Path
import subprocess

COMMIT = 'a6c70ca0e544347a0377babf748f831577ec24f9'
TAG = 'libpthread-514.100.2'
REPOSITORY = 'https://github.com/apple-oss-distributions/libpthread.git'
ROOT = 'bsd/miami_pthread'
SOURCES = {'kern_init.c': 'miami_pthread_init.c',
           'kern_support.c': 'miami_pthread_support.c',
           'kern_synch.c': 'miami_pthread_synch.c'}


def git(tree, *args):
    return subprocess.check_output(['git', '-C', str(tree), *args])


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Apple pthread integration anchor changed: ' + before[:80])
    return text.replace(before, after)


def stage(tree, source):
    if git(source, 'rev-parse', 'HEAD').decode().strip() != COMMIT:
        raise ValueError('Unexpected Apple libpthread commit')
    if (tree / ROOT).exists():
        raise ValueError('Use a fresh XNU tree for pthread integration')
    # XNU embeds opaque storage in uthread, while the paired libpthread
    # implementation accesses a trailing pointer at offset 48. Keep the
    # original layout for other boards and provide pointer alignment here.
    opaque = tree / 'bsd/sys/pthread_internal.h'
    text = opaque.read_text()
    text = replace_once(text, '\tchar opaque[48];',
        '#if defined(ARM64_BOARD_CONFIG_MIAMI)\n'
        '\tchar opaque[56] __attribute__((aligned(8)));\n'
        '#else\n\tchar opaque[48];\n#endif')
    opaque.write_bytes(text.encode())
    paths = git(source, 'ls-tree', '-r', '--name-only', 'HEAD', '--',
                'kern', 'include', 'private').decode().splitlines()
    records = []
    for path in paths:
        if not path.endswith(('.h', '.c')):
            continue
        if path.endswith('.c') and path not in ['kern/' + n for n in SOURCES]:
            raise ValueError('Unexpected pthread kernel source: ' + path)
        data = git(source, 'show', 'HEAD:' + path)
        text = data.decode()
        destination = path
        if path == 'kern/kern_internal.h':
            text = replace_once(text, 'typedef struct ksyn_waitq_element * ksyn_waitq_element_t;',
                '_Static_assert(sizeof(struct ksyn_waitq_element) == 56, "MIAMI pthread wait size mismatch");\n'
                '_Static_assert(_Alignof(struct ksyn_waitq_element) == 8, "MIAMI pthread wait alignment mismatch");\n'
                'typedef struct ksyn_waitq_element * ksyn_waitq_element_t;')
        if path == 'kern/kern_trace.h':
            text = replace_once(text, 'vm_kernel_unslide_or_perm_external(ptr, &unslid_ptr);',
                                'vm_kernel_unslide_or_perm_external((vm_offset_t)ptr, &unslid_ptr);')
        if path == 'kern/kern_support.c':
            # user_addr_t is an integer address, not a kernel C pointer.
            text = replace_once(text, '*kevent_list_out = NULL;', '*kevent_list_out = 0;')
            if text.count('user_addr_t kevent_list = NULL;') != 2:
                raise ValueError('Apple pthread event-address anchors changed')
            text = text.replace('user_addr_t kevent_list = NULL;', 'user_addr_t kevent_list = 0;')
            text = replace_once(text, 'workq_kevent(p, &th_addrs, NULL, 0, flags,',
                                'workq_kevent(p, &th_addrs, 0, 0, flags,')
        if path == 'kern/kern_synch.c':
            for name, count in (('psynch_wait_update_owner', 4),
                                ('psynch_wait_complete', 1), ('psynch_wait_wakeup', 2)):
                before = 'pthread_kern->' + name + '(kwq,'
                if text.count(before) != count:
                    raise ValueError('Apple pthread address-call anchor changed: ' + name)
                text = text.replace(before, 'pthread_kern->' + name + '((uintptr_t)kwq,')
        if path.startswith('kern/') and path.endswith('.c'):
            destination = 'kern/' + SOURCES[Path(path).name]
            if path == 'kern/kern_init.c':
                # XNU already owns the callback pointer and identical helper.
                # Reuse those definitions; keep Apple's real pthread_start/table.
                text = replace_once(text, 'pthread_callbacks_t pthread_kern;',
                                    '/* pthread_kern is owned by XNU pthread_shims.c. */')
                text = replace_once(text, '''struct uthread*
current_uthread(void)
{
\tthread_t th = current_thread();
\treturn pthread_kern->get_bsdthread_info(th);
}
''', '/* current_uthread is provided by XNU kern_proc.c. */\n')
            text = '#if defined(ARM64_BOARD_CONFIG_MIAMI)\n' + text + '\n#endif /* ARM64_BOARD_CONFIG_MIAMI */\n'
        target = tree / ROOT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
        records.append({'source': path, 'staged': ROOT + '/' + destination,
                        'source_sha256': hashlib.sha256(data).hexdigest(),
                        'staged_sha256': hashlib.sha256(text.encode()).hexdigest()})

    # The adapter uses in-kernel headers; the three original kext translation
    # units use this XNU's installed private headers, as in Apple's kext target.
    adapter = Path(__file__).with_name('pthread_register.c').read_bytes()
    (tree / ROOT / 'miami_pthread_register.c').write_bytes(adapter)

    files = tree / 'bsd/conf/files.arm64'
    files.write_bytes((files.read_text() + '\n# MIAMI static Apple pthread (source guarded by board config)\n' +
                      ''.join(ROOT + '/kern/' + name + '\tstandard\n' for name in SOURCES.values()) +
                      ROOT + '/miami_pthread_register.c\tstandard\n').encode())
    make = tree / 'bsd/conf/Makefile.template'
    flags = '\n# Match the Apple pthread kext compilation boundary.\n'
    for name in SOURCES.values():
        obj = Path(name).stem + '.o'
        flags += (obj + '_CFLAGS_RM += -DBSD_KERNEL_PRIVATE -D_KERNEL_BUILD -DKERNEL_BUILD -DMACH_KERNEL -DBSD_BUILD -DDRIVER_PRIVATE\n' +
                  obj + '_CFLAGS_ADD += -DMACH_KERNEL_PRIVATE -DABSOLUTETIME_SCALAR_TYPE -DNEEDS_SCHED_CALL_T -D__PTHREAD_EXPOSE_INTERNALS__ -I$(FAKEROOT_DIR)/$(KPINCDIR) -I$(FAKEROOT_DIR)/$(KINCDIR)\n' +
                  obj + '_INCFLAGS += -I$(SRCROOT)/' + ROOT + ' -I$(SRCROOT)/' + ROOT + '/private -I$(SRCROOT)/' + ROOT + '/include -isystem $(SDKROOT)/usr/include\n')
    make.write_bytes((make.read_text() + flags).encode())
    shims = tree / 'bsd/pthread/pthread_shims.c'
    shims_text = replace_once(shims.read_text(), '#include <stdatomic.h>\n',
                             '#include <stdatomic.h>\n#include <pexpert/pexpert.h>\n')
    shims.write_bytes(replace_once(shims_text, '\tpthread_functions->pthread_init();\n',
                     '\tpthread_functions->pthread_init();\n#if defined(MIAMI)\n'
                     '\tkprintf("MIAMI PTHREAD: kernel initialization complete\\n");\n#endif\n').encode())
    return {'repository': REPOSITORY, 'tag': TAG, 'commit': COMMIT,
            'registration': 'real pthread_start via EARLY_BOOT startup callback',
            'wait_storage': 'MIAMI LP64 56 bytes, 8-byte aligned; provider size and alignment asserted',
            'panic_guard_retained': True, 'files': records}
