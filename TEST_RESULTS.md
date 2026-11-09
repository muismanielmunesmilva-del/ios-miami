# MIAMI Verification & Test Results

**Last Updated:** 2026-11-09

## 1. Bare-Metal Hardware Probes (`miami/probe/`)
| Probe ID | Image SHA-256 | Hardware Result | Verification Evidence |
| :--- | :--- | :--- | :--- |
| `0001` | `8acd85b7...` | Returned to Android | Fastboot log |
| `0002` | `8d56c3bd...` | Hung before display; 0 pstore entries | Fastboot/TWRP logs |
| `0003` | `f358b09f...` | **PASS**: `EL1`, `MIDR=0x412fd050`, `MMFR0=0x101122`, `CNTFRQ=19.2MHz`, `PSCI=1.0` | **Photo** (`f20cf5db...`) |
| `0004` | `09b84cb1...` | **PASS**: GICv3 virtual timer `INTID 19` (`9` IRQs, `0` other, `GIC_TEST_RESULT=0`) | **Photo** (`6266bc53...`) |
| `0005` | `0451f26a...` | **PASS**: 16K MMU + caches (`SCTLR=0xc0180d`), alias R/W, guard fault (`PAR=0x80f`), 9 timer IRQs | **Photo** (`93954da7...`, `miami/probe/results/0005.json`) |

## 2. XNU Kernel Bring-Up Images (`outputs/miami-xnu-boot-0001` .. `0012`)
| Image ID | CI Run / Source Commit | `boot.img` SHA-256 | QEMU (`cortex-a55` virt) Result | Physical Device (`XT2245-1`) Result |
| :--- | :--- | :--- | :--- | :--- |
| `0001` | `42165337842` (`1574a19b`) | `57332234...` | Unaligned 16K splash table fault | Stopped before XNU console |
| `0002` | `42165337842` (`1574a19b`) | `9b843423...` | Unaligned 16K splash table fault | **Photo**: Loader copied segments `0..9`, stopped at jump |
| `0003` | `42192773280` (`02467e8f`) | `e91be91e...` | **PASS** early console -> target GIC MMIO abort | User report: stopped at loader jump message |
| `0004` | `42198284206` (`cdd0f604`) | `10278349...` | **PASS** 7 boot marks + early console | **Photo**: XNU console on screen, PE init, VM bootstrap, IOMD init |
| `0005` | `42202366971` (`a98a0f89`) | `60bc88c9...` | **PASS** `Cortex-A55` CPU0 + `SGI1` -> `pthread_init` panic | **Photo** + User report: `SGI1` verified, panic backtrace in `pthread_init` |
| `0006` | `42239849041` (`51c19485`) | `7979f2d8...` | **PASS** `pthread_init` -> `aes_encrypt_key128` NULL fault | **Photo**: Panic dump matching `LC_UUID` `AA615D30...` |
| `0007` | `42282654652` (`988db790`) | `7062d265...` | **PASS** 18-row first-panic screen shows `aes_encrypt_key128+0x10` | **Photo** (`b9c827e1...`): Protected panic pane shows `aes_encrypt_key128+0x10` (`FAR=0x78`) |
| `0008` | `42287672552` (`64c5ca35`) | `8115cf14...` | **PASS** 150s: `pthread_init`, Skywalk PASSED, `Waiting on IOMedia/Apple_HFS` | **Photo** (`a313f7d0...`): `MIAMI PTHREAD` complete, `Skywalk PASSED`, `!BSD`, `Waiting on IOMedia/Apple_HFS` |
| `0009` | `42343575171` (`b12e4249`) | `fb44f280...` | **PASS** 150s: `mockfs` `md0`, `PID=1 (getpid verified)`, 17 heartbeats, 38 EL0 SVCs | **User Report**: `PID=1` and `heartbeat` messages visible on phone |
| `0010` | `42347275248` (`bebb048d`) | `641db205...` | **PASS** 150s: `psynch_cvwait` timeout `0x13c`, 17 heartbeats, 40 EL0 SVCs | **User Report**: `MIAMI PSYNCH` timeout message and heartbeats visible on phone |
| `0011` | `42349700687` (`215a2eee`) | `7bf23e1c...` | **PASS** 150s: cross-thread `psynch_cvsignal` (`PTHRW_INC`), 17 heartbeats, 66 EL0 SVCs; negative late-signal control **PASS** | **User Report**: `MIAMI THREADS: waiting thread signaled successfully` and heartbeats visible on phone |
| `0012` | `42695357398` (`c6ae04e3` / `6fc0f0d`) | `14bf1787...` | **PASS** 150s: `hfs: mounted MiamiRoot on device b(1, 0)`, `PID=1`, `MIAMI AMFI: platform binary and XML entitlements verified`, `MIAMI HFS+: /etc/miami-root verified`, `psynch_cvwait` + cross-thread signal, 17 heartbeats, 73 EL0 SVCs | **User Report**: `MIAMI PSYNCH: cvwait timed out as expected`, `MIAMI THREADS: waiting thread signaled successfully`, and `heartbeat` visible on phone (`miami/loader/results/0012.json`) |
| `0013` | `42709183824` (`9b978f02` / `4af7ec6`) | `527a41aa...` | **PASS** 150s: BearSSL SHA-1/384/512, HFS+ link notes & rename swap, `MIAMI Sandbox: launchd op 0` & `op 4`, `MIAMI AMFI: platform binary, XML entitlements and Sandbox verified`, `MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified`, `psynch_cvwait`, cross-thread signal, 23 heartbeats, 93 EL0 SVCs across 20 call sites (`check-pid1-runtime.py` exit code 0) | Not yet attempted (`fastboot boot outputs\miami-xnu-boot-0013\boot.img`) |

## 3. Local Host Test Suites (`miami/tests/`)
* `miami/tests/check.py --dtc /mnt/c/Users/twix/Documents/Codex/2026-11-05/ol/work/dtc --live-fdt /mnt/c/Users/twix/Documents/Codex/2026-11-05/ol/work/miami-private/live-recovery.dtb`: Loader payload plan, RAM reservation, FDT validation, signed `mockfs` Mach-O (`36,800` bytes payload) and signed HFS+ RAM-root (`150,688` bytes payload) handoff, HFS+ corruption rejection, AArch64 cross-compile/link (`PASS`, 2026-11-09).
* `miami/tests/check-console.py`: Bootstrap assembly & 768-page 16K splash mapping verification (`PASS`, 2026-11-09).
* `miami/tests/check-codesign-pages.py`: Mach-O CodeDirectory SHA-256 page hash and negative special-slot (`-1..-5`) hash verifier (`PASS` on XML-entitled `miami-init.macho` and real iOS 16.7.16 `launchd`/`dyld`, 2026-11-09).
* `miami/tests/check-source.py`: Fresh pinned XNU (`1b191cb582`), helper (`663906528d`), `libpthread` (`a6c70ca0e5`), `BearSSL` (`7bea48e5e8`), and `hfs-627.100.6` (`31d5ec238d`) staging + panic (`check-panic.py`), AES (`check-aes.py`), MD5 (`check-md5.py`, 60 cases across 4 chunk sizes), SHA-256 (`check-sha256.py`), and AMFI XML-entitlements/platform-binary (`check-amfi.py`) harnesses (`PASS`, 2026-11-09).
