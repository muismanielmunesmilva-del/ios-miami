# MIAMI Project State — Experimental iOS 16 Port for Motorola Edge 30 Neo (`XT2245-1`)

**Last Updated:** 2026-11-09
**Authoritative Repository:** `C:\Users\twix\Documents\Codex\2026-11-05\ol\work\ios-miami`
**Branch:** `miami-bringup`
**Public CI Repository:** `https://github.com/muismanielmunesmilva-del/ios-miami`

## 1. Current Verified State
* **Boot Chain & Loader (`0005`):** AArch64 Linux-ABI `Image` packaged in a 96-MiB Android boot v3 + AVB (`NONE`) container for `fastboot boot`. Validates live FDT, reserved memory, upper RAM (`[0x180000000, 0x1bff00000)` + 1 MiB panic log at `0x1bff00000`), SDE autorefresh splash framebuffer (`[0x85200000, 0x85e00000)`), and copies/reads back XNU segments, ADT, and `boot_args` before branching with MMU off at EL1.
* **XNU Kernel (`xnu-8796.141.3`, iOS 16 / macOS 13.5):**
  * Single-CPU (`MAX_CPUS=1`), `arm,cortex-a55` IOCPU matching (`MIDR=0x412fd050`), GICv3 (`GICD=0x0f200000`, `GICR=0x0f240000`), architectural virtual timer `INTID 19` @ 19.2 MHz.
  * 16K page tables (`TGran16=1`), Normal-NC/XN early and final splash framebuffer mappings (`768` 16K pages), 18-row protected first-panic screen.
  * Integrated Apple `libpthread-514.100.2` (`a6c70ca`) with 56-byte / 8-byte-aligned `ksyn_waitq_element` ABI.
  * Integrated `BearSSL` (`7bea48e`) constant-time legacy AES-CBC provider (`g_crypto_funcs` fallback) and built-in XNU `ccsha256_ltc_di` SHA-256 wrapper.
  * Integrated `mockfs` + `devfs` RAMDisk root (`rd=md0`) and built-in AMFI interface (`miami_amfi.c`).
* **Latest Verified Delivery (`MIAMI_XNU_0011`):**
  * Actions Run: `42349700687` (`215a2eeed0320f00938617762b3b9d44ada02a88`), also re-verified at `823adf1075` (Run `42409278880`).
  * `boot.img` SHA-256: `7bf23e1c6c4a3f2134309ada6cdb5cc52cbdd5d9e6c4bbe071ec90401bb2670a` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `9acdf2a6342cac42b999b7e5013bf381e3ae896bc089007ee42c00d5f8570e9f` (`15,925,816` bytes, `LC_UUID`: `31FFE095-E332-3661-BAD1-20CCFC297A6D`).
  * QEMU 150s result: `PASS` (`PID=1`, `psynch_cvwait` timeout `0x13c`, cross-thread `bsdthread_create` + `psynch_cvsignal` waking actual waiter with `PTHRW_INC`, 17 heartbeats, 66 EL0 SVCs).
  * Hardware result: Temporary `fastboot boot` accepted; user reported cross-thread signal success and heartbeats on phone (no photo). Zero partition writes ever issued.
* **Real iOS 16.7.16 (`20H392`, `iPhone10,3`/`iPhone10,6`) Inspection State:**
  * Pinned `BuildManifest.plist` (`2d145210...`) and DMGs (`087-86698-044.dmg` OS, `087-86593-047.dmg` SystemOS, `087-86715-047.dmg` AppOS) verified via SHA-384 and CRC-32 in `ol\work\miami-private\`.
  * Extracted plain-arm64 `sbin/launchd` (541,600 bytes, 127 4K CodeDirectory pages, XML + DER entitlements) and `usr/lib/dyld` (922,912 bytes, 220 4K CodeDirectory pages, no entitlements); page hashes independently verified (`outputs/ios16-bootstrap-codesign.json`).

## 2. Completed Local Development Milestones (Option A + Option B)
* **Option A (AMFI XML Entitlements, `CS_PLATFORM_BINARY`, and `CS_SIGNED` Support):**
  * Staged `0035-sweet-amfi-entitlements-platform-binaries.patch` and `0036-sweet-amfi-cs-signed.patch` (`iokit/Kernel/arm/SweetEntitlements.cpp`, `bsd/kern/miami_amfi.c`, MAC policy registration in `bsd/kern/bsd_init.c`) via `miami/xnu/ram_root.py`.
  * Hardened `miami_amfi_attach_entitlements` and `miami_amfi_adjust_without_monitor` to fail closed on unreadable XML, CodeDirectory special-slot hash mismatches, or DER-only entitlements while supporting dual XML+DER blobs (matching stock iOS 16.7.16 `sbin/launchd`).
  * Embedded XML entitlements (`com.motorola.miami.pid1`, `com.apple.private.miami.test-bool`, `com.apple.private.miami.test-string`) into `miami-init.macho` (`miami/userspace/build.py`) and added EL0 `SYS_csops` (`169`) `CS_OPS_STATUS` (`CS_VALID | CS_ADHOC | CS_SIGNED | CS_PLATFORM_BINARY`) and `CS_OPS_ENTITLEMENTS_BLOB` verification in `miami/userspace/init.S`.
  * Extended `miami/userspace/verify_codesign_pages.py` to verify all negative special slots (`-1..-special`, including slot `-5` XML entitlements) in addition to positive code page slots.
* **Option B (Built-in Apple OSS HFS+ `hfs-627.100.6`, BearSSL MD5, and Multi-File HFS+ RAMDisk Root):**
  * Staged `0027-sweet-bearssl-md5.patch` (`corecrypto_md5.c` + BearSSL `md5.c`, `dec32le.c`, `enc32le.c`) in `miami/xnu/aes_component.py` and verified with `miami/tests/check-md5.py`.
  * Created `miami/xnu/hfs_component.py` to stage Apple OSS `hfs-627.100.6` (`31d5ec238dfab485e78a9a30b8b92d13e8914f03`) into `bsd/miami_hfs`, apply `0026-sweet-builtin-hfs.patch`, `0029-sweet-unsealed-root-volume.patch`, and `0031-sweet-read-write-root.patch`, and wired `--hfs` into `miami/xnu/prepare.py`, `miami/xnu/configure-helper.py`, and `.github/workflows/miami-xnu*.yml`.
  * Created `miami/userspace/mkhfs.py` to deterministically build and independently validate a 128-KiB (32 x 4-KiB block) HFS+ root volume (`miami-root.hfs`) containing `/sbin/launchd`, `/etc/miami-root` (`MIAMI HFS+ ROOT OK\n`), and `/dev`, plus EL0 `/etc/miami-root` readback in `miami/userspace/init.S`.
  * Updated `miami/loader/plan.c` and `miami/loader/payload.py` to validate both static 64-KiB Mach-O (`mockfs`) and bounded HFS+ (`H+` / `HX`, up to 64 MiB) RAMDisk images on `md0`.
