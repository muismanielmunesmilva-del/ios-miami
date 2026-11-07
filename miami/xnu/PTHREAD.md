# Matching Apple pthread kernel component

Image 0009 was booted temporarily on the phone. The user reported that
PID 1 and heartbeat messages appeared; no phone photograph was provided.
The new image 0010 is prepared for a bounded `psynch_cvwait` timeout test;
its phone test is pending.

MIAMI's opaque pthread wait storage is now 56 bytes and 8-byte aligned,
matching the pinned Apple provider, whose size and alignment have compile-time
assertions. [Actions 42347275248](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42347275248)
passed at `bebb048d775f4133c80ed1d46f5cd76105d5c9d3`. The resulting kernel is byte-identical to image 0009;
the corrected source declaration does not change that binary. The PID1 probe
is new. Its exact packaged payload passed a 150-second QEMU control: expected
`ETIMEDOUT | ECVCLEARED` (0x13c), 17 heartbeats and
40 EL0 SVC calls. This host test covers a timed wait; thread
signalling and the full pthread API remain untested.

The image 0005 photograph shows a kernel panic backtrace. Symbolication using
the exact verified kernel and LR minus four yields pthread_init.cold.1+0x24,
pthread_init+0x1c, bsd_init+0x48c and kernel_bootstrap_thread+0x4ac. The panic
header is outside the photo. Source inspection identifies the NULL function
table guard; its reason string is inferred from source, not read from the photo.

Apple's [macOS 13.5 release manifest](https://github.com/apple-oss-distributions/distribution-macOS/blob/macos-135/release.json)
pairs xnu-8796.141.3 with libpthread-514.100.2. The pthread source commit is
`a6c70ca0e544347a0377babf748f831577ec24f9`; the workflow fetches this exact
commit, and staging rejects a different commit. Input and staged file hashes
are included in miami-source.json.

The port statically links the three real Apple kernel translation units.
It preserves their function table, thread creation, workqueue stack support,
mutex/condition/rwlock implementation and allocator metadata. No userspace
libpthread code is compiled at this stage.

The original [pthread_start](https://github.com/apple-oss-distributions/libpthread/blob/libpthread-514.100.2/kern/kern_init.c)
registers its real table through pthread_kext_register. A small in-kernel
EARLY_BOOT adapter calls that entry point before bsd_init and checks the
registered table identity and callbacks pointer. The original NULL-table and
double-registration panic guards remain. Diagnostic messages distinguish
registration from the later return of the real pthread initialization.

Static-link adaptations reuse XNU's existing pthread_kern pointer and its
identical current_uthread helper, avoiding duplicate definitions. Object
filenames are prefixed to avoid BSD's existing kern_synch.o. Integer-address
arguments use explicit uintptr_t/vm_offset_t casts; zero user addresses use
integer zero instead of a C NULL pointer. These retain the original values
with current Clang type checking.

Apple's [kext target configuration](https://github.com/apple-oss-distributions/libpthread/blob/libpthread-514.100.2/xcodescripts/kext.xcconfig)
provides the component defines. The three kext translation units use the
matching XNU's installed Kernel.framework private/public headers, produced by
its normal installhdrs and KPINCFRAME_UNIFDEF machinery. They do not consume raw
BSD/Mach internals. The adapter compiles normally inside BSD with internal
headers. The workflow checks that the private pthread header exists, performs
a full ARM64/MIAMI compile/link, verifies five real implementation symbols,
then validates the kernel payload before upload.

The first full integration run (42235712904) reached the BSD compilation and
reported three missing TargetConditionals.h errors. XNU's -nostdinc build does
not search the SDK's standard include directory. The component now adds the
selected real SDK's usr/include as a system directory, after its pinned kernel
and pthread include paths; the helper checks that platform header exists.
Compiler errors are extracted separately from warning-heavy parallel logs.
The corrected [full build 42239849041](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42239849041)
passed every gate at `51c1948587595f336115c65f0abe5f8c2dc07862`.

Local checks cover fresh staging, pin/match/guard invariants, helper order and
the actual early console. An offline compile using this XNU's exported headers
and minimal SDK platform macros compiled the startup adapter, init and support
translation units. Synchronization requires Apple's __builtin_xnu_type_summary
and __builtin_xnu_type_signature; upstream Linux Clang lacks them. They are
not stubbed or disabled in production. Full Apple Clang/SDK compilation, linking
and five-symbol verification passed. Downloaded ZIP/kernel identity and actual
Mach-O implementation symbols were independently checked.

In a host-only QEMU virt control, the 10-second framebuffer shows real pthread
callback registration and CPU/SGI1 completion. XNU then waits up to 30 seconds
for IORTC. A 45-second control reaches domaininit/tcp_init, which follow the
unconditional pthread_init call in this source. The return from real pthread
initialization is inferred from that later call chain; the completion line is
overwritten in the final panic screen. The later data abort is at
aes_encrypt_key128+0x10 (ESR 0x96000005, FAR 0x78), called for TCP Fast Open.
The g_crypto_funcs provider is the next dependency to investigate. This is not
a full boot or a hardware result for image 0006.

Image 0006 was subsequently accepted by temporary fastboot boot (send 2.281s,
boot 10.487s). Its phone photograph shows a panic report with UUID
AA615D30-075F-3DC8-A494-5AC198E201E6, matching the verified binary's LC_UUID.
Only the middle metadata/zone dump is visible; the reason, exception registers
and backtrace are absent from that photograph. Phone pthread completion and
the phone panic cause remain unconfirmed; the QEMU AES fault is separate evidence.

This remains a single-CPU bring-up. No storage, USB, touch or SMP driver is
added, and testing uses temporary fastboot boot images while preserving Android.
