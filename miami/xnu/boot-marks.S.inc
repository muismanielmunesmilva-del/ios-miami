#if defined(MIAMI)
/* Stack-free cold-boot breadcrumbs. The loader validated this 32-bit splash
 * buffer and enabled autorefresh. Each reached stage adds one white 48x24
 * block at y=32, with a 16-pixel gap. Clobbers only x8..x13; no calls, clocks,
 * console state, allocation or implementation-defined register accesses. */
.macro miami_boot_mark args, stage
    ldr x8, [\args, #BA_VIDEO_ROW_BYTES]
    ldr x9, [\args, #BA_VIDEO_BASE]
    add x9, x9, x8, lsl #5
    add x9, x9, #((\stage - 1) * 256)
    mov w10, #-1
    mov x11, #24
Lmiami_mark_row\@:
    mov x13, x9
    mov x12, #48
Lmiami_mark_pixel\@:
    str w10, [x13], #4
    subs x12, x12, #1
    b.ne Lmiami_mark_pixel\@
    add x9, x9, x8
    subs x11, x11, #1
    b.ne Lmiami_mark_row\@
    dsb sy
.endmacro
#endif
