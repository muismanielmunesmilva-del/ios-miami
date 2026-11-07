/* Minimal RAM-root PID1 probe. Darwin raw syscalls, no libraries or storage IO.
 * Based on ios-sweet tools/sweet-init.S. Align SP before all stack accesses.
 * All mutable data is on the process stack. Never exits PID1.
 */
#define SYS_write 4
#define SYS_open 5
#define SYS_getpid 20
#define SYS_select 93
#define SYS_psynch_cvwait 305
#define SYS_psynch_cvsignal 304
#define SYS_bsdthread_create 360
#define SYS_bsdthread_register 366
#define SYS_mmap 197
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
    /* Exercise the pthread wait queue with a bounded timeout and no mutex.
     * Darwin's psynch_cvwait accepts 8 arguments in x0..x7. A sequence of
     * one increment and a private, stack-backed condition value reaches
     * ksyn_wait; this empty queue times out with ETIMEDOUT | ECVCLEARED
     * (0x3c | 0x100), as the paired libpthread's psynch_cvcontinue specifies.
     */
    sub sp, sp, #16
    stp xzr, xzr, [sp]
    mov x0, sp
    mov x1, #256
    mov x2, #0
    mov x3, #0
    mov x4, #0
    mov x5, #0
    mov x6, #0
    mov x7, #0xe100
    movk x7, #0x5f5, lsl #16
    mov x16, #SYS_psynch_cvwait
    svc #0x80
    add sp, sp, #16
    b.cc psynch_failed
    cmp x0, #0x13c
    b.ne psynch_failed
    adr x1, psynch_ok
    adr x2, psynch_ok_end
    sub x2, x2, x1
    bl write_all
    b thread_test
psynch_failed:
    adr x1, psynch_error
    adr x2, psynch_error_end
    sub x2, x2, x1
    bl write_all
    b tick
thread_test:
    /* Private condition and result flag stay on PID 1's writable stack. */
    sub sp, sp, #32
    stp xzr, xzr, [sp]
    mov x21, sp
    /* Independent 64 KiB anonymous stack for the second thread. */
    mov x0, #0
    mov x1, #0x10000
    mov x2, #3
    mov x3, #0x1002
    mov x4, #-1
    mov x5, #0
    mov x16, #SYS_mmap
    svc #0x80
    b.cs thread_failed
    mov x22, x0
    adr x0, signal_thread
    mov x1, #0
    mov x2, #0
    mov x3, #0
    mov x4, #0
    mov x5, #0
    mov x6, #0
    mov x16, #SYS_bsdthread_register
    svc #0x80
    b.cs thread_failed
    mov x0, #0
    mov x1, x21
    add x2, x22, #0x10, lsl #12
    mov x3, #0
    mov x4, #0x1000000
    mov x16, #SYS_bsdthread_create
    svc #0x80
    b.cs thread_failed
    mov x0, x21
    mov x1, #256
    mov x2, #0
    mov x3, #0
    mov x4, #0
    mov x5, #0x20
    mov x6, #2
    mov x7, #0
    mov x16, #SYS_psynch_cvwait
    svc #0x80
    b.cs thread_failed
    /* Wait for the signaler's result without depending on execution order. */
    mov x23, #100
thread_check:
    add x9, x21, #8
    ldar x10, [x9]
    cmp x10, #1
    b.eq thread_passed
    cbnz x10, thread_failed
    sub sp, sp, #16
    mov x9, #10000
    stp xzr, x9, [sp]
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    mov x4, sp
    mov x16, #SYS_select
    svc #0x80
    add sp, sp, #16
    subs x23, x23, #1
    b.ne thread_check
thread_failed:
    adr x1, thread_error
    adr x2, thread_error_end
    sub x2, x2, x1
    bl write_all
    /* A created child might still access this shared stack object. Keep it
     * reserved on failure until PID 1 exits, rather than reuse it. */
    b tick
thread_passed:
    adr x1, thread_ok
    adr x2, thread_ok_end
    sub x2, x2, x1
    bl write_all
    add sp, sp, #32
    b tick
/* bsdthread_create supplies user_funcarg in x3 and a private stack. */
signal_thread:
    mov x20, x3
    sub sp, sp, #16
    mov x9, #0xd090
    movk x9, #3, lsl #16
    stp xzr, x9, [sp] /* 250000 microseconds */
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    mov x4, sp
    mov x16, #SYS_select
    svc #0x80
    add sp, sp, #16
    b.cs signal_failed
    mov x0, x20
    mov x1, #256
    mov x2, #0
    mov x3, #0
    mov x4, #0
    mov x5, #0
    mov x6, #0
    mov x7, #0x20
    mov x16, #SYS_psynch_cvsignal
    svc #0x80
    b.cs signal_failed
    /* An increment confirms the signal found a waiting thread, not prepost. */
    and w9, w0, #0xffffff00
    cmp w9, #256
    b.ne signal_failed
    mov x10, #1
    b signal_store
signal_failed:
    mov x10, #2
signal_store:
    add x9, x20, #8
    stlr x10, [x9]
signal_idle:
    sub sp, sp, #16
    mov x9, #5
    stp x9, xzr, [sp]
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    mov x4, sp
    mov x16, #SYS_select
    svc #0x80
    add sp, sp, #16
    b signal_idle
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
psynch_ok:
    .ascii "MIAMI PSYNCH: cvwait timed out as expected\n"
psynch_ok_end:
psynch_error:
    .ascii "MIAMI PSYNCH ERROR: unexpected cvwait result\n"
psynch_error_end:
thread_ok:
    .ascii "MIAMI THREADS: waiting thread signaled successfully\n"
thread_ok_end:
thread_error:
    .ascii "MIAMI THREADS ERROR: signal test failed\n"
thread_error_end:
