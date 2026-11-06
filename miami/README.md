# miami bring-up: Motorola Edge 30 Neo XT2245-1

This directory is the local start of an iOS 16 port based on ios-sweet.
Probe 0005 completed with working 16K MMU translation, private-page alias data
checks and nine timer IRQs with MMU/caches on, confirmed by the user's photograph.
There is no working XNU boot or iOS image for miami here yet. The original
repository's README describes **sweet**, not this device. Historical approvals
recorded for the original sweet phone do not authorize erasing this phone.

## Verified preparation (2026-11-05)

The connected phone reports SM6375 / holi, Android 14 build
U1SSMS34.31-64-4-19, security patch 2025-09-01, unlocked bootloader, slot A.
The stock boot, vendor_boot and dtbo files supplied by the user match the
active-slot partition copies byte-for-byte. Both boot formats are v3.

Temporary TWRP 3.7.1_12-0, obtained from the Motorola-Miami maintainers' release,
provided root ADB and the live FDT. Twenty calibration and boot partition
copies (779,485,184 bytes total) passed size and SHA-256 comparison against
the phone. This is not a userdata or complete-device backup. Private dumps,
calibration and stock firmware are outside this repository.

Measured live FDT facts:

* GICD: 0x0f200000 / 0x10000; GICR: 0x0f240000 / 0x100000.
* Architectural timer: 19,200,000 Hz; virtual timer PPI 3, INTID 19.
* MPIDRs: 0x000 through 0x700 in increments of 0x100; PSCI through SMC.
* RAM banks: [0x80000000, 0xbbb00000), [0xc0000000, 0x180000000),
  [0x180000000, 0x280000000). Reserved regions must still be excluded.
* UFS host: 0x04804000; USB wrapper: 0x04e00000.
* Touch: Goodix GT9916S, SPI engine 0 at 0x04a80000.
* Selected panel identifier: csot_nt37701_1080x2400_655_dsc_cmd_v1.
  The numeric suffix is an identifier, not a measured screen diagonal.
* Ramoops region: 0xaf000000 / 0xbf800. Recovery /proc/iomem confirms
  dmesg [0xaf000000, 0xaf03f800), console [0xaf03f800, 0xaf07f800),
  and pmsg [0xaf07f800, 0xaf0bf800). ECC is disabled.

Photo-confirmed boot CPU: CurrentEL=4 (EL1), SCTLR=0xc00808 (MMU and caches
off), FDT_LAYOUT_RESULT=0, MIDR=0x412fd050 (Cortex-A55 r2p0),
ID_AA64MMFR0_EL1=0x101122 (16K granule reported supported, 40-bit physical
addresses, 16-bit ASIDs), CNTFRQ=19200000, PSCI_VERSION=0x10000 (1.0).
Probe 0005 additionally confirms counter advance and virtual-timer IRQ delivery
with MMU/caches on and working 16K mappings on this CPU. Secondary-core features
and general RAM accessibility remain untested.

The static firmware's memory/reg is all zeros; its default panel differs from
the selected live panel. Do not derive a bootable configuration from it alone.

## CPU probe

The probe is a separate, small AArch64 Linux-ABI Image, packaged as boot v3.
It does not load XNU. It records CPU registers in the reserved ramoops console.
It has no storage or filesystem driver. V2 adds an entry
delay using the physical counter, cache-line cleaning and a diagnostic record
before runtime FDT validation. V3 removes the early timer wait, reuses ABL's
linear 32-bit splash buffer, and mirrors the log as visible text. It sets
command-mode autorefresh when tear checking is enabled; manual CTL_START is
only used when autorefresh is off and INTF1 is active. V3 remains on screen
until manually reset. A failed early exception currently halts in its
vector, so recovering the device can require the hardware bootloader keys.

This overwrites volatile diagnostic console history in reserved RAM. Temporary
boot is not a guarantee that arbitrary code cannot affect persistent state.
The tested TWRP automatically mounts data and metadata; no flash, erase, format,
slot-change or bootloader-lock operation was issued during preparation.

Dependencies: Linux, gcc, aarch64-linux-gnu-gcc/binutils, mkbootimg, Python 3,
the upstream dtc checkout pinned to 54e547173bf0f2a4cc35eba8b5738caf38b9230f,
and AOSP avbtool.py. Only libfdt's read-only source files are linked.

```sh
bash miami/probe/build.sh /path/to/dtc /private/path/live-recovery.dtb /path/to/avbtool.py
```

The build validates the actual FDT with the same layout guards used by the
probe. The incomplete stock FDT must be rejected (-4). Compiler warnings are
errors; C object absolute pointers are rejected; the final ELF is static.
The AVB container uses algorithm NONE, as the maintainers' TWRP does, and its
embedded image hash is checked with avbtool. This does not give it an OEM
signature or make it suitable for a locked bootloader.

Only after selecting and verifying the miami bootloader should the experimental
image be started with `fastboot boot miami/probe/out/avb/boot.img`. Do not flash
this diagnostic image. Boot temporary TWRP directly after a probe to retrieve
the old console from /sys/fs/pstore; an intervening Android boot can consume
or replace the previous log.

## Current results and next work

* Probe 0001, raw 57,344-byte boot image, SHA-256
  8acd85b70057f84493d271e9ce7ace777480c04466c9da6c73688845bdb13782:
  fastboot send/boot OKAY; phone returned to Android; no execution log recovered.
* Probe 0001 with AVB footer, same code: send/boot OKAY; returned to Android.
  Adding a footer did not establish execution.
* Probe 0002, raw SHA-256
  cabac4a525e0fc6d4b3ebea41f44d40920d9eba829e238dd3cac9780fdf6c11d;
  padded AVB image SHA-256
  8d56c3bdec9afd38d834887936f1717114a71959a2c9dc95692ee1139fec2509:
  send/boot OKAY; no USB device during a 45-second observation window;
  user then returned the device to the bootloader with the buttons.
  Direct temporary TWRP subsequently recovered no pstore entries.
* Probe 0003, raw SHA-256
  b982c2700f6b97317939885b8ca36ff29cc67547eae2397493d0f8716e3464ac;
  padded AVB image SHA-256
  f358b09fd3fb603e90c23e23e7af3a5d89dda592f7eb70989658d74ffcb115f4:
  send/boot OKAY; the user confirmed white text/bands on a black background.
  This establishes custom code execution and basic framebuffer output.
  The subsequent photograph shows FDT validation success, all CPU register
  lines, and the final complete marker; the boot-CPU values are recorded above.
* Probe 0004 adds exception diagnostics and a single-CPU GICv3 virtual-timer
  test. The AVB image SHA-256 is
  09b84cb1cb277f281d88c8b3b382a7d525a3047778a04ba0dce0bc5df76157f3.
  The photograph confirms completion, counter delta 0x9e5, nine timer IRQs,
  zero other IRQs, last INTID 19 and GIC_TEST_RESULT=0. IMAGE_BASE=0xa00b0000.
* Probe 0005 adds sparse 16K page tables, enabling MMU and caches. It maps
  the loaded Image, measured display/GIC/log regions and one private scratch
  page alias. It checks both ends of the alias, an unmapped guard page,
  bidirectional data access and timer IRQs with MMU on. It writes no external
  RAM or partitions. The AVB image SHA-256 is
  0451f26a59cc4fef949a892155e3b1cf38e524439dbd0f0657eb3727617de0ca.
  Native independent table-walk invariants pass at four placements; build,
  FDT, header, vector/storage alignment, relocation and AVB checks pass.
  Temporary fastboot boot: send OKAY (2.673 s), boot OKAY (10.474 s).
  The user's photograph confirms MMU_TEST_RESULT=0, MMU_ALIAS_DATA_OK=1,
  PAR_ALIAS_GUARD=0x80f (translation fault), GIC_AFTER_MMU_RESULT=0,
  nine timer IRQ19 events and zero other IRQs. SCTLR=0xc0180d enables M/C/I.
  Image [0xa0080000,0xa00c0000); scratch=0xa0088000; alias=0xf00000000.
  Full transcription and photo hash: probe/results/0005.json.

An OKAY response establishes image acceptance only; the visible probe output
is the independent execution observation. Actual 16K mappings now pass on the
boot CPU. Ramoops recovery, upper RAM and secondary CPUs remain unproven.
The initial single-CPU XNU source/loader/ADT adaptation passed the complete
macOS build and payload validation in [Actions run #3](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42165337842),
source commit `1574a19bf2b95dc2563a1a3d89a81ff99e77b223`.
Downloaded kernel/payload/ADT checksums and identities were independently
verified; see xnu/README.md and xnu/BRINGUP.md. The first XNU boot remains pending.
UFS, SPI touch, SMP and
display services for iOS remain to be ported. The original SWEET
kernel's hard-coded display addresses and peripheral drivers are not ported.

## Primary references

* [HackiOSX porting stages](https://hackiosx.dev/porting)
* [Motorola-Miami temporary TWRP guide](https://motorola-miami.github.io/downloads/guide/miami/)
* [Maintainers' TWRP release](https://github.com/Motorola-Miami/miami_releases/releases/tag/%232)
* [AOSP boot unpacker](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/main/unpack_bootimg.py)
* [AOSP AVB documentation](https://android.googlesource.com/platform/external/avb/+/refs/heads/main/README.md)
* [AArch64 boot ABI](https://docs.kernel.org/arch/arm64/booting.html)
* [libfdt](https://github.com/dgibson/dtc/tree/54e547173bf0f2a4cc35eba8b5738caf38b9230f/libfdt)
* [Motorola ramoops layout](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/MMI-T1SSMS33.1-121-4-8/fs/pstore/ram.c)
* [Motorola display register definitions](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/MMI-T1SSMS33.1-121-4-8/msm/sde/sde_hw_sspp.c)
* [Pixel 4 command-mode bring-up](https://github.com/NWylynko/ios-flame/blob/745c4341af86089efb0df851fa8a27fb8face624/shim/sde.c)
* [Arm Cortex-A55 reference manual](https://documentation-service.arm.com/static/5e7e09f6a3736a0d2e862d2f)
* [Arm PSCI specification](https://documentation-service.arm.com/static/640f584656ea36189d4e94a4)
* [Arm memory-management guide](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/LearnTheArchitecture-MemoryManagement-101811_0100_00_en.pdf?revision=01a01804-ca64-4e19-a55e-2af56afea5a5)
* [Linux v5.4 translation-table definitions](https://github.com/torvalds/linux/blob/v5.4/arch/arm64/include/asm/pgtable-hwdef.h)
