# MIAMI Next Concrete Engineering Steps

**Last Updated:** 2026-11-09

## 1. Completed & Verified in Milestone `MIAMI_XNU_0013` (2026-11-09)
1. **Cryptographic Providers & Userspace Support:**
   * Staged BearSSL SHA-1 (`0032`), BearSSL SHA-384 & SHA-512 (`0033`), HFS+ link notes (`0041`), HFS+ `VFS_RENAME_SWAP` (`0052`), `bindfs` (`0037`), `AppleKeyStore` (`0038`, `0055`), `do_coredump = 0` (`0039`), exec short logging (`0042`), console crash logging (`0043`, `0044`), permissive `"Sandbox"` MAC policy (`0050`), and `PRIV_WORK_INTERVAL` (`0064`).
   * Unit-tested cryptographic hashing (`check-sha256.py`) against `hashlib` across 80 cases and chunk sizes, and verified AMFI XML entitlements and Sandbox MAC syscall handling (`check-amfi.py`).
2. **Dynamic Linker (`LC_LOAD_DYLINKER` / `/usr/lib/dyld`) & Multi-File HFS+ Catalog:**
   * Added folders `/usr`, `/usr/lib`, and signed binary `/usr/lib/dyld` (`MH_DYLINKER`) to `miami-root.hfs` (`mkhfs.py`).
   * Configured `/sbin/launchd` with `LC_LOAD_DYLINKER -> /usr/lib/dyld`.
   * Verified `_dyld_start` execution at EL0: XNU maps `/usr/lib/dyld`, pushes the main binary Mach-O header pointer to `[sp]`, and enters `_dyld_start`, which verifies `MH_MAGIC_64`, sets `x28 = 0x44594c44` (`"DYLD"`), and jumps to `/sbin/launchd`.
3. **Compilation & Architectural QEMU Verification:**
   * Built `kernel.development.miami` on macOS Xcode 16.4 in GitHub Actions Run [`42709183824`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42709183824) (`9b978f02931a7b45f44daaa2cffdb01fc6ad55c5`).
   * Packaged `boot.img` (`outputs/miami-xnu-boot-0013/boot.img`, SHA-256 `527a41aa80de84059f170b870582c0d00d477557e6623b7e3dff07e82a4b5bf6`).
   * 150-second architectural QEMU run: **PASS** (all probes verified: `PID=1`, `Sandbox: launchd op 0/4`, `AMFI: platform binary, XML entitlements and Sandbox verified`, `HFS+: /usr/lib/dyld and /etc/miami-root verified`, `PSYNCH: cvwait timed out as expected`, `THREADS: waiting thread signaled successfully`, 23 heartbeats, 93 EL0 SVC calls across 20 call sites, `check-pid1-runtime.py` exit code 0).

## 2. Next Concrete Engineering Tasks
1. **Physical Hardware Boot Test (`MIAMI_XNU_0013`):**
   * When authorized by the user, test `outputs\miami-xnu-boot-0013\boot.img` via temporary `fastboot boot` on the Motorola Edge 30 Neo (`XT2245-1`) to confirm physical hardware execution of `/usr/lib/dyld` handoff, permissive Sandbox MAC policy, and HFS+ root file readback.
2. **Prepare Real iOS 16 Shared Cache & UFS Storage Architecture:**
   * Investigate SM6375 UFS controller registers and drivers (`0028`, `0030`, `0034`, `0069`) to enable reading disk images or large libraries from storage without writing to or modifying Android partitions.
