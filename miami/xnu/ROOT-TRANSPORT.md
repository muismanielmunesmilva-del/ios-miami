# Real iOS root: investigation, not yet an implementation

The phone has reported that image0011 runs the bounded PSYNCH signal probe.
The current `mockfs` root exposes one static Mach-O and is limited to 64 KiB.
It cannot mount the filesystem used by real launchd or dyld. MIAMI currently
declares 0x3ff00000 bytes of usable RAM in its XNU handoff, plus a reserved
1 MiB panic area; this is not a measurement of all RAM in the phone.

The Apple-hosted iPhone10,3/iPhone10,6 iOS 16.7.16 restore manifest identifies
the OS image `087-86698-044.dmg` (4,730,814,044 bytes), SystemOS cryptex
`087-86593-047.dmg` (2,743,074,816 bytes), and AppOS cryptex
`087-86715-047.dmg` (10,485,760 bytes). These are container sizes, not proven
resident memory or extracted filesystem sizes. The ipsw inventory checks the
manifest's pinned SHA-256 and d22ap Update identity; it does not authenticate
or download the DMG contents. Separately, all three local DMGs were fetched
from the Apple-hosted archive, passed ZIP CRC-32 and matched the SHA-384
digests in the pinned manifest. This is digest verification against that
manifest; the manifest's Apple signature has not been independently verified.
CI checks only the small manifest using range requests and does not publish
Apple binaries.

Read-only local APFS inspection found plain-arm64 `launchd` (541,600 bytes)
and `dyld` (922,912 bytes). The former names `/usr/lib/dyld` as its loader
and imports `libSystem.B.dylib` and `libobjc.A.dylib`; neither executable
fits the current 64 KiB mockfs probe limit. Their CodeDirectory SHA-256 page
hashes were independently checked (127 and 220 pages respectively), but
neither CMS signatures nor Apple trust chains were verified. Local inspection
staging contains these two files only and is explicitly marked not bootable.

The SystemOS dyld cache directory contains 44 entries totalling 3,330,359,296
logical bytes, including a 592,101,376-byte symbols file. These are measured
file sizes, not proof that every file or byte is required at runtime. A minimal
dependency closure and its memory/storage requirements remain unmeasured.
APFS was read locally using the GPL-licensed apfs-fuse at commit
`66b86bd525e8cb90f9012543be89b1f092b75cf3`; no code or Apple binaries from
that inspection are shipped in this repository.

The ios-sweet root builder normally constructs a 16 GiB HFS+ image from the
OS and cryptexes, using apfs-fuse, mkfs.hfsplus, rsync and privileged mounts.
It uses userdata for its UFS root. That route is not authorized on MIAMI:
Android and its data must be preserved. No MIAMI storage driver is staged.

Possible approaches require further evidence:

* A reduced RAM root needs a measured dependency closure including dyld and
  its shared cache, a real filesystem implementation and a verified memory
  layout. It must fit without overwriting firmware reservations or the kernel.
* A read-only external USB root needs a working MIAMI USB host controller,
  mass-storage and filesystem stack, and a separately supplied external medium.
  None is currently implemented or verified here. The supplied Motorola
  firmware device tree names a Synopsys DWC3 controller and `dr_mode = "otg"`;
  this is Android firmware description, not a successful XNU host-mode test.
  [UniXNU QcomDwc3](https://github.com/UniXNU/QcomDwc3) is a potentially useful
  reference, but targets SM8550/iPadOS 27 and relies on Apple USB controller
  classes. Its authors report host mode as partial and peripheral enumeration
  unverified. Its PHY files have GPL-2.0-only licensing. Compatibility with
  SM6375/iOS 16, PHY sequencing, power, DMA/SMMU and licensing require separate
  investigation; no code has been copied or enabled from it.
* A network root similarly needs working network and filesystem drivers. No
  functional MIAMI network device is available to the current XNU build.

Do not flash, repartition, format or use Android userdata for these experiments.
First measure the actual executable and shared-cache dependencies from the
pinned Apple source, establish a bounded transport and test it independently.
Compiling the existing kernel or parsing the restore manifest does not establish
that real launchd or iOS can start. No new phone image is prepared by this work.

References: [ios-sweet root builder](https://github.com/dipa-studio/ios-sweet/blob/45263bee51df4a0f55cdf9c649af886399488ddb/tools/mkiosroot.sh),
[Apple XNU memory devices](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/dev/memdev.c),
and [Apple iOS 16.7.16 release](https://developer.apple.com/news/releases/?id=05112026j).
