# Single-CPU XNU adaptation for miami

Image 0005's subsequent photograph confirms a kernel panic backtrace. Its header
is outside the frame. Exact-kernel LR-4 symbolication reaches pthread_init's
missing-function-table guard, then bsd_init. The matching Apple libpthread kernel
component is now staged for a full build; see [PTHREAD.md](PTHREAD.md). The original
panic and callback-registration guards remain active. Build/runtime verification
of the new integration is still pending; Android remains preserved.

Latest, 2026-11-06: [run 42202366971, attempt 2](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42202366971)
passed all validation/build/package gates at `a98a0f89afc60886943faf9436ef313ccc360525`.
Downloaded artifact identity, CPU compatible, startup_debug and linked table
alignment passed independent checks. A host-only QEMU virt control with its
own GIC/timer ADT values now shows CPU registration, SGI1 verification and BSD
MAC Framework initialization. Production ADT addresses remain for SM6375.
On temporary image 0005, the user reports "MIAMI CPU / SGI1 verified"; the exact
full line and a photograph are not yet available. This is reported single-CPU
hardware progress, not a complete boot. Await the last subsequent screen line.

Status, 2026-11-05: [Actions run #3](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42165337842)
passed validation, full macOS compile/link, real payload validation and upload
at source commit `1574a19bf2b95dc2563a1a3d89a81ff99e77b223`.
The artifact was downloaded and its checksums and identities independently
verified. The later image 0004 photo now confirms XNU console execution on the
phone, platform expert registration, VM bootstrap completion and IOMD ownership
initialization. The user reports a stationary screen without panic; this is not
a complete boot. The final subsystem-line prefix is not fully legible.

CPU personality audit found an inherited qcom,kryo470 match while our CPU ADT
published ARM,v8. The correction uses a shared arm,cortex-a55 compatible derived
from the measured boot CPU MIDR, retaining ARM,v8 as fallback. Only the match
string and diagnostic CPU name change; one-CPU, topology and SGI self-test checks
remain active. This is a concrete mismatch, not proof of the stall's cause.
Apple's existing startup_debug=1 boot argument adds the next-stage logs.

Temporary image 0002 subsequently reached its pre-XNU-branch message on the
phone: all three loader validators returned 0 and segment copy markers 0..9
are photo-confirmed. That attempt showed no XNU-generated stage marker. Host bootstrap
analysis of that compiled kernel found the added splash tables at offsets
0x3000 (bootstrap) and 0x2000 (final) inside 16K pages, despite the source's
aligned(16384) declarations. QEMU Cortex-A55 reached the first early-console
marker and raised a level-3 translation fault on its framebuffer write. QEMU
virt is not a model of this phone; this identifies a real binary defect but
does not by itself establish the hardware failure's cause.

The correction reserves 32K for each 16K table and rounds its runtime address
up to the next 16K boundary, including a physical-address alignment assertion
for the final table. Regression tests execute the actual final mapping function
with six deliberately misaligned backing offsets and verify all leaves and
untouched guards. [The corrected full build](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42192773280)
passed at `02467e8f6b3170bb90fddfd6c4513e26e82c01c4`. Download hashes and
linked storage bounds/alignment passed. QEMU then initialized the console and
reached the target GIC code before a target-MMIO abort; virt does not model the
SM6375 GIC layout. The phone's temporary image 0003 still shows only the loader's
pre-branch message, according to the user. Image 0004 subsequently confirmed
XNU console execution on the phone as described above.

Diagnostic image 0004 added complete segment/zero-tail readback and critical
boot-argument readback to loader 0004. Seven stack-free assembly markers add
white blocks at y=32 in the validated splash buffer. Their boot-argument field
offsets come from genassym; they touch no clock or storage registers.

| White blocks reached | Cold-boot milestone |
| --- | --- |
| 1 | start_first_cpu reached, before OSLAR |
| 2 | early physical exception vector installed |
| 3 | boot memory parameters read, before virtual stack selection |
| 4 | bootstrap and splash tables populated |
| 5 | translation registers set, before enabling MMU |
| 6 | MMU-enable instruction and following ISB completed |
| 7 | about to enter arm_init |

The markers use x8..x13 only and make no function call or stack access. Later
console output can overwrite them. Source checks and a fresh full kernel build
must pass before this diagnostic is booted on the phone. These checks now PASS
in [Intel run 42198284206](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42198284206),
commit `cdd0f604e5fe08b7e9e7e2a57539a0ec2ff37f2c`. Independent artifact and linked
table checks pass; QEMU reaches console initialization through the marker path
before its target-MMIO panic. Real image 0004 is packaged and verified; its
hardware photo now confirms progress through VM bootstrap. Readback guards must
have passed by control flow, but their numeric lines and the early blocks were
overwritten before the photo and are not independent transcriptions.

## Adaptation

`prepare.py` checks Apple's exact xnu-8796.141.3 commit
`1b191cb58250d0705d8a51287127505aa4bc0789`, requires all 18 initial ios-sweet
patches, and stages them under the MIAMI namespace. Required patch rejection
is fatal; target edits require exact anchors. Use a fresh pinned checkout.
Later SWEET UFS, PMIC, touch, USB, SMP and display-service drivers are excluded.

MAX_CPUS=1. The Apple Device Tree describes MPIDR affinity zero, GICD
0x0f200000/0x10000, GICR 0x0f240000/0x100000 and virtual timer INTID 19
at 19.2 MHz. CPU/bus diagnostic rates use defaults from XNU's
pe_identify_machine.c, not measured frequencies; they do not program clocks.
There is no iPhone identity or Apple userland in this stage.

`miami/loader/` validates segment sources/destinations, overlaps, entry address,
ADT and boot arguments before copying. It checks the live target FDT, fixed,
memreserve and dynamic RAM reservations, plus current Image/FDT/initrd overlap.
There is no storage driver, CPU_ON call or reset write. The payload is embedded
in the Image, avoiding reliance on an untested ABL initrd transfer.

Kernel RAM is initially [0x180000000,0x1bff00000), with the following 1 MiB
reserved for panic logging. The live FDT permits this carve-out. Image 0004's
XNU console and VM bootstrap output establish execution using this bank;
they do not establish a comprehensive RAM test. Probe V5 tested only private
memory inside its loaded Image. Kernel bring-up remains experimental.

The loader validates ABL's active framebuffer and requires SDE autorefresh.
It patches video address, extent and stride into the ADT and boot arguments.
Bootstrap and final 16K tables map only [0x85200000,0x85e00000) as Normal-NC/XN.
The early console uses the validated video state and its final VA alias.
The target no longer writes/maps the old fixed 0x9c000000 framebuffer.

## Toolchain

The helper is pinned to blacktop/darwin-xnu-build
`663906528d1cd5ea8fde7de6f16de73db9511549`. `configure-helper.py` inserts
required MIAMI preparation between source fetch and helper patch/header
processing, and enables plain arm64 firehose. Applicable generic helper
patches remain available.

The `.github/workflows/miami-xnu.yml` validates target-code pushes or manual
dispatches on Ubuntu 24.04,
then selects macOS 15/Xcode 16.4 and builds DEVELOPMENT/ARM64/MIAMI. It validates
the real payload copy plan before uploading kernel/payload/checksum artifacts;
failure logs are retained separately. It has no phone commands.

Xcode 16 iig uses the kernel-only IORPC.kernelContent field in Apple's later
XNU. The adaptation adds this field to both exported headers and populates it
at the old runtime's dispatch boundaries. Userspace IORPC layout is unchanged;
all kernel objects must rebuild together. The complete generated-iig/SDK
compile/link passed on Xcode 16.4 / Apple clang 17.0.0, macOS 15.8.2 arm64.
Runtime dispatch compatibility remains untested.

The first run exposed the helper's Python 3.9.6: source writers now use explicit
UTF-8 bytes instead of the newer Path.write_text newline argument. The second
run compiled successfully but exposed Apple's file-only __CTF debug segment
during packaging. The validator now permits only bounded, read-only __CTF with
zero VM size; it is excluded from loaded segments. Regression fixtures reject
other zero-VM data and executable __CTF. The third run passed every gate.

## Local evidence

* Loader: valid payload accepted; 11 malformed/truncated payloads rejected;
  one-CPU ADT serialized; four reservation/bank failures rejected; >2-MiB
  synthetic payload cross-compiled and linked for AArch64. Image header, 16K
  size alignment and absence of unresolved relocations passed.
* The private live FDT passed upper-RAM reservation analysis.
* Console: bootstrap fragment compiled as Darwin arm64 assembly; the actual
  final-table function, executed with mocked table access, mapped exactly
  768 Normal-NC/XN splash pages and no other leaves.
* Fresh pinned-source staging passed; the actual early console compiled as
  Darwin arm64 C with minimal external API declarations.
* The Actions YAML and loader shell passed actionlint and shellcheck.

These local checks supplement the successful full CI build; none is a hardware test.
`miami/loader/out/` contains a SYNTHETIC test Image/ELF, not XNU. It is ignored
and excluded from delivery. No Android boot.img was generated by the tests.
The old reference-stage.json describes the earlier SWEET audit; new MIAMI
builds generate miami-source.json with required input/target patch hashes.

Next: record the last screen line after image 0005's reported CPU/SGI milestone
and use the new startup logs to identify the next blocking stage. Image 0005
has already been packaged, independently checked and temporarily booted. It
retains loader version 0004 and adds startup_debug=1 in the new kernel payload.
Images 0001 through 0005 have been temporarily started; image 0004 provides
the photographic console evidence described above. Preserve Android.

## Primary references

* [Apple XNU 8796](https://github.com/apple-oss-distributions/xnu/tree/xnu-8796.141.3)
* [Later IORPC field](https://github.com/apple-oss-distributions/xnu/blob/xnu-11215.81.4/iokit/IOKit/IORPC.h)
* [Later dispatch implementation](https://github.com/apple-oss-distributions/xnu/blob/xnu-11215.81.4/iokit/Kernel/IOUserServer.cpp)
* [Pinned build helper](https://github.com/blacktop/darwin-xnu-build/tree/663906528d1cd5ea8fde7de6f16de73db9511549)
* [macOS 15 runner inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md)
* [macOS 14 retirement](https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement/)
* [AArch64 boot ABI](https://docs.kernel.org/arch/arm64/booting.html)
