/* Minimal RAM-root PID1 probe. Darwin raw syscalls, no libraries or storage IO.
 * Based on ios-sweet tools/sweet-init.S. Align SP before all stack accesses.
 * All mutable data is on the process stack. Never exits PID1.
 */
#define SYS_write 4
#define SYS_open 5
#define SYS_getpid 20
#define SYS_select 93
.text
.globl _start
.p2align 2
_start:
    mov x9, sp
    and x9, x9, #~15
    mov sp, x9
    adr x0, console_path
    mov x1, #2
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs failed
    mov x19, x0
    mov x16, #SYS_getpid
    svc #0x80
    b.cs failed
    cmp x0, #1
    b.ne wrong_pid
    adr x1, hello
    adr x2, hello_end
    sub x2, x2, x1
    bl write_all
tick:
    sub sp, sp, #16
    mov x5, #5
    stp x5, xzr, [sp]
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    mov x4, sp
    mov x16, #SYS_select
    svc #0x80
    add sp, sp, #16
    b.cs failed
    adr x1, heartbeat
    adr x2, heartbeat_end
    sub x2, x2, x1
    bl write_all
    b tick
wrong_pid:
    adr x1, error_pid
    adr x2, error_pid_end
    sub x2, x2, x1
    bl write_all
failed:
    b failed
write_all:
    stp x20, x21, [sp, #-32]!
    str x30, [sp, #16]
    mov x20, x1
    mov x21, x2
write_more:
    mov x0, x19
    mov x1, x20
    mov x2, x21
    mov x16, #SYS_write
    svc #0x80
    b.cs failed
    cbz x0, failed
    cmp x0, x21
    b.hi failed
    add x20, x20, x0
    subs x21, x21, x0
    b.ne write_more
    ldr x30, [sp, #16]
    ldp x20, x21, [sp], #32
    ret
console_path:
    .asciz "/dev/console"
hello:
    .ascii "\n*** MIAMI USERSPACE: PID=1 (getpid verified) ***\n"
hello_end:
heartbeat:
    .ascii "MIAMI PID1: heartbeat\n"
heartbeat_end:
error_pid:
    .ascii "MIAMI PID1 ERROR: getpid was not 1\n"
error_pid_end:
