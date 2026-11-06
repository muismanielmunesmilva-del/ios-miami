# First-panic framebuffer diagnostics

Image 0006's photograph matches the verified kernel UUID and shows a panic,
but the reason and register lines have already been overwritten by the normal
console's ring. The user confirmed that these lines are not visible. The
phone's panic cause remains unknown; the separate host AES abort is not proof
of the phone's failure.

The next diagnostic build reserves the top 18 text rows (576 pixels) only
after the first panic. Normal serial output continues below them. It captures
the valid 64-bit saved state at Apple's `panic_with_thread_kernel_state`
before the existing native panic call: reason, PC, LR, ESR, FAR, SP and FP.
Other panic paths preserve the formatted reason and caller and explicitly
say that saved registers are unavailable. A later panic cannot replace the
first capture. The normal panic/reporting path and all guards remain intact.

The capture uses the already mapped framebuffer, with the persistent early
alias as fallback. It works after the early console is disabled. It neither
allocates memory nor acquires locks, accesses storage or resets the device.
This build remains single CPU. It does not fix or bypass the crypto-provider
dependency observed in the host control.

`check-panic.py` executes the staged C code and serial functions against
guarded framebuffer memory using Apple's real font. It decodes the rendered
pixels back into text and verifies exact reason/register values, generic
formatting without consuming the original arguments, 10,000 serial lines,
early-console wrap, reinitialization, nested panic, padded stride, long reason
clipping and invalid framebuffer rejection. Only ARM barriers and the external
formatting API are replaced for host execution. The actual early-console C
also compiles as freestanding Darwin arm64 with warnings as errors. These
checks do not replace the full macOS kernel build or a physical phone test.

Primary source integration points:

- [Apple XNU 8796.141.3 exception handling](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm64/sleh.c)
- [Apple XNU 8796.141.3 panic handling](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/kern/debug.c)
