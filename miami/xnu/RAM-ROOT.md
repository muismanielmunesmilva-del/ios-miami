# RAM-only first userspace process

Image0008 reached the IOMedia/Apple_HFS root-device wait on the phone, with
pthread completion and Skywalk self-tests visible. The next test supplies
only a small RAM-backed executable. It does not contain an iOS installation.

## Kernel path

Five selected ios-sweet fixes (0021–0025), transformed to MIAMI names, enable
Apple's built-in `mockfs`, correct its typed node allocation, handle absent
IOStorageFamily classes for memory-root selection, use XNU's existing SHA-256
implementation for legacy wrappers/code-signing page hashes, and route virtual
RAM disks through normal device IO. The last fix also keeps memdev's 4K page
units distinct from this kernel's 16K pages. Input/target patch hashes are
recorded in `miami-source.json`. Other boards retain the original IOStorage
assertions and crypto dispatch path.

Mockfs exposes the RAM executable as `/sbin/launchd`, with a devfs mountpoint.
The test executable uses only open/write/getpid/select. It checks the actual
getpid result equals1 before printing `MIAMI USERSPACE: PID=1 (getpid verified)`
and emits `MIAMI PID1: heartbeat` after each five-second select. Its stack is
explicitly aligned before any stack access; timeout and mutable data are on
the writable stack. Console writes handle partial results. It never exits PID1.

## Bounded handoff

The packager accepts an optional static plain-arm64 probe, at most64KiB,
and independently checks Mach-O layout, entry, permissions, ad-hoc SHA-256
CodeDirectory and every signed page. It uses `rd=md0` and appends one owned
16K-aligned segment after the kernel. The ADT RAMDisk physical range must match
that final segment exactly and end before the ADT/bootargs reservation.

The native C loader rejects duplicate/misplaced RAMDisk properties, missing or
duplicate/inconsistent root arguments, wrong image architecture/type, bad root
sizes/ranges and an entry redirected into the RAM image. Existing upper-RAM,
reserved-memory, payload-copy/readback, framebuffer and AVB checks remain.
The loader's new diagnostic banner is0005; the planned next test ID is0009.

This change adds no UFS/storage/USB driver and permits no persistent root path.
The executable only writes its diagnostic text to the console. Android and
userdata remain intact; tests use temporary `fastboot boot` only.

## Checks and current status

Fresh pinned XNU staging with all target patches passes. The actual XNU
SHA256 wrappers and built-in provider match hashlib for44 empty, known,
boundary, large and chunked-input cases. The existing pthread/AES/source and
panic-console checks pass. The loader tests execute its actual C validator
against a real signed probe plus synthetic-kernel fixtures, rejecting malformed
RAM handoffs and altered signed code. Cross-compilation/link and both workflow
syntax checks pass. Full CI42294997601 passed, but the 150-second isolated host test found a
kernel data abort at accelerate_entitlement_queries+0x1c, FAR0x1a0, before
EL0 execution. This is the absent AMFI interface, not a successful PID1 test.
The verified revision stages the selected upstream no-entitlements interface,
hardened to reject XML/DER entitlement blobs or existing entitlement objects.
All privilege queries are denied. Normal CodeDirectory and page-hash checks
remain. The policy harness checks these rejection cases; the real kernel
build verifies Apple's actual interface ABI. No image0009 has been sent.

Both workflows build/package the same static probe, require actual mockfs and
SHA256/AMFI symbols, validate the rooted payload and publish its hashes alongside
the kernel. A successful host runtime test must show PID1 and repeated
heartbeats, with independent EL0/SVC trace evidence. A compiled image alone
does not establish userspace execution or an iOS boot.

## Verified delivery

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

The final artifact's kernel SHA-256 is `9acdf2a6342cac42b999b7e5013bf381e3ae896bc089007ee42c00d5f8570e9f` and UUID
`31FFE095-E332-3661-BAD1-20CCFC297A6D`. Image0009 SHA-256 is
`fb44f280f0a8e49ab89bb50d83de352bfa2673c8f7f4c49628b74022c7241324`. The signed probe is
`0bf2c9dec1f231148aba48ec8dc191f8e98ead908d857b9c02e7304b4135c681`.

The pre-reconstitution guard runs after structural signature validation and
before XML can be stripped. The host policy harness checks denial cases.
Physical validation remains pending. The final artifact kernel/probe and the
exact payload embedded in image0009 passed the host execution test. The CI
payload also passed separately; repackaging supplies a fresh entropy seed.

The probe does not exercise PSYNCH/full pthread APIs. Before those tests,
the MIAMI kernel's opaque wait storage must be reconciled with the paired
provider structure and checked with an ABI size/alignment assertion.

## References

- [Apple mockfs design](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/miscfs/mockfs/mockfs_vfsops.c)
- [Apple RAMDisk/root-device selection](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/iokit/bsddev/IOKitBSDInit.cpp)
- [Apple memory devices](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/dev/memdev.c)
- [Apple initial process loading](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/kern/bsd_init.c)
- [Original static test wrapper](../../tools/mkinit.py)
- [MIAMI test program](../userspace/init.S)
