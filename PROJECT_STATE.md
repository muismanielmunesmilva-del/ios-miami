# MIAMI Project State — Experimental iOS 16 Port for Motorola Edge 30 Neo (`XT2245-1`)

**Last Updated:** 2026-11-09
**Authoritative Repository:** `C:\Users\twix\Documents\Codex\2026-11-05\ol\work\ios-miami`
**Branch:** `miami-bringup`
**Public CI Repository:** `https://github.com/muismanielmunesmilva-del/ios-miami`

## 1. Current Verified State
* **Boot Chain & Loader (`0005`):** AArch64 Linux-ABI `Image` packaged in a 96-MiB Android boot v3 + AVB (`NONE`) container for `fastboot boot`. Validates live FDT, reserved memory, upper RAM (`[0x180000000, 0x1bff00000)` + 1 MiB panic log at `0x1bff00000`), SDE autorefresh splash framebuffer (`[0x85200000, 0x85e00000)`), and copies/reads back XNU segments, ADT, `boot_args`, and bounded RAMDisk (`mockfs` Mach-O up to 64 KiB or HFS+ volume up to 64 MiB) before branching with MMU off at EL1.
* **XNU Kernel (`xnu-8796.141.3`, iOS 16 / macOS 13.5):**
  * Single-CPU (`MAX_CPUS=1`), `arm,cortex-a55` IOCPU matching (`MIDR=0x412fd050`), GICv3 (`GICD=0x0f200000`, `GICR=0x0f240000`), architectural virtual timer `INTID 19` @ 19.2 MHz.
  * 16K page tables (`TGran16=1`), Normal-NC/XN early and final splash framebuffer mappings (`768` 16K pages), 18-row protected first-panic screen.
  * Integrated Apple `libpthread-514.100.2` (`a6c70ca`) with 56-byte / 8-byte-aligned `ksyn_waitq_element` ABI.
  * Integrated `BearSSL` (`7bea48e`) constant-time legacy AES-CBC (`g_crypto_funcs` fallback) and MD5 (`corecrypto_md5.c`), plus built-in XNU `ccsha256_ltc_di` SHA-256 wrapper.
  * Integrated `mockfs`, `devfs`, and Apple OSS HFS+ (`hfs-627.100.6`, commit `31d5ec238d`) RAMDisk root (`rd=md0`).
  * Integrated built-in AMFI interface (`miami_amfi.c` + `SweetEntitlements.cpp`) with `OSDictionary` XML entitlement parsing, rootfs `CS_PLATFORM_BINARY | CS_SIGNED` MAC policy, dual XML+DER entitlement admission, and fail-closed validation on malformed XML or DER-only blobs.
* **Latest Verified Physical Hardware Execution (`MIAMI_XNU_0016`):**
  * Actions Run: [`42831584898`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42831584898) (kernel CI commit `349afb2`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `74ba3cdf994a8e4484a8523da70022ee21427941c9c38dfa468f8bb7de55dcd8` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `e432c695a0bc0eec73b18dfdb1e33dff659eb8f972b93086eb2a344937fa648c` (`16,611,360` bytes).
  * Features integrated in `0016`: Native HID & Touchscreen Subsystem (`MiamiHIDTouch` for Goodix GT9916S SPI digitizer + `MiamiHIDButtons` + `IOHIDEvent` + `IOHIDEventServiceQueue` + `IOHIDEventServiceUserClient` on `/arm-io`).
  * Hardware result (`0016`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed physical display of verbose console, `miami userspace pid=1 (getpid verified)`, AMFI validation, rapid continuous heartbeats, and zero crashes. Native HID services verified intact in single-CPU kernel.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0015`):**
  * Actions Run: [`42817993843`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42817993843) (kernel CI commit `312d6bb`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `54daf3b9a56699a7f1fd2455eb71f8367f186eca796c66daaf54e5262f45f363` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `b88c93254c0f3cc642ff3634a02b5d156eabcd7e665d6f5fd0ac0109828994a0` (`16,531,480` bytes).
  * Features integrated in `0015`: Native display pipeline (`IOCoreSurfaceRoot` + `AppleCLCD : public IOMobileFramebuffer` on `/arm-io/disp0`), 1080x2400 AMOLED continuous splash mapping at `0x85200000`, 60 Hz VSync timer (`IOTimerEventSource`), user client interfaces (`IOSurfaceRootUserClient`, `IOMobileFramebufferUserClient`), and `/arm-io` nub publisher hook in `SweetPlatformExpert::processTopLevel`.
  * Hardware result (`0015`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed physical on-screen boot with continuous heartbeats and zero crashes. Display drivers, ADT nodes, and kernel structures verified intact.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0014`):**
  * Actions Run: [`42725998034`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42725998034) (kernel CI commit `320da2742af46c883be503fce7d44830f79e419c`, branch `miami-ci-public` / `main`).
  * `boot.img` SHA-256: `c8de4ddf0fc9e9324b053384e629f20277e3450817ba6e5968fdf6e3011508eb` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `293970176d1250e485f59865f33c509c3671f53dc44b368a8d53c4cc8b465673` (`16,474,136` bytes).
  * Features integrated in `0014`: Qualcomm UFSHCI 2.1 SCSI read-only storage driver (`bsd/dev/miami_ufs.c` at MMIO `0x04804000`), `/miami-ufs` ADT node, polled SCSI Read(10), GPT partition scanner (`ufsroot=userdata`), devfs nodes `ufsroot0` and `rufsroot0`, and strict read-only partition protection (`EROFS`).
  * Hardware result (`0014`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed physical display of threads, HFS+, Sandbox, psynch, AMFI platform binary / entitlements, and rapid continuous heartbeats. Zero partition writes issued.
* **Previous Verified Host Delivery (`MIAMI_XNU_0013`):**
  * Actions Run: [`42709183824`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42709183824) (kernel CI commit `9b978f02931a7b45f44daaa2cffdb01fc6ad55c5`, branch `miami-ci-public` / `main`).
  * `boot.img` SHA-256: `54640ba0bb21748312dbf409741490ce6d99230d0c3c3f0c1ac15fcf1386852d` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `166c94e58cfa356bffb6512d8698764630bb9e92e5ea9f13387cd89da4de660e` (`16,472,952` bytes, `LC_UUID`: `4D194B4E-5205-325A-98C0-E5E3DDA5BA90`).
  * `payload.bin` (HFS+ RAMDisk) SHA-256: `323b0008e1e0cf1e32db9c4cf495d89f033d9148442837bae8c09cd2582a8122` (`16,591,168` bytes).
  * `miami-root.hfs` SHA-256: `2e07d565d801caf763bd1cd95f55dcd84f406cab98be81c29dec2b8f7c9843c2` (`131,072` bytes; contains `/sbin/launchd`, `/etc/miami-root`, and `/usr/lib/dyld`).
  * `miami-init.macho` SHA-256: `b49bc2fc20d054ef1c75f2b0a644f33d1d35609c20789c84ffc20e5a9294c9a8` (`17,171` bytes).
  * QEMU 150s result: `PASS` (`hfs: mounted MiamiRoot on device b(1, 0)`, `PID=1 (getpid verified)`, `MIAMI Sandbox: launchd op 0`, `MIAMI Sandbox: launchd op 4`, `MIAMI AMFI: platform binary, XML entitlements and Sandbox verified`, `MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified`, `MIAMI PSYNCH: cvwait timed out as expected`, `MIAMI THREADS: waiting thread signaled successfully`, 23 heartbeats, 93 EL0 SVCs across 20 call sites, `check-pid1-runtime.py` exit code 0).
  * Features integrated in `0013`: BearSSL SHA-1 (`0032`), BearSSL SHA-384 & SHA-512 (`0033`), HFS+ link notes (`0041`), HFS+ `VFS_RENAME_SWAP` (`0052`), `bindfs` (`0037`), `AppleKeyStore` (`0038`, `0055`), `do_coredump = 0` (`0039`), exec short logging (`0042`), console crash logging (`0043`, `0044`), permissive `"Sandbox"` MAC policy (`0050`), `PRIV_WORK_INTERVAL` (`0064`), signed `/usr/lib/dyld` (`MH_DYLINKER`) execution before `/sbin/launchd`.
  * Hardware result (`0013`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed on-screen execution of `MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified`, `MIAMI AMFI: platform binary, XML entitlements and Sandbox verified`, `MIAMI PSYNCH: cvwait timed out as expected`, `MIAMI THREADS: waiting thread signaled successfully`, and continuous heartbeats. Zero flash writes issued.
* **Latest Verified Physical Hardware Execution (`MIAMI_XNU_0012`):**
  * Actions Run: [`42695357398`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42695357398) (kernel CI commit `c6ae04e343fcad26caf4e6be8f5a8e1a4551cdbe`, loader/PID1 commit `6fc0f0d`).
  * `boot.img` SHA-256: `14bf17878b396cb50244d0acf74fff2731f9d567b88c33ba3dd3bc598a405cdc` (`100,663,296` bytes).
  * Hardware result (`0012`): **PASS (User Verified)** — temporary `fastboot boot` accepted; user confirmed `MIAMI PSYNCH: cvwait timed out as expected`, `MIAMI THREADS: waiting thread signaled successfully`, and repeating `MIAMI PID1: heartbeat` on the Motorola Edge 30 Neo screen. Zero partition writes ever issued.
* **Real iOS 16.7.16 (`20H392`, `iPhone10,3`/`iPhone10,6`) Inspection State:**
  * Pinned `BuildManifest.plist` (`2d145210...`) and DMGs (`087-86698-044.dmg` OS, `087-86593-047.dmg` SystemOS, `087-86715-047.dmg` AppOS) verified via SHA-384 and CRC-32 in `ol\work\miami-private\`.
  * Extracted plain-arm64 `sbin/launchd` (541,600 bytes, 127 4K CodeDirectory pages, XML + DER entitlements) and `usr/lib/dyld` (922,912 bytes, 220 4K CodeDirectory pages, no entitlements); page and special-slot hashes independently verified (`outputs/ios16-bootstrap-codesign.json`).
