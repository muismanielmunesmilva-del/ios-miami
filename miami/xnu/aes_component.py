"""Stage the audited ios-sweet legacy AES/MD5 adapters and pinned BearSSL C code."""
import hashlib
from pathlib import Path
import subprocess

COMMIT = '7bea48e5e850ab4cafbe68d3765cdaba13a86d6f'
REPOSITORY = 'https://www.bearssl.org/git/BearSSL'
MIRROR = 'https://github.com/status-im/BearSSL.git'
ROOT = 'libkern/crypto/miami_bearssl'
UNITS = ('aes_ct', 'aes_ct_enc', 'aes_ct_dec', 'aes_ct_cbcenc', 'aes_ct_cbcdec')
MD5_FILES = ('src/hash/md5.c', 'src/codec/dec32le.c', 'src/codec/enc32le.c')


def git(tree, *args, data=None):
    return subprocess.run(['git', '-C', str(tree), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def stage(tree, source):
    if git(source, 'rev-parse', 'HEAD').decode().strip() != COMMIT:
        raise ValueError('Unexpected BearSSL commit')
    if (tree / ROOT).exists():
        raise ValueError('Use a fresh XNU tree for AES/MD5 integration')
    port = Path(__file__).resolve().parents[2]
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)
    original = (port / 'xnu/patches/0020-sweet-portable-aes-cbc.patch').read_bytes().replace(b'\r\n', b'\n')
    patch = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
    git(tree, 'apply', '--check', '--whitespace=nowarn', '-', data=patch)
    git(tree, 'apply', '--whitespace=nowarn', '-', data=patch)
    (patch_dir / '0020-miami-portable-aes-cbc.patch').write_bytes(patch)
    md5_original = (port / 'xnu/patches/0027-sweet-bearssl-md5.patch').read_bytes().replace(b'\r\n', b'\n')
    md5_patch = md5_original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
    git(tree, 'apply', '--check', '--whitespace=nowarn', '-', data=md5_patch)
    git(tree, 'apply', '--whitespace=nowarn', '-', data=md5_patch)
    (patch_dir / '0027-miami-bearssl-md5.patch').write_bytes(md5_patch)
    paths = git(source, 'ls-tree', '-r', '--name-only', 'HEAD', '--', 'inc').decode().splitlines()
    paths += ['src/inner.h', 'src/config.h', 'LICENSE.txt']
    paths += ['src/symcipher/' + unit + '.c' for unit in UNITS]
    paths += list(MD5_FILES)
    records = []
    for path in paths:
        if path.startswith('inc/') and not path.endswith('.h'):
            raise ValueError('Unexpected public BearSSL file: ' + path)
        data = git(source, 'show', 'HEAD:' + path)
        staged = data
        if path == 'src/inner.h':
            before = b'#include <limits.h>'
            if data.count(before) != 1:
                raise ValueError('BearSSL limits include anchor changed')
            staged = data.replace(before, b'#if defined(KERNEL)\n#include <machine/limits.h>\n#else\n#include <limits.h>\n#endif')
        destination = tree / ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(staged)
        records.append({'source': path, 'source_sha256': hashlib.sha256(data).hexdigest(),
                        'staged_sha256': hashlib.sha256(staged).hexdigest()})
    return {'repository': REPOSITORY, 'mirror': MIRROR, 'commit': COMMIT,
            'adapter_patch': '0020-sweet-portable-aes-cbc.patch',
            'adapter_input_sha256': hashlib.sha256(original).hexdigest(),
            'adapter_target_sha256': hashlib.sha256(patch).hexdigest(),
            'md5_patch': '0027-sweet-bearssl-md5.patch',
            'md5_input_sha256': hashlib.sha256(md5_original).hexdigest(),
            'md5_target_sha256': hashlib.sha256(md5_patch).hexdigest(),
            'legacy_modes': ['AES-CBC encrypt/decrypt', 'single-block ECB via zero-IV CBC',
                             'MD5Init/MD5Update/MD5Final via BearSSL br_md5'],
            'implementation': 'BearSSL aes_ct portable bitslice C and br_md5; no heap/SIMD/crypto extensions',
            'full_corecrypto_provider_registered': False,
            'other_crypto_modes_unchanged': True, 'files': records}
