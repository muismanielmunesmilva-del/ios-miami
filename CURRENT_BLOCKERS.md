# MIAMI Current Technical Blockers

**Last Updated:** 2026-11-09

## 1. Kernel AMFI & Entitlement Admission Blocker (Resolved Locally — Pending CI XNU Build `0012`)
* **Observation:** Real iOS 16.7.16 `sbin/launchd` (`12370e5ee3...`, 541,600 bytes) carries an ad-hoc `CodeDirectory` (`flags=0x2`), an XML entitlements slot (`slot 5`, magic `0xfade7171`, 1,677 bytes), and a DER entitlements slot (`slot 7`, magic `0xfade7172`, 1,105 bytes).
* **Resolution Implemented & Host-Verified:** Staged `0035-sweet-amfi-entitlements-platform-binaries.patch` and `0036-sweet-amfi-cs-signed.patch` (`SweetEntitlements.cpp` + MAC policy in `bsd/kern/miami_amfi.c` + `bsd/kern/bsd_init.c`) via `miami/xnu/ram_root.py`. Hardened `miami_amfi_attach_entitlements` and `miami_amfi_adjust_without_monitor` to parse XML entitlements (`OSUnserializeXML`), mark rootfs binaries with `CS_SIGNED | CS_PLATFORM_BINARY`, allow dual XML+DER blobs, and fail closed on DER-only or malformed XML blobs. Verified in `miami/tests/check-amfi.py` and `miami/tests/check-source.py`.

## 2. Root Filesystem (`mockfs` vs. HFS+) & Loader 64 KiB Cap Blocker (Resolved Locally — Pending CI XNU Build `0012`)
* **Observation:** `mockfs` wraps only a single flat Mach-O in `md0` as `/sbin/launchd`, and `miami/loader/plan.c` previously enforced `s->file_size <= 0x10000` (64 KiB) with a Mach-O header check.
* **Resolution Implemented & Host-Verified:**
  1. Staged Apple OSS `hfs-627.100.6` (`31d5ec238dfab485e78a9a30b8b92d13e8914f03`) via `miami/xnu/hfs_component.py` (`0026-sweet-builtin-hfs.patch`, `0029-sweet-unsealed-root-volume.patch`, `0031-sweet-read-write-root.patch`) and BearSSL MD5 (`0027-sweet-bearssl-md5.patch`) via `miami/xnu/aes_component.py`.
  2. Added `miami/userspace/mkhfs.py` to build and validate a deterministic 128-KiB HFS+ root image (`miami-root.hfs`) containing `/sbin/launchd`, `/etc/miami-root`, and `/dev`.
  3. Updated `miami/loader/plan.c` and `miami/loader/payload.py` to validate both static 64-KiB Mach-O (`mockfs`) and bounded HFS+ (`H+` / `HX`, up to 64 MiB) RAMDisk images. Verified in `miami/tests/check.py` and `miami/tests/check-source.py`.

## 3. Next Blocker: macOS Xcode 16.4 Kernel Build (`0012`) & Dynamic Linker (`dyld`) Shared Cache
* **Observation:**
  1. Compiling the newly staged XNU kernel (`MIAMI_XNU_0012` with XML AMFI + HFS+ + BearSSL MD5) requires triggering `.github/workflows/miami-xnu.yml` on the macOS 15 Intel runner (`macos-15-intel` with Xcode 16.4) after authorized push to the public CI repository.
  2. Real iOS 16.7.16 `sbin/launchd` uses `/usr/lib/dyld` (`LC_LOAD_DYLINKER`) and links against `/usr/lib/libSystem.B.dylib` and `/usr/lib/libobjc.A.dylib`, which reside in `SystemOS` `dyld_shared_cache_arm64*` (44 files, 3.33 GB total). Android `userdata` on UFS must not be overwritten.
* **Required Resolution:** After compiling and verifying `MIAMI_XNU_0012` on an HFS+ RAMDisk in QEMU (`miami-root.hfs`), construct a minimal/sliced read-only shared cache or multi-file `/usr/lib/dyld` test HFS+ RAMDisk within MIAMI's upper RAM.
