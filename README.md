# ios-miami

Single-CPU XNU bring-up for Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

The pthread integration passed every gate in [Actions run 42239849041](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42239849041), source commit `51c1948587595f336115c65f0abe5f8c2dc07862`. Apple's matching libpthread-514.100.2 is pinned to `a6c70ca0e544347a0377babf748f831577ec24f9`. The real implementation and panic guards are retained. ZIP/kernel identity, actual Mach-O implementation symbols, embedded ADT and linked table alignment passed independent checks.

The host-only virtual GIC/timer control shows pthread callback registration and CPU/SGI1 completion. After XNU's 30-second RTC-service wait, its later domaininit/tcp_init backtrace establishes return from pthread_init by source call ordering; the completion line was overwritten. The control then aborts in aes_encrypt_key128+0x10 (ESR 0x96000005, FAR 0x78). The crypto provider is the next dependency to investigate. This is not a full boot or a phone result.

On the phone, image 0004's photograph confirms XNU console, platform expert and VM bootstrap progress. Image 0005's user report confirms CPU/SGI1 progress, followed by a photograph whose backtrace identifies the previous missing pthread-table guard; the panic header is outside the photo. Image 0006 was accepted by temporary fastboot boot; its photograph confirms XNU panic output with the exact verified kernel UUID. The reason, exception registers and backtrace are absent, so its cause and phone pthread completion remain unproven. iOS userland has not started.

The next diagnostic preserves the first panic reason and valid saved exception registers in 18 protected framebuffer rows. Host pixel/console regression tests and isolated Darwin arm64 compilation pass; its full Actions build and physical test are pending. See [diagnostic design and checks](miami/xnu/PANIC-SCREEN.md).

- [Build instructions](miami/xnu/README.md)
- [Pthread matching, integration and results](miami/xnu/PTHREAD.md)
- [Bring-up details](miami/xnu/BRINGUP.md)
- [Automatic main workflow](.github/workflows/miami-xnu.yml)
- [Manual Intel workflow](.github/workflows/miami-xnu-intel.yml)

Both workflows use macOS 15 Intel, preinstalled Xcode 16.4 and DEVELOPMENT/ARM64/MIAMI. The fallback is manual only. Device dumps, calibration, downloaded Apple userland and local build output are excluded. Android is preserved; device tests use temporary fastboot boot images.

Latest kernel: 15,904,816 bytes, SHA-256 `ed5206231af5a6f9d46f2f690b99b9fea6ccecc905e2ca5801e5f35533b30b8b`.

See [LICENSE](LICENSE) and original copyright notices.
