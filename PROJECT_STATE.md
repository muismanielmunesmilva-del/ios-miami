# MIAMI Project State — Experimental iOS 16 Port for Motorola Edge 30 Neo (`XT2245-1`)

**Last Updated:** 2026-11-10
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
* **Latest Verified Physical Hardware Execution (`MIAMI_XNU_0020`):**
  * Actions Run: [`42871865902`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42871865902) (kernel CI commit `f118662`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `5685dae2b83de4836fa83b820453393dfeb66a99e06cafab00594395fc9a8375` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `ff9ceeaef8449e755259e843c98d6c78a0d4c845b5c92c81729b1ea2904534ef` (`16,628,544` bytes).
  * Features integrated in `0020`: USB CDC-ECM Ethernet gadget descriptors (`USB\Class_02&SubClass_06&Prot_00`), multi-endpoint DWC3 configuration (EP0 control, EP1 bulk IN/OUT, EP2 interrupt IN), deferred `ue0` network stack initialization (`192.168.7.2/24`).
  * Hardware result (`0020`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; host Windows PC enumerated CDC-ECM device (`Miami iOS 16 (XNU)`); user confirmed live control packet serving on screen (`setup 80 06 0300 0000 len 255`, `event 0x0000c040`); zero panics, continuous verbose console and heartbeats stable.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0019`):**
  * Actions Run: [`42860272847`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42860272847) (kernel CI commit `e487efd`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `f211214c4e8605315a936a0d37b998c9b39872e9da54c1e20c72fc8136cbb179` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `6d0d0640f01b2e4656cf3e182529154d1567bbc7e5ecb7de5bc40272c8aa4f06` (`16,628,336` bytes).
  * Features integrated in `0019`: Synopsys DWC3 USB Gadget EP0 control transfer enumeration + Qualcomm QSCRATCH VBUS override at `0x04ef8800` (`QSCRATCH_HS_PHY_CTRL` / `QSCRATCH_SS_PHY_CTRL`).
  * Hardware result (`0019`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; VBUS override engaged, D+ pulled up, host Windows PC successfully enumerated USB device `Miami iOS 16 (XNU)` (VID `0x1209`, PID `0x0001`), standard EP0 `GET_DESCRIPTOR` served without panic.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0018`):**
  * Actions Run: [`42847601129`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42847601129) (kernel CI commit `d4e8a01`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `7e999bc4e932c7e7c05847362811e008f93616c56034c29afd0350102089bce6` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `18f780517855b7c89694ce22896f60ea0b005e8346e9df53cae9ef8b08eb3e28` (`16,611,736` bytes).
  * Features integrated in `0018`: Read-only Synopsys DWC3 USB & Femto HSPHY hardware state probe (`bsd/dev/miami_usb.c` at DWC3 MMIO `0x04e00000`, HSPHY `0x0162b000`, GCC `0x01400000`), verifying live USB core ID (`GSNPSID`, `GHWPARAMS`), link state (`DSTS`), and event buffer layout left by fastboot.
  * Hardware result (`0018`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed physical display of `MIAMI USB:` probe logs on-screen, active verbose console, and rapid continuous heartbeats without any bus fault or kernel panic.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0017`):**
  * Actions Run: [`42839628747`](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42839628747) (kernel CI commit `b1e3dbe`, branch `main` / `miami-ci`).
  * `boot.img` SHA-256: `d910331fe0dc0e64aaed36743887c09b213a87a635f56a63c684579c7fd71119` (`100,663,296` bytes).
  * `kernel.development.miami` SHA-256: `785d0da4e8db374026dc7aa0a7905dbe0fc15dc1ec0fa7a9cfa6b0ff12ff7f8a` (`16,611,696` bytes).
  * Features integrated in `0017`: Polled SPMI hardware keys driver (`bsd/dev/miami_keys.c` at SPMI core `0x01c40000`, obsrvr `0x03e00000`, cnfg `0x01c0a000`), PM6125 PON (Power + VolDown), PMR735A GPIO1 (VolUp), and active HID event generation (`MiamiHIDButtons` + `miamihidtest=5`).
  * Hardware result (`0017`): **PASS (User Verified on Physical Motorola Edge 30 Neo `XT2245-1`)** — temporary `fastboot boot` accepted; user confirmed physical display of `MIAMI HID: key 0x...` event logs with hexadecimal usages on-screen, active verbose console, and rock-solid stability without panic.
* **Previous Verified Physical Hardware Execution (`MIAMI_XNU_0016`):**
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
