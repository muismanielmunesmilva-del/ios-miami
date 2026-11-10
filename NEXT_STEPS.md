# MIAMI Next Concrete Engineering Steps

**Last Updated:** 2026-11-10

## 1. Completed & Verified Milestones on Physical Hardware (Motorola Edge 30 Neo `XT2245-1`)
* **`MIAMI_XNU_0014` (Verified PASS):**
  * Qualcomm UFSHCI 2.1 SCSI read-only storage driver (`bsd/dev/miami_ufs.c` at MMIO `0x04804000`), `/miami-ufs` ADT node, polled SCSI Read(10), GPT partition scanner, devfs `ufsroot0`/`rufsroot0`, and strict read-only partition protection (`EROFS`).
  * Physical boot verified by user: `threads, hfs, sandbox, psynch, amfi entrou tudinho certo` and rapid continuous heartbeats. Zero partition writes issued.
* **`MIAMI_XNU_0015` (Verified PASS):**
  * Native display pipeline (`IOCoreSurfaceRoot` + `AppleCLCD : public IOMobileFramebuffer` on `/arm-io/disp0`), 1080x2400 AMOLED continuous splash mapping at `0x85200000`, 60 Hz VSync timer (`IOTimerEventSource`), user client interfaces (`IOSurfaceRootUserClient`, `IOMobileFramebufferUserClient`), and `/arm-io` nub publisher hook in `SweetPlatformExpert::processTopLevel`.
  * Physical boot verified by user: continuous heartbeats with active display pipeline drivers. Zero partition writes issued.

## 2. Next Milestone: `MIAMI_XNU_0016` (Touchscreen / HID Input Subsystem)
1. **Touchscreen Driver Architecture (`0058-sweet-hid-event-services.patch` & `0062-sweet-touch-power-battery.patch`):**
   * Integrate touch controller / HID event services (`SweetHID.cpp`, `IOHIDEvent.cpp`, `IOHIDEventServiceQueue.cpp`, `IOHIDEventServiceUserClient.cpp`).
   * Match touch input device tree node or polled I2C/SPI touch nub for the Edge 30 Neo digitizer.
   * Expose HID events to userspace clients for multi-touch gestures and button presses.
2. **Userspace Display Client Testing:**
   * Exercise `IOSurfaceRootUserClient` and `IOMobileFramebufferUserClient` from PID1 (`miami-init`) to allocate surfaces and swap frames onto the AMOLED display.
