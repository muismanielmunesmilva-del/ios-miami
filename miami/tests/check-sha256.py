#!/usr/bin/env python3
"""Execute the real XNU SHA-1, SHA-256, SHA-384, and SHA-512 wrappers against hashlib."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <libkern/crypto/sha1.h>
#include <libkern/crypto/sha2.h>
void cc_clear(size_t n, void *p) { volatile unsigned char *q = p; while (n--) *q++ = 0; }
void panic(const char *fmt, ...) { (void)fmt; abort(); }
static void print_hex(const unsigned char *buf, unsigned n) {
    for (unsigned i = 0; i < n; i++) printf("%02x", buf[i]);
    puts("");
}
int main(int argc, char **argv) {
    if (argc != 3) return 1;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    size_t chunk = strtoul(argv[2], NULL, 10); if (!chunk || chunk > 8192) return 3;
    unsigned char data[8192], d1[20], d256[32], d384[48], d512[64];
    SHA1_CTX c1, c1_copy;
    SHA256_CTX c256;
    SHA384_CTX c384, c384_copy;
    SHA512_CTX c512, c512_copy;
    SHA1Init(&c1);
    SHA256_Init(&c256);
    SHA384_Init(&c384);
    SHA512_Init(&c512);
    size_t n;
    while ((n = fread(data, 1, chunk, f))) {
        SHA1Update(&c1, data, n); c1_copy = c1; c1 = c1_copy;
        SHA256_Update(&c256, data, n);
        SHA384_Update(&c384, data, n); c384_copy = c384; c384 = c384_copy;
        SHA512_Update(&c512, data, n); c512_copy = c512; c512 = c512_copy;
    }
    if (ferror(f)) return 4;
    fclose(f);
    SHA1Final(d1, &c1);
    SHA256_Final(d256, &c256);
    SHA384_Final(d384, &c384);
    SHA512_Final(d512, &c512);
    print_hex(d1, 20);
    print_hex(d256, 32);
    print_hex(d384, 48);
    print_hex(d512, 64);
    return 0;
}
'''


def check(source):
    with tempfile.TemporaryDirectory(prefix='miami-sha-') as folder:
        temp = Path(folder)
        (temp / 'libkern/crypto').mkdir(parents=True)
        (temp / 'kern').mkdir()
        (temp / 'sys').mkdir()
        (temp / 'sys/types.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u_int8_t;\ntypedef uint32_t u_int32_t;\ntypedef uint64_t u_int64_t;\ntypedef int kern_return_t;\ntypedef bool Boolean;\n')
        (temp / 'sys/systm.h').write_text('/* host test stub */\n')
        (temp / 'machine').mkdir()
        (temp / 'machine/types.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u_int8_t;\ntypedef uint32_t u_int32_t;\ntypedef uint64_t u_int64_t;\ntypedef int kern_return_t;\ntypedef bool Boolean;\n')
        (temp / 'libkern/libkern.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <string.h>\n')
        (temp / 'libkern/OSAtomic.h').write_text('#include <stdbool.h>\nstatic inline bool OSCompareAndSwapPtr(void *o, void *n, void * volatile *a) { if (*a == o) { *a = n; return true; } return false; }\n')
        (temp / 'libkern/crypto/crypto_internal.h').write_text('/* SHA-1/SHA-2 use built-in and BearSSL providers. */\n')
        (temp / 'kern/debug.h').write_text('void panic(const char *, ...) __attribute__((noreturn));\n')
        wrapper_sha1 = (source / 'libkern/crypto/corecrypto_sha1.c').read_text()
        assert 'miami_bearssl/inc/bearssl_hash.h' in wrapper_sha1
        assert 'SHA1ToBr(' in wrapper_sha1 and 'BrToSHA1(' in wrapper_sha1
        wrapper_sha2 = (source / 'libkern/crypto/corecrypto_sha2.c').read_text()
        assert '#define SHA256_DI()' in wrapper_sha2 and '(&ccsha256_ltc_di)' in wrapper_sha2
        assert 'br_sha384_init(' in wrapper_sha2 and 'br_sha512_init(' in wrapper_sha2
        (temp / 'harness.c').write_text(HARNESS)
        crypto = source / 'libkern/crypto'
        bearssl = crypto / 'miami_bearssl'
        units = ['ccdigest_init', 'ccdigest_update', 'ccdigest_final_64be',
                 'ccsha256_ltc_di', 'ccsha256_ltc_compress', 'ccsha256_K', 'ccsha256_initial_state']
        files = [temp / 'harness.c',
                 crypto / 'corecrypto_sha1.c', crypto / 'miami_sha1.c',
                 crypto / 'miami_dec32be.c', crypto / 'miami_enc32be.c',
                 crypto / 'corecrypto_sha2.c', crypto / 'miami_sha2big.c',
                 crypto / 'miami_dec64be.c', crypto / 'miami_enc64be.c']
        files += [source / 'osfmk/corecrypto' / (n + '.c') for n in units]
        command = ['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-DARM64_BOARD_CONFIG_MIAMI',
                   '-DCRYPTO_SHA2', '-DCC_DARWIN=0', '-I', str(temp),
                   '-I', str(source / 'EXTERNAL_HEADERS'), '-I', str(source / 'libkern'),
                   '-I', str(bearssl / 'inc'), '-I', str(bearssl / 'src')]
        subprocess.run(command + [str(p) for p in files] + ['-o', str(temp / 'sha')], check=True)
        cases = [b'', b'abc'] + [bytes((i * 37) & 255 for i in range(n))
                                for n in (1, 55, 56, 63, 64, 65, 111, 112, 127, 128, 129, 4096, 65536, 1000000)]
        for data in cases:
            (temp / 'input').write_bytes(data)
            for chunk in (1, 7, 64, 128, 4093):
                lines = subprocess.check_output([str(temp / 'sha'), str(temp / 'input'), str(chunk)], text=True).strip().splitlines()
                assert len(lines) == 4
                assert lines[0] == hashlib.sha1(data).hexdigest(), ('sha1', len(data), chunk)
                assert lines[1] == hashlib.sha256(data).hexdigest(), ('sha256', len(data), chunk)
                assert lines[2] == hashlib.sha384(data).hexdigest(), ('sha384', len(data), chunk)
                assert lines[3] == hashlib.sha512(data).hexdigest(), ('sha512', len(data), chunk)
    print('PASS: actual XNU SHA-1, SHA-256, SHA-384, and SHA-512 wrappers/providers match hashlib across 80 cases and chunk sizes')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
