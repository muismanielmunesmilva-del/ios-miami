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
or download the DMG contents. CI checks only the small manifest using range
requests and does not publish Apple binaries.

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
  None is currently implemented or verified here.
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
