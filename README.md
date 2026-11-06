# ios-miami

Single-CPU XNU bring-up for Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

The latest verified kernel passed [Actions run 42202366971, attempt 2](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42202366971), source commit `a98a0f89afc60886943faf9436ef313ccc360525`. Artifact identity, ARM64 target, embedded ADT and linked table alignment were independently checked.

On the phone, image 0004's photograph confirms XNU console execution, platform expert registration and VM bootstrap completion. On image 0005 the user reports the CPU registration/SGI1 message; a subsequent photograph shows a panic backtrace through pthread_init and bsd_init. The exact panic header is outside the photo. Exact-kernel callsite symbolication identifies the missing pthread function-table guard. A complete kernel boot and iOS userland remain unconfirmed.

This source integrates Apple's matching libpthread-514.100.2 kernel implementation at commit `a6c70ca0e544347a0377babf748f831577ec24f9`, retaining real initialization, synchronization and panic guards. Fresh staging and local API checks passed within the documented limits; the full Apple-compiler build and runtime result for this integration are pending.

- [Build instructions](miami/xnu/README.md)
- [Pthread source matching, integration and verification](miami/xnu/PTHREAD.md)
- [Bring-up results and diagnostic-stage map](miami/xnu/BRINGUP.md)
- [Automatic main workflow](.github/workflows/miami-xnu.yml)
- [Manual Intel workflow](.github/workflows/miami-xnu-intel.yml)

Both workflows use macOS 15 Intel, preinstalled Xcode 16.4 and DEVELOPMENT/ARM64/MIAMI. The fallback is manual only. Device dumps, calibration, downloaded Apple userland and local build output are excluded. Android is preserved; device testing uses temporary fastboot boot images.

Latest verified kernel: 15,883,920 bytes, SHA-256 `1eccaf12b8dec4a9e61d6940b730efc5a5d2d6a52637451cbd45114d1af99107`.

See [LICENSE](LICENSE) and original copyright notices.
