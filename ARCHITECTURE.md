# MIAMI System Architecture (`XT2245-1` / `SM6375`)

**Last Updated:** 2026-11-09

## 1. Boot Chain & Handoff (`miami/loader/`)
1. **ABL (Android Bootloader):** Loads Android boot v3 image (`boot.img`, 96 MiB container with AVB `NONE` footer) via `fastboot boot` into lower DRAM (`~0xa0080000`), passes live Flattened Device Tree (`fdt`) in `x0`, enters at `EL1` (`CurrentEL=4`) with MMU and caches off (`SCTLR_EL1=0xc00808`), and leaves the command-mode DSI splash pipe (`csot_nt37701_1080x2400_655_dsc_cmd_v1`) active in SDE autorefresh mode at `[0x85200000, 0x85e00000)`.
2. **MIAMI Loader (`miami/loader/main.c`, `plan.c`, `ram.c`):**
   * Validates `CurrentEL == EL1`, `SCTLR_EL1` caches/MMU off, and live FDT integrity (`libfdt`).
   * Verifies that the target XNU upper-RAM carve-out `[0x180000000, 0x1c0000000)` (`1 GiB`) lies completely inside a valid FDT `/memory` bank and does not intersect any `/reserved-memory` node, `memreserve`, dynamic `alloc-ranges`, loader `Image`, live `FDT`, or `initrd`.
   * Verifies SDE autorefresh on the active splash pipe and initializes the ramoops console (`0xaf03f800`) and framebuffer text console.
   * Validates the embedded `MIAMIXNU` payload (`miami/loader/payload.py` / `tools/mkpayload.py`), copies all pre-rebased XNU segments (and optional `RAMDisk` segment) to `[0x180000000, ...)`, performs byte-for-byte + zero-tail readback verification, writes the Apple Device Tree (`ADT`) and `boot_args` (version 2, 736 bytes), reads back `boot_args`, executes `dsb sy; ic iallu; dsb sy; isb`, and branches to `XNU_ENTRY_PA` with `x0 = boot_args_pa`.

## 2. XNU Kernel Adaptation (`miami/xnu/`)
* **Base Source:** Apple `xnu-8796.141.3` (`1b191cb58250d0705d8a51287127505aa4bc0789`), configured as `DEVELOPMENT` / `ARM64` / `MIAMI` (`MAX_CPUS=1`, 16K page granule).
* **Staging Pipeline (`miami/xnu/prepare.py`):**
  1. Applies the 18 foundational `ios-sweet` patches (`0001`–`0018`) transformed to `MIAMI` / `motorola,miami` / `SM6375`.
  2. Sets `MAX_CPUS=1`, matches `SweetCPU` (`IOCPU`) to `arm,cortex-a55`, backports `IORPC.kernelContent` for Xcode 16.4 `iig` compatibility, and installs 7 early assembly progress markers (`boot-marks.S.inc`).
  3. Overallocates 32 KiB for 16K-aligned bootstrap and final splash L3 page tables (`bootstrap-splash.S.inc`, `final-splash.c.inc`) mapping `[0x85200000, 0x85e00000)` as Normal-NC/XN.
  4. Stages the 18-row protected first-panic screen (`panic_screen.py` / `panic-screen.c.inc`).
  5. Stages Apple `libpthread-514.100.2` (`pthread_component.py`, `a6c70ca`) with 56-byte/8-aligned `ksyn_waitq_element` ABI.
  6. Stages `BearSSL` (`aes_component.py`, `7bea48e`) constant-time legacy AES-CBC behind `corecrypto_aes.c` and RFC 1321 MD5 (`0027`) behind `corecrypto_md5.c`.
  7. Stages Apple OSS HFS+ (`hfs_component.py`, `hfs-627.100.6` at `31d5ec238d`) into `bsd/miami_hfs` (`0026-sweet-builtin-hfs.patch`, `0029-sweet-unsealed-root-volume.patch`, `0031-sweet-read-write-root.patch`).
  8. Stages RAM-root (`ram_root.py`): patches `0021`–`0025` (`mockfs`, `IOKitBSDInit` RAMDisk without `IOMedia`, `ccsha256_ltc_di` for `libkern` SHA-256, 4K `memdev` vs 16K page fix, and built-in AMFI), calls `hfs_component.stage()`, and applies `0035` + `0036` (`SweetEntitlements.cpp` XML entitlement parser, `CS_PLATFORM_BINARY` + `CS_SIGNED` MAC policy, dual XML+DER support, fail-closed DER-only/malformed rejection).
* **Apple Device Tree (`miami/xnu/mkadt.py`):**
  * `/chosen`: `dram-base = 0x180000000`, `dram-size = 0x3ff00000`, `memory-map/RAMDisk = <pa, size>`.
  * `/cpus/cpu0`: `compatible = "arm,cortex-a55\0ARM,v8"`, `timebase-frequency = 19200000`.
  * `/arm-io`: `ranges = <0x0 0x01000000 0xff000000>`, child `/arm-io/gic` (`0x0f200000`, `0x0f240000`, `virtual-timer-intid = 19`).
  * `/miami-fbcon`: runtime-patched framebuffer address, `1080x2400`, stride.
  * `/pram`: `0x1bff00000` (`0x100000` bytes).
