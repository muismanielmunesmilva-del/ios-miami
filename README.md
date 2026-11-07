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

Image 0009 was booted temporarily on the phone. The user reported PID 1
and heartbeat messages. For image 0010 the user reported the expected PSYNCH
timeout message and heartbeats. No phone photograph was provided for either.

Image 0011 prepares a cross-thread condition-signal test. The program
registers and creates a BSD thread, then waits on a private PSYNCH condition.
The second thread signals it, and the test requires the returned PTHRW_INC
to confirm an actual waiter was signaled instead of only preposting a signal.
[Actions 42349700687](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42349700687)
passed at `215a2eeed0320f00938617762b3b9d44ada02a88`. An isolated 150-second QEMU test of the exact
delivered payload showed the signal success, 17 heartbeats and
66 EL0 SVCs. This is host evidence. The phone test remains pending.
This is a bounded kernel-interface test, not full libpthread or iOS userland.
A separate host-only late-signal variant produced the expected failure and
continued heartbeats without a visible panic.

MIAMI's opaque pthread wait storage is now 56 bytes and 8-byte aligned,
matching the pinned Apple provider, whose size and alignment have compile-time
assertions. [Actions 42347275248](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42347275248)
passed at `bebb048d775f4133c80ed1d46f5cd76105d5c9d3`. The resulting kernel is byte-identical to image 0009;
the corrected source declaration does not change that binary. The PID1 probe
is new. Its exact packaged payload passed a 150-second QEMU control: expected
`ETIMEDOUT | ECVCLEARED` (0x13c), 17 heartbeats and
40 EL0 SVC calls. That host test covered a timed wait; the subsequent cross-thread
signal test is described above. The full pthread API remains untested.

The RAM root contains a static test program and devfs. Full iOS userland,
storage and other device drivers remain future work.

The first RAM-root host attempt exposed a missing AMFI interface. The target
now registers a no-entitlements interface, denies privilege queries and rejects
XML/DER before signature reconstitution. CodeDirectory/page-hash checks remain.
The image 0009 probe used open/write/getpid/select; image 0010 adds one
bounded condition wait. It does not validate the full pthread userspace API. See [RAM-root design and evidence](miami/xnu/RAM-ROOT.md).

Kernel: 15925816 bytes, SHA-256 `9acdf2a6342cac42b999b7e5013bf381e3ae896bc089007ee42c00d5f8570e9f`.
UUID: `31FFE095-E332-3661-BAD1-20CCFC297A6D`.
Prepared image 0011 SHA-256: `7bf23e1c6c4a3f2134309ada6cdb5cc52cbdd5d9e6c4bbe071ec90401bb2670a`.

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
