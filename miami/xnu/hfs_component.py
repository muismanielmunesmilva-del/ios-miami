"""Stage Apple's open-source hfs-627.100.6 for the built-in MIAMI HFS+ filesystem."""
import hashlib
from pathlib import Path
import subprocess

COMMIT = '31d5ec238dfab485e78a9a30b8b92d13e8914f03'
TAG = 'hfs-627.100.6'
REPOSITORY = 'https://github.com/apple-oss-distributions/hfs.git'
ROOT = 'bsd/miami_hfs'
PATCHES = ('0026-sweet-builtin-hfs.patch',
           '0029-sweet-unsealed-root-volume.patch',
           '0031-sweet-read-write-root.patch',
           '0041-sweet-hfs-link-notes.patch',
           '0052-sweet-hfs-rename-swap.patch')
TARGET_CONDITIONALS = b'''#ifndef __TARGETCONDITIONALS__
#define __TARGETCONDITIONALS__
#define TARGET_OS_MAC 1
#define TARGET_OS_OSX 1
#define TARGET_OS_IPHONE 0
#define TARGET_OS_IOS 0
#define TARGET_OS_WATCH 0
#define TARGET_OS_TV 0
#define TARGET_OS_MACCATALYST 0
#define TARGET_OS_SIMULATOR 0
#define TARGET_OS_EMBEDDED 0
#define TARGET_OS_DRIVERKIT 0
#define TARGET_OS_WIN32 0
#define TARGET_OS_UNIX 0
#define TARGET_CPU_ARM64 1
#define TARGET_CPU_X86_64 0
#define TARGET_RT_64_BIT 1
#define TARGET_RT_LITTLE_ENDIAN 1
#define TARGET_RT_BIG_ENDIAN 0
#endif /* __TARGETCONDITIONALS__ */
'''


def git(tree, *args, data=None):
    res = subprocess.run(['git', '-C', str(tree), *args], input=data,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode:
        raise RuntimeError(f'git {args}: {res.stderr.decode(errors="replace")}')
    return res.stdout


def stage(tree, source):
    if git(source, 'rev-parse', 'HEAD').decode().strip() != COMMIT:
        raise ValueError('Unexpected Apple HFS commit')
    target = tree / ROOT
    if target.exists():
        raise ValueError('Use a fresh XNU tree for HFS integration')
    paths = git(source, 'ls-tree', '-r', '--name-only', 'HEAD', '--',
                'core', 'hfs_encodings').decode().splitlines()
    records = []
    for path in paths:
        data = git(source, 'show', 'HEAD:' + path)
        staged = data
        if path == 'core/hfs_iokit.h':
            text = data.decode('utf-8')
            include = '#include <AppleKeyStore/AppleKeyStoreFSServices.h>\n'
            first = 'int hfs_unwrap_key('
            end = '__END_DECLS'
            if text.count(include) != 1 or text.count(first) != 1 or text.count(end) != 1:
                raise ValueError('HFS AppleKeyStore header anchor changed')
            text = text.replace(include, '#if CONFIG_PROTECT\n' + include + '#endif\n')
            i, j = text.index(first), text.index(end)
            text = text[:i] + '#if CONFIG_PROTECT\n' + text[i:j].rstrip('\n') + '\n#endif\n\n' + text[j:]
            staged = text.encode('utf-8')
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(staged)
        records.append({'source': path, 'source_sha256': hashlib.sha256(data).hexdigest(),
                        'staged_sha256': hashlib.sha256(staged).hexdigest()})
    (target / 'TargetConditionals.h').write_bytes(TARGET_CONDITIONALS)
    port = Path(__file__).resolve().parents[2]
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)
    patch_records = []
    for name in PATCHES:
        original = (port / 'xnu/patches' / name).read_bytes().replace(b'\r\n', b'\n')
        patch = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
        if name == '0026-sweet-builtin-hfs.patch':
            old_hunk = (
                b'diff --git a/bsd/conf/Makefile.template b/bsd/conf/Makefile.template\n'
                b'--- a/bsd/conf/Makefile.template\n'
                b'+++ b/bsd/conf/Makefile.template\n'
                b'@@ -51,6 +51,15 @@\n'
                b' miami_pthread_init.o_INCFLAGS = $(MIAMI_PTHREAD_INC)\n'
                b' miami_pthread_support.o_INCFLAGS = $(MIAMI_PTHREAD_INC)\n'
                b' miami_pthread_synch.o_INCFLAGS = $(MIAMI_PTHREAD_INC)\n'
                b'+\n'
                b'+# Apple OSS HFS built in (bsd/miami_hfs): compiled like the kext, see miami_hfs_compat.h.\n'
                b'+# The compat header must come after the kernel\'s -D options, hence _CFLAGS_ADD.\n'
                b'+MIAMI_HFS_ROOT = $(SRCROOT)/bsd/miami_hfs\n'
                b'+MIAMI_HFS_OBJS = BTree.o BTreeAllocate.o BTreeMiscOps.o BTreeNodeOps.o BTreeNodeReserve.o BTreeScanner.o BTreeTreeOps.o BTreeWrapper.o CatalogUtilities.o FileExtentMapping.o FileIDsServices.o MacOSStubs.o UnicodeWrappers.o VolumeAllocation.o hfs_attrlist.o hfs_btreeio.o hfs_catalog.o hfs_chash.o hfs_cnode.o hfs_cprotect.o hfs_endian.o hfs_extents.o hfs_fsinfo.o hfs_hotfiles.o hfs_journal.o hfs_link.o hfs_lookup.o hfs_notification.o hfs_quota.o hfs_readwrite.o hfs_resize.o hfs_search.o hfs_vfsops.o hfs_vfsutils.o hfs_vnops.o hfs_xattr.o rangelist.o hfs_encodinghint.o hfs_encodings.o miami_hfs_iokit.o\n'
                b'+$(foreach o,$(MIAMI_HFS_OBJS),$(eval $(o)_CFLAGS_ADD += -include $(MIAMI_HFS_ROOT)/miami_hfs_compat.h -I$(MIAMI_HFS_ROOT) -I$(MIAMI_HFS_ROOT)/core))\n'
                b'+# HFSEncodings is a separate kext on Apple with its own allocation counter.\n'
                b'+hfs_encodings.o_CFLAGS_ADD += -Dhfs_allocated=hfs_encodings_allocated\n'
                b'+hfs_encodinghint.o_CFLAGS_ADD += -Dhfs_allocated=hfs_encodings_allocated\n'
                b' endif\n'
                b' \n'
                b' #\n'
            )
            new_hunk = (
                b'diff --git a/bsd/conf/Makefile.template b/bsd/conf/Makefile.template\n'
                b'--- a/bsd/conf/Makefile.template\n'
                b'+++ b/bsd/conf/Makefile.template\n'
                b'@@ -43,5 +43,16 @@\n'
                b' \t-DBSD_KERNEL_PRIVATE -DLP64_DEBUG=0 \\\n'
                b'         -Warray-bounds-pointer-arithmetic\n'
                b' SFLAGS+= -include meta_features.h\n'
                b'+\n'
                b'+ifeq ($(CURRENT_MACHINE_CONFIG),MIAMI)\n'
                b'+# Apple OSS HFS built in (bsd/miami_hfs): compiled like the kext, see miami_hfs_compat.h.\n'
                b'+# The compat header must come after the kernel\'s -D options, hence _CFLAGS_ADD.\n'
                b'+MIAMI_HFS_ROOT = $(SRCROOT)/bsd/miami_hfs\n'
                b'+MIAMI_HFS_OBJS = BTree.o BTreeAllocate.o BTreeMiscOps.o BTreeNodeOps.o BTreeNodeReserve.o BTreeScanner.o BTreeTreeOps.o BTreeWrapper.o CatalogUtilities.o FileExtentMapping.o FileIDsServices.o MacOSStubs.o UnicodeWrappers.o VolumeAllocation.o hfs_attrlist.o hfs_btreeio.o hfs_catalog.o hfs_chash.o hfs_cnode.o hfs_cprotect.o hfs_endian.o hfs_extents.o hfs_fsinfo.o hfs_hotfiles.o hfs_journal.o hfs_link.o hfs_lookup.o hfs_notification.o hfs_quota.o hfs_readwrite.o hfs_resize.o hfs_search.o hfs_vfsops.o hfs_vfsutils.o hfs_vnops.o hfs_xattr.o rangelist.o hfs_encodinghint.o hfs_encodings.o miami_hfs_iokit.o\n'
                b'+$(foreach o,$(MIAMI_HFS_OBJS),$(eval $(o)_CFLAGS_ADD += -include $(MIAMI_HFS_ROOT)/miami_hfs_compat.h -I$(MIAMI_HFS_ROOT) -I$(MIAMI_HFS_ROOT)/core))\n'
                b'+# HFSEncodings is a separate kext on Apple with its own allocation counter.\n'
                b'+hfs_encodings.o_CFLAGS_ADD += -Dhfs_allocated=hfs_encodings_allocated\n'
                b'+hfs_encodinghint.o_CFLAGS_ADD += -Dhfs_allocated=hfs_encodings_allocated\n'
                b'+endif\n'
                b' \n'
                b' #\n'
            )
            if patch.count(old_hunk) != 1:
                raise ValueError('0026 Makefile.template hunk anchor changed')
            patch = patch.replace(old_hunk, new_hunk)
        git(tree, 'apply', '--check', '--whitespace=nowarn', '-', data=patch)
        git(tree, 'apply', '--whitespace=nowarn', '-', data=patch)
        (patch_dir / name.replace('sweet', 'miami')).write_bytes(patch)
        patch_records.append({'name': name, 'input_sha256': hashlib.sha256(original).hexdigest(),
                              'target_sha256': hashlib.sha256(patch).hexdigest()})
    return {'repository': REPOSITORY, 'tag': TAG, 'commit': COMMIT,
            'root': ROOT, 'patches': patch_records, 'files': records}
