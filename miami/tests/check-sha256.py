#!/usr/bin/env python3
"""Execute the real XNU SHA256 wrappers and built-in provider against hashlib."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <libkern/crypto/sha2.h>
void cc_clear(size_t n, void *p) { volatile unsigned char *q = p; while (n--) *q++ = 0; }
void panic(const char *fmt, ...) { (void)fmt; abort(); }
int main(int argc, char **argv) {
    if (argc != 3) return 1;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    size_t chunk = strtoul(argv[2], NULL, 10); if (!chunk || chunk > 8192) return 3;
    unsigned char data[8192], digest[32]; SHA256_CTX ctx;
    SHA256_Init(&ctx); size_t n;
    while ((n = fread(data, 1, chunk, f))) SHA256_Update(&ctx, data, n);
    if (ferror(f)) return 4;
    fclose(f); SHA256_Final(digest, &ctx);
    for (unsigned i = 0; i < 32; i++) printf("%02x", digest[i]);
    puts(""); return 0;
}
'''


def check(source):
    with tempfile.TemporaryDirectory(prefix='miami-sha256-') as folder:
        temp = Path(folder)
        (temp / 'libkern/crypto').mkdir(parents=True)
        (temp / 'kern').mkdir()
        (temp / 'libkern/libkern.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <string.h>\n')
        (temp / 'libkern/crypto/crypto_internal.h').write_text('/* SHA256 uses the actual built-in provider. */\n')
        (temp / 'kern/debug.h').write_text('void panic(const char *, ...) __attribute__((noreturn));\n')
        wrapper = (source / 'libkern/crypto/corecrypto_sha2.c').read_text()
        wrapper = wrapper[:wrapper.index('void\nSHA384_Init(')] + '\n#endif\n'
        assert '#define SHA256_DI()' in wrapper and '(&ccsha256_ltc_di)' in wrapper
        (temp / 'wrapper.c').write_text(wrapper)
        (temp / 'harness.c').write_text(HARNESS)
        units = ['ccdigest_init', 'ccdigest_update', 'ccdigest_final_64be',
                 'ccsha256_ltc_di', 'ccsha256_ltc_compress', 'ccsha256_K', 'ccsha256_initial_state']
        files = [temp / 'harness.c', temp / 'wrapper.c']
        files += [source / 'osfmk/corecrypto' / (n + '.c') for n in units]
        command = ['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-DARM64_BOARD_CONFIG_MIAMI',
                   '-DCRYPTO_SHA2', '-DCC_DARWIN=0', '-I', str(temp),
                   '-I', str(source / 'EXTERNAL_HEADERS'), '-I', str(source / 'libkern')]
        subprocess.run(command + [str(p) for p in files] + ['-o', str(temp / 'sha')], check=True)
        cases = [b'', b'abc'] + [bytes((i * 37) & 255 for i in range(n))
                                for n in (1, 55, 56, 63, 64, 65, 4096, 65536, 1000000)]
        for data in cases:
            (temp / 'input').write_bytes(data)
            for chunk in (1, 7, 64, 4093):
                actual = subprocess.check_output([str(temp / 'sha'), str(temp / 'input'), str(chunk)], text=True).strip()
                assert actual == hashlib.sha256(data).hexdigest(), (len(data), chunk)
    print('PASS: actual XNU SHA256 wrappers/built-in provider match hashlib for 44 empty/known/boundary/large and chunking cases')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
