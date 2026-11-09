# MIAMI Next Concrete Engineering Steps

**Last Updated:** 2026-11-09

## 1. Completed in Current Session (2026-11-09)
1. **Option A (AMFI XML Entitlements, `CS_PLATFORM_BINARY`, and `CS_SIGNED` Support):**
   * Staged `0035-sweet-amfi-entitlements-platform-binaries.patch` and `0036-sweet-amfi-cs-signed.patch` (`SweetEntitlements.cpp`, `miami_amfi.c`, `bsd_init.c`) via `miami/xnu/ram_root.py` with fail-closed validation on malformed XML, hash mismatches, or DER-only entitlements and dual XML+DER support.
   * Embedded XML entitlements (`com.motorola.miami.pid1`, `com.apple.private.miami.test-bool`, `com.apple.private.miami.test-string`) into `miami-init.macho` (`miami/userspace/build.py`) and added EL0 `SYS_csops` (`169`) `CS_OPS_STATUS` + `CS_OPS_ENTITLEMENTS_BLOB` verification in `miami/userspace/init.S`.
   * Updated `miami/userspace/verify_codesign_pages.py` to verify all negative special slots (`-1..-5`) and verified with `check-codesign-pages.py` and `check-amfi.py`.
2. **Option B (Built-in Apple OSS HFS+ `hfs-627.100.6`, BearSSL MD5, and Multi-File HFS+ RAMDisk Root):**
   * Staged `0027-sweet-bearssl-md5.patch` and BearSSL MD5 (`miami/xnu/aes_component.py`) and verified with `miami/tests/check-md5.py`.
   * Created `miami/xnu/hfs_component.py` to stage `hfs-627.100.6` (`31d5ec238d`) and apply `0026`, `0029`, and `0031`; wired `--hfs` into `prepare.py`, `configure-helper.py`, `check-source.py`, and `.github/workflows/miami-xnu*.yml`.
   * Created `miami/userspace/mkhfs.py` to build and validate a deterministic 128-KiB HFS+ root image (`miami-root.hfs`) containing `/sbin/launchd`, `/etc/miami-root` (`MIAMI HFS+ ROOT OK\n`), and `/dev`.
   * Updated `miami/loader/plan.c` and `miami/loader/payload.py` to support both static Mach-O (`mockfs`) and bounded HFS+ (`H+`/`HX`) RAMDisks on `md0`, and verified in `miami/tests/check.py` and `miami/tests/check-source.py`.

## 2. Next Concrete Engineering Task: Build & Verify `MIAMI_XNU_0012` (HFS+ RAMDisk + XML AMFI)
1. **Authorize Git Checkpoint & Public CI Sync:**
   * Commit the verified Option A + Option B changes in `ios-miami` (`miami-bringup`) and sync the public CI branch (`main` at `https://github.com/muismanielmunesmilva-del/ios-miami`) when authorized.
2. **Trigger macOS Xcode 16.4 Kernel Build (`miami-xnu.yml`):**
   * Run `miami-xnu.yml` on `macos-15-intel` to compile `kernel.development.miami` with XML AMFI (`0035`–`0036`), built-in HFS+ (`0026`, `0029`, `0031`), and BearSSL MD5 (`0027`).
3. **Package & Verify `MIAMI_XNU_0012` in 150-Second QEMU Run:**
   * Package `kernel.development.miami` with `miami-root.hfs` (`131,072` bytes) into `outputs/miami-xnu-boot-0012/boot.img`.
   * Run the 150-second QEMU (`cortex-a55` `virt`) verification test to confirm:
     * `hfs_mountroot` mounts `md0` as `/` (`HFS+`).
     * `/sbin/launchd` (`PID=1`) executes with `CS_VALID | CS_ADHOC | CS_SIGNED | CS_PLATFORM_BINARY` (`0x24000003`) and retrieves its XML entitlements via `SYS_csops`.
     * `/etc/miami-root` is opened and read from the HFS+ root volume (`MIAMI HFS+ ROOT OK`).
     * Cross-thread `psynch_cvsignal` and 17 heartbeats complete without panic.
4. **Stage Multi-File `dyld` + `launchd` HFS+ RAMDisk Bring-Up:**
   * Build a multi-file HFS+ RAMDisk containing `/usr/lib/dyld` (`922,912` bytes from iOS 16.7.16) and a minimal dynamic Mach-O `/sbin/launchd` test binary to verify XNU `load_dylinker` + `dyld` entry before introducing `libSystem` / shared-cache slices.
