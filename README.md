# ios-miami

Initial single-CPU XNU adaptation for the Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

Probe V5 confirmed 16K MMU translation and timer interrupts on the boot CPU. The complete XNU kernel now compiles, links and passes payload validation in [Actions run #3](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42165337842), source commit `1574a19bf2b95dc2563a1a3d89a81ff99e77b223`. The downloaded artifact's hashes, arm64 identity and embedded MIAMI ADT were independently verified. XNU has not been booted on miami; there is no working iOS installation here yet.

- [Build and GitHub Actions instructions](miami/xnu/README.md)
- [Adaptation, verification and limitations](miami/xnu/BRINGUP.md)
- [Build workflow](.github/workflows/miami-xnu.yml)

The workflow validates source, loader bounds and console mappings on Linux, then builds DEVELOPMENT/ARM64/MIAMI with macOS 15 and Xcode 16.4. It runs on target-code pushes to main and supports manual dispatch. Python 3.9 source writing and file-only __CTF packaging errors were corrected with regression checks. No device connection, flashing, storage installation, downloaded Apple userland or calibration dumps are included.

Verified kernel: 15,883,864 bytes, SHA-256 `68f974e4e99fe2c0987a5f5529996322ff59f25b02cc723cb57854839560a219`.

The selected upper-RAM bank has been checked against the live FDT; its physical accessibility is still untested. A real-kernel Android boot.img must be packaged and reviewed locally before a first temporary phone test.

See [LICENSE](LICENSE) and the original source copyright notices.
