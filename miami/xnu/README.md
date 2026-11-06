# MIAMI: initial XNU build for Motorola Edge 30 Neo

This is a single-CPU adaptation based on ios-sweet. Probe V5 confirmed 16K
translation and timer IRQs on the boot CPU. The full XNU kernel has not yet
been compiled in CI or booted on miami. This package has no iOS installation.
Read [BRINGUP.md](BRINGUP.md) for implementation details and limitations.

## GitHub Actions

Extract the source bundle into a repository, preserving dotfiles and folders.
It includes required original patches, helper tools, target sources, tests
and license. Device dumps, calibration, firmware, Apple userland and local
build output are excluded.

The manual-only workflow is `.github/workflows/miami-xnu.yml`, named
`miami-xnu`. Place it on the default branch and enable Actions. Run from
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
IORPC adaptation handles the newer iig field; a full CI build must still
verify SDK/generator compatibility. No full CI run has occurred yet.
The workflow needs no phone connection and uses a read-only GITHUB_TOKEN.

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
663906528d1cd5ea8fde7de6f16de73db9511549. This changes those checkouts:

```sh
python3 miami/tests/check-source.py --source /path/to/fresh/xnu --helper /path/to/fresh/helper
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
temporary phone test. The selected upper RAM remains physically untested.

Original inspiration:
[ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb).
