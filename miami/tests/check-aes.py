#!/usr/bin/env python3
"""Run actual staged XNU legacy AES wrappers/provider against NIST vectors.

Uses this XNU's real AES/corecrypto headers. Only external kernel logging and
memory-clear facilities are supplied by the host harness. GCM is not changed
by this adapter and is excluded from this CBC/ECB functional executable.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

HARNESS = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libkern/crypto/aes.h>
extern const struct ccmode_cbc miami_aes_cbc_encrypt, miami_aes_cbc_decrypt;
void cc_clear(size_t size, void *out) { volatile unsigned char *p = out; while (size--) *p++ = 0; }
void panic(const char *fmt, ...) { (void)fmt; abort(); }
static void hex(unsigned char *out, const char *text) {
    while (*text) { unsigned n; assert(sscanf(text, "%2x", &n) == 1); *out++ = n; text += 2; }
}
static const char *keys[] = {
    "2b7e151628aed2a6abf7158809cf4f3c",
    "8e73b0f7da0e6452c810f32b809079e562f8ead2522c6b7b",
    "603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4"
};
static const char *ciphertexts[] = {
    "7649abac8119b246cee98e9b12e9197d5086cb9b507219ee95db113a917678b2"
    "73bed6b8e3c1743b7116e69e222295163ff1caa1681fac09120eca307586e1a7",
    "4f021db243bc633d7178183a9fa071e8b4d9ada9ad7dedf4e5e738763f69145a"
    "571b242012fb7ae07fa9baac3df102e008b0e27988598881d920a9e64f5615cd",
    "f58c4c04d6e5f1ba779eabfb5f7bfbd69cfc4e967edb808d679f777bc6702c7d"
    "39f23369a9d9bacfa530e26304231461b2eb05e2c39be9fcda6c19078c6a9d1b"
};
int main(void) {
    unsigned char plain[64], key[32], iv[16], saved_iv[16], expected[64];
    struct { unsigned char before[16], data[80], after[16]; } buffer;
    memset(&buffer, 0xa5, sizeof(buffer));
    hex(plain, "6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51"
               "30c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710");
    for (unsigned test = 0; test < 3; test++) {
        hex(key, keys[test]); hex(expected, ciphertexts[test]);
        hex(iv, "000102030405060708090a0b0c0d0e0f"); memcpy(saved_iv, iv, 16);
        aes_encrypt_ctx enc; aes_decrypt_ctx dec;
        assert(!aes_encrypt_key(key, 16 + test * 8, &enc));
        assert(!aes_decrypt_key(key, 16 + test * 8, &dec));
        assert(!aes_encrypt_cbc(plain, iv, 4, buffer.data, &enc));
        assert(!memcmp(buffer.data, expected, 64) && !memcmp(iv, saved_iv, 16));
        assert(!aes_decrypt_cbc(buffer.data, iv, 4, buffer.data, &dec));
        assert(!memcmp(buffer.data, plain, 64) && !memcmp(iv, saved_iv, 16));
        memcpy(buffer.data, plain, 64);
        assert(!aes_encrypt_cbc(buffer.data, iv, 4, buffer.data, &enc));
        assert(!memcmp(buffer.data, expected, 64));
        /* Real provider IV updates permit chunking; contexts can be copied. */
        aes_encrypt_ctx copied = enc;
        cccbc_iv_decl(16, chain);
        memcpy(chain, saved_iv, 16);
        assert(!miami_aes_cbc_encrypt.cbc(copied.ctx, chain, 1, plain, buffer.data));
        assert(!miami_aes_cbc_encrypt.cbc(copied.ctx, chain, 3, plain + 16, buffer.data + 16));
        assert(!memcmp(buffer.data, expected, 64) && !memcmp(chain, expected + 48, 16));
        memcpy(chain, saved_iv, 16);
        assert(!miami_aes_cbc_decrypt.cbc(dec.ctx, chain, 2, expected, buffer.data));
        assert(!miami_aes_cbc_decrypt.cbc(dec.ctx, chain, 2, expected + 32, buffer.data + 32));
        assert(!memcmp(buffer.data, plain, 64) && !memcmp(chain, expected + 48, 16));
        /* Partial overlap is handled by the provider's memmove. */
        memcpy(buffer.data, plain, 64);
        assert(!aes_encrypt_cbc(buffer.data, iv, 4, buffer.data + 1, &enc));
        assert(!memcmp(buffer.data + 1, expected, 64));
        assert(!aes_encrypt_cbc(NULL, iv, 0, NULL, &enc));
        assert(aes_encrypt_key(key, 15, &enc) != 0);
        assert(aes_decrypt_key(NULL, 16, &dec) != 0);
        for (unsigned i = 0; i < 16; i++) assert(buffer.before[i] == 0xa5 && buffer.after[i] == 0xa5);
    }
    aes_encrypt_ctx enc; aes_decrypt_ctx dec;
    hex(key, "000102030405060708090a0b0c0d0e0f");
    hex(plain, "00112233445566778899aabbccddeeff");
    hex(expected, "69c4e0d86a7b0430d8cdb78070b4c55a");
    assert(!aes_encrypt_key128(key, &enc)); assert(!aes_decrypt_key128(key, &dec));
    assert(!aes_encrypt(plain, buffer.data, &enc)); assert(!memcmp(buffer.data, expected, 16));
    assert(!aes_decrypt(expected, buffer.data, &dec)); assert(!memcmp(buffer.data, plain, 16));
    cccbc_iv_decl(16, chain); memset(chain, 0, 16);
    assert(miami_aes_cbc_encrypt.cbc(enc.ctx, chain, SIZE_MAX / 16 + 1, plain, buffer.data) != 0);
    assert(miami_aes_cbc_encrypt.cbc(enc.ctx, NULL, 1, plain, buffer.data) != 0);
    assert(miami_aes_cbc_encrypt.cbc(NULL, chain, 1, plain, buffer.data) != 0);
    return 0;
}
'''


def check(source):
    with tempfile.TemporaryDirectory(prefix='miami-aes-') as folder:
        temp = Path(folder)
        for directory in ('libkern/crypto', 'kern'):
            (temp / directory).mkdir(parents=True)
        (temp / 'libkern/libkern.h').write_text('#include <stddef.h>\n#include <stdint.h>\n#include <string.h>\n')
        (temp / 'libkern/crypto/crypto_internal.h').write_text('/* Legacy CBC/ECB uses the staged mode descriptors. */\n')
        (temp / 'kern/debug.h').write_text('void panic(const char *, ...) __attribute__((noreturn));\n')
        legacy = (source / 'libkern/crypto/corecrypto_aes.c').read_text()
        legacy = legacy[:legacy.index('aes_rval\naes_encrypt_key_gcm(')]
        assert legacy.count('AES_CBC_ENCRYPT_MODE;') == 2
        assert legacy.count('AES_CBC_DECRYPT_MODE;') == 2
        (temp / 'legacy.c').write_text(legacy)
        (temp / 'harness.c').write_text(HARNESS)
        crypto = source / 'libkern/crypto'
        bearssl = crypto / 'miami_bearssl'
        files = [temp / 'harness.c', temp / 'legacy.c', crypto / 'miami_aes.c']
        files += [crypto / ('miami_' + unit + '.c') for unit in
                  ('aes_ct', 'aes_ct_enc', 'aes_ct_dec', 'aes_ct_cbcenc', 'aes_ct_cbcdec')]
        command = ['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-DARM64_BOARD_CONFIG_MIAMI',
                   '-DCC_DARWIN=0', '-I', str(temp), '-I', str(source / 'EXTERNAL_HEADERS'),
                   '-I', str(source / 'libkern'), '-I', str(bearssl / 'inc'), '-I', str(bearssl / 'src')]
        subprocess.run(command + [str(p) for p in files] + ['-o', str(temp / 'aes')], check=True)
        subprocess.run([str(temp / 'aes')], check=True)
    print('PASS: actual XNU headers/legacy wrappers + staged BearSSL adapter; NIST AES-128/192/256 CBC and AES-128 ECB, in-place/overlap/chunking/IV/context copy, invalid keys and overflow guards')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
