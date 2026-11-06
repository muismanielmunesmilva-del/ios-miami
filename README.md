# ios-miami

Initial single-CPU XNU adaptation for Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

The latest diagnostic kernel compiles, links and passes payload validation in [Intel-hosted Actions run 42198284206](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42198284206), source commit `cdd0f604e5fe08b7e9e7e2a57539a0ec2ff37f2c`. Artifact hashes, target identity, embedded ADT and linked table storage were independently checked. QEMU reaches console initialization, then panics on target GIC MMIO not represented by virt; this is not a complete boot or hardware result.

On the phone, probe V5 confirmed 16K translation and timer interrupts. Temporary XNU images 0002/0003 reached the loader's pre-branch message after ten segment-copy markers. The image 0004 photograph now confirms XNU console execution, platform expert registration and VM bootstrap completion on the phone. The user reports a stationary screen without panic; a complete kernel boot and iOS userland remain unconfirmed. The next change corrects an inherited CPU-driver/ADT match mismatch using the measured Cortex-A55 compatible and enables startup_debug=1 logs.

- [Build instructions](miami/xnu/README.md)
- [Adaptation, results and diagnostic-stage map](miami/xnu/BRINGUP.md)
- [Standard workflow](.github/workflows/miami-xnu.yml)
- [Intel fallback workflow](.github/workflows/miami-xnu-intel.yml)

Both workflows now use macOS 15 Intel, verified preinstalled Xcode 16.4 and DEVELOPMENT/ARM64/MIAMI. The Intel fallback builds on its own workflow updates or manual dispatch. Device dumps, calibration, downloaded Apple userland and local build output are excluded. Android is preserved; testing uses temporary fastboot boot images.

Latest kernel: 15,883,920 bytes, SHA-256 `a05028b955f6bb64d1b2e2e535c6e82706af311ff0d53150dfb1d72a3a6fa354`.

See [LICENSE](LICENSE) and the original copyright notices.
