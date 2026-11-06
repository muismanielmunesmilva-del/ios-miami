# ios-miami

Initial single-CPU XNU adaptation for the Motorola Edge 30 Neo XT2245-1 (SM6375), inspired by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

Probe V5 confirmed 16K MMU translation and timer interrupts on the boot CPU. The complete XNU kernel has not yet been built in CI or booted on miami. There is no working iOS installation here yet.

- [Build and GitHub Actions instructions](miami/xnu/README.md)
- [Adaptation, local verification and limitations](miami/xnu/BRINGUP.md)
- [Manual build workflow](.github/workflows/miami-xnu.yml)

The workflow first validates source, loader bounds and console mappings on Linux, then builds DEVELOPMENT/ARM64/MIAMI with macOS 15 and Xcode 16.4. No device connection, flashing, storage installation, downloaded Apple userland or calibration dumps are included.

The selected upper-RAM bank has been checked against the live FDT; its physical accessibility is still untested. Review a complete kernel build and image identity before a first temporary phone test.

See [LICENSE](LICENSE) and the original source copyright notices.
