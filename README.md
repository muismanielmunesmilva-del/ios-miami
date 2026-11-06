# ios-miami

Single-CPU XNU bring-up for Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

The pthread integration passed every gate in [Actions run 42239849041](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42239849041), source commit `51c1948587595f336115c65f0abe5f8c2dc07862`. Apple's matching libpthread-514.100.2 is pinned to `a6c70ca0e544347a0377babf748f831577ec24f9`. The real implementation and panic guards are retained. ZIP/kernel identity, actual Mach-O implementation symbols, embedded ADT and linked table alignment passed independent checks.

The host-only virtual GIC/timer control shows pthread callback registration and CPU/SGI1 completion. After XNU's 30-second RTC-service wait, its later domaininit/tcp_init backtrace establishes return from pthread_init by source call ordering; the completion line was overwritten. The control then aborts in aes_encrypt_key128+0x10 (ESR 0x96000005, FAR 0x78). The crypto provider is the next dependency to investigate. This is not a full boot or a phone result.

On the phone, image 0004's photograph confirms XNU console, platform expert and VM bootstrap progress. Image 0005's user report confirms CPU/SGI1 progress, followed by a photograph whose backtrace identifies the previous missing pthread-table guard; the panic header is outside the photo. Image 0006 was accepted by temporary fastboot boot; its photograph confirms XNU panic output with the exact verified kernel UUID. The reason, exception registers and backtrace are absent, so its cause and phone pthread completion remain unproven. iOS userland has not started.

The first-panic diagnostic passed the complete [Actions run 42281662142](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42281662142) at `988db79023cdce6805785bcc980b65a2adf07094`. In a 45-second host control, its protected pane survives the native panic report and its PC/ESR/FAR match QEMU's independent exception trace. Image 0007 passed packaging/FDT/AVB checks and was accepted by temporary fastboot boot. The complete phone photo now confirms the protected first-panic pane: Kernel data abort, PC `0xfffffe00078f6a88` (`aes_encrypt_key128+0x10`), ESR `0x96000005`, FAR `0x78`. Exact code reads the NULL crypto-function table; it matches the host fault. See [diagnostic design and results](miami/xnu/PANIC-SCREEN.md).

The next source adaptation supplies the real portable legacy AES-CBC/ECB provider used by ios-sweet, backed by pinned BearSSL bitslice C. Tests using this XNU's real headers and legacy wrappers pass NIST known-answer vectors and API/error cases. Full compilation and the next hardware test are pending. This does not register the complete corecrypto table. See [AES integration and evidence](miami/xnu/AES.md).

- [Build instructions](miami/xnu/README.md)
- [Pthread matching, integration and results](miami/xnu/PTHREAD.md)
- [Bring-up details](miami/xnu/BRINGUP.md)
- [Automatic main workflow](.github/workflows/miami-xnu.yml)
- [Manual Intel workflow](.github/workflows/miami-xnu-intel.yml)

Both workflows use macOS 15 Intel, preinstalled Xcode 16.4 and DEVELOPMENT/ARM64/MIAMI. The fallback is manual only. Device dumps, calibration, downloaded Apple userland and local build output are excluded. Android is preserved; device tests use temporary fastboot boot images.

Latest diagnostic kernel: 15,905,352 bytes, SHA-256 `842b7d87c6c840bc14d98d42a7e3cf43aaf53321ee6fc26e1a8f1c33f15fe61b`, UUID `47A0388E-4A7B-3B9B-A5D4-96E5C55468B4`.

See [LICENSE](LICENSE) and original copyright notices.
