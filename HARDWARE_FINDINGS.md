# MIAMI Hardware Findings (`Motorola Edge 30 Neo` / `XT2245-1`)

**Last Updated:** 2026-11-09

## 1. Verified Device & Firmware Identity
* **Device:** Motorola Edge 30 Neo (`miami`, Model `XT2245-1`, Brazil `RETBR`)
* **SoC:** Qualcomm Snapdragon 695 (`SM6375` / `holi`), Adreno 619 GPU
* **Active Stock Firmware:** Android 14 `U1SSMS34.31-64-4-19` (security patch `2025-09-01`), slot A, unlocked bootloader.
* **Boot Container Requirements:** Android boot image header v3 (`1580` bytes), page size `4096`, `ramdisk_size > 0` (dummy gzipped ramdisk accepted), wrapped in a 96-MiB (`100,663,296` bytes) AVB container (`avbtool add_hash_footer --algorithm NONE`).

## 2. Verified CPU & Exception Level (Photo-Confirmed via Probes `0003`–`0005`)
* **Boot Entry State:** `CurrentEL = 0x4` (`EL1`), `SCTLR_EL1 = 0xc00808` (MMU, D-cache, I-cache off).
* **Boot CPU Identity:** `MPIDR_EL1 = 0x81000000` (CPU 0), `MIDR_EL1 = 0x412fd050` (ARM Cortex-A55 r2p0).
* **MMU Capabilities:** `ID_AA64MMFR0_EL1 = 0x101122` (`TGran16 = 1` confirming hardware 16 KiB granule support, `PARange = 2` / 40-bit PA, `ASIDBits = 2` / 16-bit ASID).
* **16K MMU & Cache Enablement:** Confirmed working on hardware in Probe `0005` (`SCTLR_EL1 = 0xc0180d`, `TCR_EL1 = 0x2409cb51c`) and XNU Images `0004`–`0011`.
* **PSCI & SMP Topology (FDT-Verified):** `PSCI_VERSION = 0x10000` (v1.0, `smc` conduit); 8 CPUs in FDT with `MPIDR` `0x000`..`0x700` in steps of `0x100` (6x Cortex-A55 + 2x Cortex-A78 performance cores; secondary cores currently kept offline with `MAX_CPUS=1`).

## 3. Verified Memory Map & Reserved Regions (Live Recovery FDT & `/proc/iomem`)
* **DRAM Banks (Live FDT `/memory`):**
  1. `[0x80000000, 0xbbb00000)` (~955 MiB, contains numerous firmware/modem/splash reservations and dynamic `alloc-ranges` in `[0x80000000, 0xc0000000)`).
  2. `[0xc0000000, 0x180000000)` (3 GiB).
  3. `[0x180000000, 0x280000000)` (4 GiB; `[0x180000000, 0x1c0000000)` is verified free of FDT reservations and used for XNU DRAM + panic region).
* **Note on Static Firmware DTB:** Stock `miami.dts` has `memory { reg = <0 0 0 0>; }` (populated dynamically by ABL at boot) and must never be used standalone.
* **Ramoops / Pstore Region:** `0xaf000000` size `0xbf800` (`dmesg` `[0xaf000000, 0xaf03f800)`, `console` `[0xaf03f800, 0xaf07f800)`, `pmsg` `[0xaf07f800, 0xaf0bf800)`). Note: rebooting via hardware buttons or booting Android clears/consumes volatile RAM before TWRP can inspect `/sys/fs/pstore`.

## 4. Verified Interrupts, Timers, Display & Peripherals
* **GICv3:** `GICD = 0x0f200000` (size `0x10000`), `GICR = 0x0f240000` (size `0x100000`).
* **Architectural Timer:** `CNTFRQ_EL0 = 19,200,000` Hz (19.2 MHz); virtual timer PPI 3 (`INTID 19`), verified delivering interrupts in Probe `0004`, Probe `0005`, and XNU (`0004`–`0011`).
* **Display / Framebuffer:** Panel `csot_nt37701_1080x2400_655_dsc_cmd_v1` (1080x2400, 32 bpp, command mode). ABL leaves SDE `SSPP_SRC0_ADDR` active inside `[0x85200000, 0x85e00000)` with tear-check / autorefresh enabled (`PINGPONG_0_AUTOREFRESH_CONFIG`), allowing XNU to render text by writing to Normal-NC mapped splash pages without touching DSI/clock registers.
* **Unported Peripherals (FDT Addresses Measured Only):**
  * UFS Host Controller: `0x04804000`
  * USB DWC3 Wrapper: `0x04e00000` (`dr_mode = "otg"`)
  * Touch Controller: Goodix `GT9916S` on GENI SPI0 at `0x04a80000`
