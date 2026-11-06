# Matching Apple pthread kernel component

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
The corrected full build is pending.

Local checks cover fresh staging, pin/match/guard invariants, helper order and
the actual early console. An offline compile using this XNU's exported headers
and minimal SDK platform macros compiled the startup adapter, init and support
translation units. Synchronization requires Apple's __builtin_xnu_type_summary
and __builtin_xnu_type_signature; upstream Linux Clang lacks them. They are
not stubbed or disabled in production. Full Apple-compiler verification and
runtime testing are pending.

This remains a single-CPU bring-up. No storage, USB, touch or SMP driver is
added, and testing uses temporary fastboot boot images while preserving Android.
