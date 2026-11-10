# MIAMI Current Technical Blockers

**Last Updated:** 2026-11-09

## 1. Kernel AMFI & Entitlement Admission Blocker (RESOLVED & QEMU-VERIFIED in `MIAMI_XNU_0012`)
* **Observation:** Real iOS 16.7.16 `sbin/launchd` (`12370e5ee3...`, 541,600 bytes) carries an ad-hoc `CodeDirectory` (`flags=0x2`), an XML entitlements slot (`slot 5`, magic `0xfade7171`, 1,677 bytes), and a DER entitlements slot (`slot 7`, magic `0xfade7172`, 1,105 bytes).
* **Resolution Verified:** Compiled in GitHub Actions Run `42695357398` (`c6ae04e343fcad26caf4e6be8f5a8e1a4551cdbe`) and verified in 150-second QEMU run (`MIAMI_XNU_0012`): `SweetEntitlements.cpp` + `miami_amfi.c` parse XML entitlements into `OSDictionary`, mark rootfs binaries `CS_PLATFORM_BINARY | CS_SIGNED`, and pass EL0 `SYS_csops` (`CS_OPS_STATUS` and `CS_OPS_ENTITLEMENTS_BLOB`).

## 2. Root Filesystem (`mockfs` vs. HFS+) & Loader 64 KiB Cap Blocker (RESOLVED & QEMU-VERIFIED in `MIAMI_XNU_0012`)
* **Observation:** `mockfs` wraps only a single flat Mach-O in `md0` as `/sbin/launchd`, and `miami/loader/plan.c` previously enforced `s->file_size <= 0x10000` (64 KiB) with a Mach-O header check.
* **Resolution Verified:** Compiled Apple OSS `hfs-627.100.6` (`31d5ec238d`) and BearSSL MD5 into `kernel.development.miami` (`d60d968a...`), built a deterministic 128-KiB HFS+ root volume (`miami-root.hfs`) containing `/sbin/launchd`, `/etc/miami-root`, and `/dev`, and verified in 150-second QEMU run (`hfs: mounted MiamiRoot on device b(1, 0)` and `MIAMI HFS+: /etc/miami-root verified`).

## 3. Dynamic Linker (`dyld`) Handoff & Sandbox/Crypto/HFS+ Userspace Kernel Support (RESOLVED & QEMU-VERIFIED in `MIAMI_XNU_0013`)
* **Observation:**
  1. Real iOS 16.7.16 `sbin/launchd` uses `/usr/lib/dyld` (`LC_LOAD_DYLINKER`) and issues `SYS___mac_syscall("Sandbox", ...)` and requests `PRIV_WORK_INTERVAL`.
  2. Userspace and crypto libraries in XNU require BearSSL SHA-1 (`0032`), BearSSL SHA-384 & SHA-512 (`0033`), HFS+ link notes (`0041`), HFS+ `VFS_RENAME_SWAP` (`0052`), `bindfs` (`0037`), `AppleKeyStore` (`0038`, `0055`), `do_coredump = 0` (`0039`), exec short logging (`0042`), console crash logging (`0043`, `0044`), permissive `"Sandbox"` MAC policy (`0050`), and `PRIV_WORK_INTERVAL` (`0064`).
* **Resolution Verified:**
  1. Integrated all above patches and BearSSL source files into `miami/xnu/` and compiled in macOS Xcode 16.4 Actions Run `42709183824` (`9b978f02931a7b45f44daaa2cffdb01fc6ad55c5`).
  2. Packaged `/usr/lib/dyld` (`MH_DYLINKER`) in `miami-root.hfs`, mapped by XNU `load_dylinker()`, which executes at EL0, verifies the main binary Mach-O header pointer passed on the stack by `exec_mach_imgact()`, sets `x28 = 0x44594c44` (`"DYLD"`), and transfers control to `/sbin/launchd`.
  3. Verified in 150-second QEMU run (`MIAMI_XNU_0013`): `MIAMI Sandbox: launchd op 0`, `MIAMI Sandbox: launchd op 4`, `MIAMI AMFI: platform binary, XML entitlements and Sandbox verified`, `MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified`, 23 heartbeats, 93 EL0 SVC calls across 20 call sites (`check-pid1-runtime.py` exit code 0).

## 4. Current Active Blocker: Full Dynamic Userland Dependencies & Shared Cache Mapping
* **Observation:**
  1. Full stock iOS 16.7.16 `sbin/launchd` links against `/usr/lib/libSystem.B.dylib` and `/usr/lib/libobjc.A.dylib`, which reside in the dyld shared cache (`dyld_shared_cache_arm64*`, ~3.33 GB total).
  2. The phone has 128 GB UFS storage, but Android `userdata` and system partitions must never be erased or corrupted without explicit authorization.
  3. `ios-sweet` implements UFS read/write and shared-cache mapping via patches `0028`, `0030`, `0034`, `0046`, `0069`.
* **Required Resolution:**
  1. ~~Test physical device temporary boot of `MIAMI_XNU_0013` (`fastboot boot outputs\miami-xnu-boot-0013\boot.img`)~~ -> **CONFIRMED PASS on physical Motorola Edge 30 Neo `XT2245-1`**: User observed on-screen display of `MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified`, `MIAMI AMFI: platform binary, XML entitlements and Sandbox verified`, `MIAMI PSYNCH: cvwait timed out as expected`, `MIAMI THREADS: waiting thread signaled successfully`, and repeating heartbeats.
  2. Implement Option B (`MIAMI_XNU_0014`): UFS controller driver (`miami_ufs.c` / Qualcomm UFSHCI 2.1 at `0x04804000`) for read-only access to isolated disk images without touching Android partitions.
