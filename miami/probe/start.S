/* SPDX-License-Identifier: MIT
 * AArch64 Linux Image ABI; position independent, linked at zero.
 */
.section .text.head, "ax"
.global _head
_head:
    b entry
    .long 0
    .quad 0
    .quad _end
    .quad 0xc /* LE, 16K pages, placement independent */
    .quad 0, 0, 0
    .ascii "ARM\x64"
    .long 0
.text
entry:
    msr daifset, #0xf
    mov x19, x0
    msr spsel, #1
    adr x1, _stack_top
    mov sp, x1
    adr x1, vectors
    mrs x2, CurrentEL
    cmp x2, #4
    b.eq 1f
    cmp x2, #8
    b.ne halt
    msr vbar_el2, x1
    b 2f
1:  msr vbar_el1, x1
2:  isb
    adr x1, _bss_start
    adr x2, _bss_end
3:  cmp x1, x2
    b.hs 4f
    str xzr, [x1], #8
    b 3b
4:  mov x0, x19
    bl probe_main
halt:
    wfe
    b halt
.balign 2048
.global vectors
vectors:
.macro vector slot
    sub sp, sp, #256
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]
    stp x8, x9, [sp, #64]
    stp x10, x11, [sp, #80]
    stp x12, x13, [sp, #96]
    stp x14, x15, [sp, #112]
    stp x16, x17, [sp, #128]
    stp x18, x19, [sp, #144]
    stp x20, x21, [sp, #160]
    stp x22, x23, [sp, #176]
    stp x24, x25, [sp, #192]
    stp x26, x27, [sp, #208]
    stp x28, x29, [sp, #224]
    str x30, [sp, #240]
    mov x0, #\slot
    b vector_common
    .balign 128
.endm
.set slot_number, 0
.rept 16
    vector slot_number
    .set slot_number, slot_number + 1
.endr
.global vector_common
vector_common:
    bl probe_exception
    cbz w0, halt
    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    ldp x8, x9, [sp, #64]
    ldp x10, x11, [sp, #80]
    ldp x12, x13, [sp, #96]
    ldp x14, x15, [sp, #112]
    ldp x16, x17, [sp, #128]
    ldp x18, x19, [sp, #144]
    ldp x20, x21, [sp, #160]
    ldp x22, x23, [sp, #176]
    ldp x24, x25, [sp, #192]
    ldp x26, x27, [sp, #208]
    ldp x28, x29, [sp, #224]
    ldr x30, [sp, #240]
    add sp, sp, #256
    eret
