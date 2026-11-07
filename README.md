# ios-miami

Single-CPU XNU bring-up for Motorola Edge 30 Neo XT2245-1 (SM6375), inspired
by [ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).

The RAM-only first-process build passed [Actions 42343575171](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42343575171)
at `b12e42493b7ca027465805bd06a77d950da92502`. Its exact kernel/payload/probe passed independent
artifact, implementation, signature-page, RAM-range and loader checks.
The 150-second QEMU control mounted md0 through mockfs and executed the
static program as PID1: getpid verified, 17 visible heartbeats and
38 SVC calls from the four probe call sites in EL0. No panic was
visible in the final snapshot. These are host results.

Temporary image0009 is prepared with loader0005 and `rd=md0`; the phone test
has not been attempted. The last phone evidence remains image0008: pthread
initialization, Skywalk PASSED and the IOMedia/Apple_HFS root-device wait.
The new RAM root contains only the static test program and devfs; full iOS
userland, storage and other device drivers remain future work.

The first RAM-root host attempt exposed a missing AMFI interface. The target
now registers a no-entitlements interface, denies privilege queries and rejects
XML/DER before signature reconstitution. CodeDirectory/page-hash checks remain.
The probe uses open/write/getpid/select; it does not validate the full pthread
userspace API. See [RAM-root design and evidence](miami/xnu/RAM-ROOT.md).

Kernel: 15925816 bytes, SHA-256 `9acdf2a6342cac42b999b7e5013bf381e3ae896bc089007ee42c00d5f8570e9f`.
UUID: `31FFE095-E332-3661-BAD1-20CCFC297A6D`.
Prepared boot image SHA-256: `fb44f280f0a8e49ab89bb50d83de352bfa2673c8f7f4c49628b74022c7241324`.

- [Build instructions and earlier milestones](miami/xnu/README.md)
- [Pthread integration](miami/xnu/PTHREAD.md)
- [Portable legacy AES](miami/xnu/AES.md)
- [Protected first-panic diagnostics](miami/xnu/PANIC-SCREEN.md)
- [Main workflow](.github/workflows/miami-xnu.yml)
- [Manual Intel workflow](.github/workflows/miami-xnu-intel.yml)

Both workflows select macOS15 Intel/Xcode16.4 and DEVELOPMENT/ARM64/MIAMI.
Apple XNU8796.141.3, matching libpthread514.100.2 and BearSSL are pinned in
the workflow and source manifests. Device dumps, calibration, downloaded Apple
userland and local output are excluded. Android and userdata are preserved;
device tests use temporary `fastboot boot`, without partition-write commands.

See [LICENSE](LICENSE) and retained copyright notices.
