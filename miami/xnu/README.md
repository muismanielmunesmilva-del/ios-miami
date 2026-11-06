# MIAMI: initial XNU build for Motorola Edge 30 Neo

Current status: the complete image0007 phone photo identifies the same AES
data abort seen in the host control, after pthread initialization. The first
panic reason/register pane worked on hardware. The legacy AES-CBC/ECB provider
passed local known-answer tests and the complete Actions42287672552 build.
Its 150-second host control reaches an IOMedia/Apple_HFS root-device wait,
without a visible panic. The image0008 phone photograph now confirms the same
pthread/Skywalk progress and IOMedia/Apple_HFS root wait, with no panic visible.
There is still no mounted root filesystem or iOS userland.
See [AES.md](AES.md) and [PANIC-SCREEN.md](PANIC-SCREEN.md).

## Earlier build history

This is a single-CPU adaptation based on ios-sweet. Probe V5 confirmed 16K
translation and timer IRQs on the boot CPU. The full XNU kernel compiled,
linked and passed payload validation in [the latest Intel-hosted Actions run](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42239849041)
at source commit `51c1948587595f336115c65f0abe5f8c2dc07862`.
The user's image 0004 photograph now confirms XNU execution on miami, platform
expert registration and VM bootstrap completion. It stops without a visible
panic; a complete kernel boot and iOS installation remain unconfirmed.
Temporary loader 0002 reached the pre-branch marker after copying all kernel
segments. That first kernel has a confirmed splash-table alignment defect;
source now aligns overallocated table storage at runtime. The corrected full
build passed in run 42192773280 and progressed through console initialization
in QEMU. Hardware image 0003 still stops at the pre-branch message. The next
diagnostic adds loader readback checks and seven early-entry visual markers.
It now passes the full build and host bootstrap observation; its image 0004
produced XNU-generated hardware output in image 0004. The next source correction
matches the CPU driver to the measured Cortex-A55 ADT node and enables Apple's
startup_debug=1 diagnostics. This build passed; the user now reports the
MIAMI CPU / SGI1 verified message on temporary image 0005. This establishes
the reported single-CPU milestone, not a complete boot or iOS userland.
The subsequent photo of 0005 shows a panic backtrace through pthread_init and
bsd_init. Its panic header is outside the photograph. The exact kernel's LR-4
callsites identify the guard for a missing pthread function table. The next
build integrates Apple's matching pthread kernel implementation; read
[PTHREAD.md](PTHREAD.md). Full compilation/link and independent artifact checks
passed. Host control registers callbacks and subsequently reaches TCP init,
after the real pthread initialization. A later AES data abort remains.
Temporary image 0006 was accepted by fastboot. Its photo shows a panic report
with the verified kernel UUID; the cause and phone pthread completion remain
unconfirmed because the reason, exception registers and backtrace are not visible.
Read [BRINGUP.md](BRINGUP.md) for implementation details and limitations.

## GitHub Actions

Extract the source bundle into a repository, preserving dotfiles and folders.
It includes required original patches, helper tools, target sources, tests
and license. Device dumps, calibration, firmware, Apple userland and local
build output are excluded.

The workflow is `.github/workflows/miami-xnu.yml`, named `miami-xnu`.
It runs on target-code pushes to main and allows manual dispatch. Place it
on the default branch and enable Actions. Run manually from
the Actions tab, or using an authenticated GitHub CLI:

```sh
gh workflow run miami-xnu.yml -R OWNER/REPOSITORY --ref main
gh run list -R OWNER/REPOSITORY --workflow miami-xnu.yml
gh run view RUN_ID -R OWNER/REPOSITORY --log-failed
gh run download RUN_ID -R OWNER/REPOSITORY -n miami-xnu-kernel -D xnu/out-miami
```

Substitute the actual default branch if it is not main. Success produces
kernel.development.miami, payload/ADT, checksums, port/source identities and
toolchain information. Failure diagnostics are in miami-xnu-diagnostics;
their existence alone does not establish success. Retention is seven days.

The build selects macOS 15/Xcode 16.4 and pinned xnu-8796.141.3. A kernel-only
IORPC adaptation handles the newer iig field; the full CI compile/link now
passes with that SDK/generator. Source preparation supports the helper's
Python 3.9.6. Packaging accepts Apple's bounded, read-only, file-only __CTF
debug metadata without copying it into kernel RAM; regression checks pass.
The workflow needs no phone connection and uses a read-only GITHUB_TOKEN.

Verified latest kernel: 15,904,816 bytes, SHA-256
`ed5206231af5a6f9d46f2f690b99b9fea6ccecc905e2ca5801e5f35533b30b8b`.
The downloaded artifact's checksums, source commit, arm64 architecture and
embedded MIAMI ADT were independently verified. Compilation and payload
checks do not establish hardware boot success.

The main workflow now uses the documented macOS 15 Intel runner and the same
Xcode 16.4/ARM64 target that already passed. The optional `miami-xnu-intel.yml`
now runs only on manual dispatch, avoiding duplicate builds.
Both require preinstalled selected Xcode and avoid the unused xcodes installer.

## Local checks (Linux or WSL)

Dependencies: gcc, clang, gcc-aarch64-linux-gnu/binutils, device-tree-compiler,
Python 3, and the pinned dtc source:

```sh
git clone https://github.com/dgibson/dtc.git /path/to/dtc
git -C /path/to/dtc checkout 54e547173bf0f2a4cc35eba8b5738caf38b9230f
python3 miami/tests/check.py --dtc /path/to/dtc
python3 miami/tests/check-console.py
```

For source checks, provide fresh checkouts of Apple XNU commit
1b191cb58250d0705d8a51287127505aa4bc0789 and build-helper commit
663906528d1cd5ea8fde7de6f16de73db9511549, plus libpthread commit
a6c70ca0e544347a0377babf748f831577ec24f9. This changes the XNU/helper checkouts:

```sh
python3 miami/tests/check-source.py --source /path/to/fresh/xnu --helper /path/to/fresh/helper --pthread /path/to/pinned/libpthread --bearssl /path/to/pinned/BearSSL
```

Loader tests use a synthetic Mach-O and compile-only mode. Their output is
not XNU and must not be booted; they generate no Android boot.img.

## Packaging after a successful kernel build

Verify the downloaded artifact checksums. The local builder needs mkbootimg,
official AOSP avbtool.py, pinned dtc and the private live FDT from this phone:

```sh
bash miami/loader/build.sh /path/to/kernel.development.miami /path/to/dtc /path/to/avbtool.py /private/live-recovery.dtb
```

This packages miami/loader/out/boot.img as boot v3 with the verified target
header conventions and a 96-MiB AVB container. It issues no phone commands.
Review kernel identity, build checks and final hash before planning a
temporary phone test. Image 0004/0005 output confirms execution using the
selected RAM bank; it does not establish a comprehensive memory test.

Original inspiration:
[ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).
