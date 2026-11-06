# First-panic framebuffer diagnostics

The complete [Actions run 42281662142](https://github.com/muismanielmunesmilva-del/ios-miami/actions/runs/42281662142)
passed at `988db79023cdce6805785bcc980b65a2adf07094`. The independently verified
kernel SHA-256 is `842b7d87c6c840bc14d98d42a7e3cf43aaf53321ee6fc26e1a8f1c33f15fe61b`,
UUID `47A0388E-4A7B-3B9B-A5D4-96E5C55468B4`. Four actual defined diagnostic
functions and five pthread implementation symbols were checked in Mach-O.
Linked table storage checks passed. The compiler unrolled the short title
into immediate-character drawing calls; the title is verified at runtime.

In the 45-second QEMU virt GIC/timer control, the first-panic pane survives
the complete native panic report. Its decoded PC `0xfffffe00078f6a88`,
ESR `0x96000005` and FAR `0x78` exactly match QEMU's independent exception
trace; the PC is `aes_encrypt_key128+0x10`. This is host evidence only.

Image 0007 is 100,663,296 bytes, SHA-256
`91fb8caa8782a56e1890b5dc20bacc5982f835a326f17cd0959e171755ed33d2`.
Payload/live-FDT, Android/ARM64 headers, embedded kernel identity and official
AVB verification passed. Temporary fastboot boot was accepted after verifying
exact size/hash and one product `miami`: send 2.277s, boot 10.490s, exit 0.
The later complete phone photograph confirms the protected pane survives the
native report: `Kernel data abort.`, PC `0xfffffe00078f6a88`, LR
`0xfffffe0007669f98`, ESR `0x96000005`, FAR `0x78`. The exact binary identifies
`aes_encrypt_key128+0x10`, reading the NULL crypto-function table at offset120.
Photo SHA-256: `b9c827e17f67065b5639aa493b589297aa5eefade8567e4e6ffc3bef798d00df`.
This is now phone evidence matching the prior host control. See [AES.md](AES.md).

Image 0006's photograph matches the verified kernel UUID and shows a panic,
but the reason and register lines have already been overwritten by the normal
console's ring. The user confirmed that these lines are not visible. The
phone's panic cause remains unknown; the separate host AES abort is not proof
of the phone's failure.

The diagnostic build reserves the top 18 text rows (576 pixels) only
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
