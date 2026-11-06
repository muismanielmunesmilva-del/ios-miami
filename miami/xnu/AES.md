# Legacy AES provider for MIAMI

The complete image 0007 phone photograph now shows the preserved first panic:
`Kernel data abort.`, PC `0xfffffe00078f6a88`, LR `0xfffffe0007669f98`,
ESR `0x96000005`, FAR `0x78`. Its SHA-256 is
`b9c827e17f67065b5639aa493b589297aa5eefade8567e4e6ffc3bef798d00df`.
The earlier cropped photo supplies the remaining backtrace. Neither photo is
committed; only transcriptions/hashes are retained.

In the exact verified kernel, PC is `aes_encrypt_key128+0x10`, instruction
`0xf9403d00`: `ldr x0, [x8, #120]`. The preceding load reads `g_crypto_funcs`.
FAR 0x78 means that base x8 was zero. This is the unregistered crypto-function
table dereference, during TCP Fast Open key initialization. It matches the
independent host control's PC/ESR/FAR. Reaching TCP initialization establishes
return from `pthread_init` by the unconditional source call ordering; it does
not establish all pthread functionality or complete boot.

## Adaptation

The port selectively applies ios-sweet's existing patch 0020, transforming
only board/path names to MIAMI. Its adapter supplies real AES-CBC encrypt and
decrypt mode descriptors for the legacy XNU API, including the single-block
ECB wrappers used by TCP. The original key/context-size/error checks remain.
It does not disable TCP or replace crypto with success stubs.

The implementation is BearSSL's portable `aes_ct` bitslice C code, pinned to
`7bea48e5e850ab4cafbe68d3765cdaba13a86d6f`, the same immutable Git object used
by ios-sweet. Upstream is `https://www.bearssl.org/git/BearSSL`; its DNS did not
resolve in this session. Builds fetch that exact object from the status-im
GitHub mirror and reject a different HEAD. The source manifest records hashes
of every input/staged file and both original/transformed adapter patches.
Only public headers, five AES C units, two supporting headers and the MIT
license are staged. Kernel builds use general registers only for these units.

This provides legacy CBC/ECB only. It does not register the complete
`g_crypto_funcs` table or add GCM, XTS, hashes or other missing providers.
Those dependencies must be investigated from subsequent actual failures.

## Validation

The host test compiles the actual staged adapter, BearSSL units, this XNU's
real AES/corecrypto headers and its original legacy wrapper functions. External
kernel memory clearing and panic logging are supplied by the host harness;
GCM wrappers are excluded because this change leaves them untouched.

NIST SP 800-38A AES-CBC vectors for 128/192/256-bit keys and the FIPS-197
AES-128 single-block example pass encrypt/decrypt. Tests also cover in-place
and overlapping buffers, chaining/updated IV, unchanged wrapper input IV,
copied contexts, zero blocks, invalid key sizes/null keys and overflow guards.
Fresh source staging, preserved first-panic console tests, isolated early C
Darwin arm64 compilation and both workflow syntax checks pass locally.
The complete [Actions run 42287672552](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42287672552)
passed at `64c5ca35fabdfc6838192d07412ff486ab6fc6b1`. Independent checks verify
the exact kernel, all six AES implementation symbols, both actual CBC mode
descriptors (256-byte contexts, 16-byte blocks), retained pthread/panic code,
linked splash tables and MIT license identity.

Kernel: 15,922,656 bytes, SHA-256
`97085e47288650ee7b99a6ad03abf16666e3e6a0880fa1290fa86da91a59471a`.
Artifact13539790538 ZIP11,238,164 bytes, SHA-256
`039656570716e80b34ef143b0222ae345723b6ac9acf7f9d5e672ab160469932`.

The 150-second QEMU virt GIC/timer control now shows the pthread initialization
completion line, Skywalk self-tests passed, loopback/gif/stf thread scheduling
and an IOMedia/Apple_HFS root-device wait. No panic is visible in the final
snapshot; decoded text has zero unknown glyphs and CPU0 PC is cpu_idle+0x1ec.
This establishes post-AES host progress, not phone success or complete boot.

Image0008 passed real payload/live-FDT/header/AVB checks: 100,663,296 bytes,
SHA-256 `8115cf14c36fea21efe4c411dbc4f53f8ed8eebdf6f30f95cd088b3871df893a`.
Its physical temporary-boot test is pending. No root filesystem/storage driver
is included, so root-device waiting is the expected next observation.

## Sources

- [Apple legacy AES wrappers](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/libkern/crypto/corecrypto_aes.c)
- [Apple crypto registration](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/libkern/crypto/register_crypto.c)
- [Apple TCP key initialization](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/netinet/tcp_subr.c)
- [ios-sweet adapter](../../xnu/patches/0020-sweet-portable-aes-cbc.patch)
- [BearSSL constant-time AES design](https://bearssl.org/constanttime.html)
- [Pinned source mirror](https://github.com/status-im/BearSSL/tree/7bea48e5e850ab4cafbe68d3765cdaba13a86d6f)
- [NIST SP 800-38A, appendix F.2](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38a.pdf)
- [FIPS 197](https://csrc.nist.gov/pubs/fips/197/final)
