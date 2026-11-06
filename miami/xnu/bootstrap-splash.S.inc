#if defined(MIAMI)
    /* A separate L3 maps ONLY the measured 12-MiB splash reservation.
     * Both kernel PA (6 GiB) and splash have L1 index zero with 16K pages.
     * Find the identity L2 from its descriptor instead of guessing its page.
     */
    adrp    x10, EXT(miami_boot_splash_l3)@page
    add     x10, x10, EXT(miami_boot_splash_l3)@pageoff
    mov     x11, x10
    mov     x12, #2048
Lmiami_zero_splash:
    str     xzr, [x11], #8
    subs    x12, x12, #1
    b.ne    Lmiami_zero_splash
    MOV64   x11, 0x85200000
    MOV64   x12, 0x85e00000
    MOV64   x13, (ARM_TTE_TYPE_TABLE | ARM_TTE_VALID | ARM_TTE_BLOCK_SH(SH_OUTER_MEMORY) | ARM_TTE_BLOCK_ATTRINDX(CACHE_ATTRINDX_WRITECOMB) | ARM_TTE_BLOCK_AF | ARM_TTE_BLOCK_PNX | ARM_TTE_BLOCK_NX)
Lmiami_map_splash:
    and     x8, x11, #0x1ffffff
    lsr     x8, x8, #14
    orr     x9, x11, x13
    str     x9, [x10, x8, lsl #3]
    add     x11, x11, #4, lsl #12
    cmp     x11, x12
    b.lo    Lmiami_map_splash
    ldr     x11, [x25]  // PA 0x85200000 has L1 index zero
    and     x11, x11, #(ARM_TTE_TABLE_MASK)
    MOV64   x12, 0x84000000
    lsr     x12, x12, #25
    orr     x10, x10, #(ARM_TTE_TYPE_TABLE | ARM_TTE_VALID)
    str     x10, [x11, x12, lsl #3]
#endif
