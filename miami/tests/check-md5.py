#!/usr/bin/env python3
"""Execute the real staged XNU MD5 wrappers and BearSSL provider against hashlib."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <libkern/crypto/md5.h>
void panic(const char *fmt, ...) { (void)fmt; abort(); }
int main(int argc, char **argv) {
    if (argc != 3) return 1;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    size_t chunk = strtoul(argv[2], NULL, 10); if (!chunk || chunk > 8192) return 3;
    unsigned char data[8192], digest[MD5_DIGEST_LENGTH];
    MD5_CTX ctx, copied;
    MD5Init(&ctx);
    size_t n;
    while ((n = fread(data, 1, chunk, f))) {
        MD5Update(&ctx, data, (unsigned int)n);
        copied = ctx;
        ctx = copied;
    }
    if (ferror(f)) return 4;
    fclose(f);
    MD5Final(digest, &ctx);
    for (unsigned i = 0; i < MD5_DIGEST_LENGTH; i++) printf("%02x", digest[i]);
    puts("");
    return 0;
}
'''


def check(source):
    with tempfile.TemporaryDirectory(prefix='miami-md5-') as folder:
        temp = Path(folder)
        (temp / 'libkern/crypto').mkdir(parents=True)
        (temp / 'kern').mkdir()
        (temp / 'machine').mkdir()
        (temp / 'machine/types.h').write_text('#include <stdint.h>\ntypedef uint32_t u_int32_t;\n')
        (temp / 'libkern/libkern.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <string.h>\n')
        (temp / 'libkern/crypto/crypto_internal.h').write_text('/* MD5 uses the staged BearSSL provider. */\n')
        (temp / 'kern/debug.h').write_text('void panic(const char *, ...) __attribute__((noreturn));\n')
        wrapper = (source / 'libkern/crypto/corecrypto_md5.c').read_text()
        assert 'miami_bearssl/inc/bearssl_hash.h' in wrapper
        assert 'MD5ToBr(' in wrapper and 'BrToMD5(' in wrapper
        (temp / 'harness.c').write_text(HARNESS)
        crypto = source / 'libkern/crypto'
        bearssl = crypto / 'miami_bearssl'
        files = [temp / 'harness.c', crypto / 'corecrypto_md5.c',
                 crypto / 'miami_md5.c', crypto / 'miami_dec32le.c', crypto / 'miami_enc32le.c']
        command = ['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-DARM64_BOARD_CONFIG_MIAMI',
                   '-DCC_DARWIN=0', '-I', str(temp), '-I', str(source / 'EXTERNAL_HEADERS'),
                   '-I', str(source / 'libkern'), '-I', str(bearssl / 'inc'), '-I', str(bearssl / 'src')]
        subprocess.run(command + [str(p) for p in files] + ['-o', str(temp / 'md5')], check=True)
        cases = [b'', b'a', b'abc', b'message digest',
                 b'abcdefghijklmnopqrstuvwxyz',
                 b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
                 b'12345678901234567890123456789012345678901234567890123456789012345678901234567890']
        cases += [bytes((i * 41) & 255 for i in range(n))
                  for n in (1, 55, 56, 63, 64, 65, 4096, 65536)]
        for data in cases:
            (temp / 'input').write_bytes(data)
            for chunk in (1, 7, 64, 4093):
                actual = subprocess.check_output([str(temp / 'md5'), str(temp / 'input'), str(chunk)], text=True).strip()
                assert actual == hashlib.md5(data).hexdigest(), (len(data), chunk)
    print('PASS: actual XNU MD5 wrappers + staged BearSSL provider match RFC 1321/hashlib across 60 cases and chunk sizes')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
