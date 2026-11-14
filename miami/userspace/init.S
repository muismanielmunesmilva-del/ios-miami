/* Minimal RAM-root PID1 probe. Darwin raw syscalls, no libraries or storage IO.
 * Based on ios-sweet tools/sweet-init.S. Align SP before all stack accesses.
 * All mutable data is on the process stack. Never exits PID1.
 */
#define SYS_read 3
#define SYS_write 4
#define SYS_open 5
#define SYS_close 6
#define SYS_getpid 20
#define SYS_select 93
#define SYS_mount 167
#define SYS_csops 169
#define SYS_mmap 197
#define SYS_psynch_cvsignal 304
#define SYS_psynch_cvwait 305
#define SYS_bsdthread_create 360
#define SYS_bsdthread_register 366
#define SYS_mac_syscall 381
.text
.globl _start
.p2align 2
_start:
    mov x9, sp
    and x9, x9, #~15
    mov sp, x9
    mov x24, #0               /* optional read-only mount has not run */
    mov x26, #0               /* synthetic root unless real-root node exists */
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
    /* Verify built-in AMFI policy: CS_OPS_STATUS (0) must report
     * CS_VALID (0x1) | CS_PLATFORM_BINARY (0x04000000) | CS_SIGNED
     * (0x20000000). XNU 8796 kern_exec.c does not propagate CS_ADHOC from
     * the CodeDirectory into ip_csflags; build.py verifies it in the file.
     * CS_OPS_ENTITLEMENTS_BLOB (7) must return the embedded XML blob.
     */
    sub sp, sp, #512
    /* Failure stage survives syscalls in callee-saved x22: 1=status syscall,
     * 2=status flags, 3=entitlement syscall, 4=blob header/length,
     * 5=Sandbox op 0, 6=Sandbox op 4. */
    mov x22, #'1'
    str wzr, [sp]
    mov x0, #0
    mov x1, #0
    mov x2, sp
    mov x3, #4
    mov x16, #SYS_csops
    svc #0x80
    b.cs amfi_failed
    mov x22, #'2'
    ldr w9, [sp]
    mov w10, #0x0001
    movk w10, #0x2400, lsl #16
    and w9, w9, w10
    cmp w9, w10
    b.ne amfi_failed
    mov x22, #'3'
    stp xzr, xzr, [sp]
    mov x0, #0
    mov x1, #7
    mov x2, sp
    mov x3, #512
    mov x16, #SYS_csops
    svc #0x80
    b.cs amfi_failed
    mov x22, #'4'
    ldr w9, [sp]
    rev w9, w9
    mov w10, #0x7171
    movk w10, #0xfade, lsl #16
    cmp w9, w10
    b.ne amfi_failed
    ldr w9, [sp, #4]
    rev w9, w9
    cmp w9, #32
    b.ls amfi_failed
    cmp w9, #512
    b.hi amfi_failed
    add sp, sp, #512
    /* Verify built-in permissive Sandbox MAC policy (0050):
     * __mac_syscall("Sandbox", 0, NULL) == 0 and op 4 == ENOENT (2).
     */
    mov x22, #'5'
    adr x0, sandbox_policy
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_mac_syscall
    svc #0x80
    b.cs amfi_no_sp_failed
    cbnz x0, amfi_no_sp_failed
    mov x22, #'6'
    adr x0, sandbox_policy
    mov x1, #4
    mov x2, #0
    mov x16, #SYS_mac_syscall
    svc #0x80
    b.cc amfi_no_sp_failed
    cmp x0, #2
    b.ne amfi_no_sp_failed
    adr x1, amfi_ok
    adr x2, amfi_ok_end
    sub x2, x2, x1
    bl write_all
    b hfs_probe
amfi_failed:
    /* Print the unmasked status on stage 2 without changing the policy. */
    cmp x22, #'2'
    b.ne amfi_restore_stack
    ldr w10, [sp]
    add x11, sp, #496
    adr x12, hex_digits
    mov x13, #0
amfi_hex_loop:
    mov x14, #28
    sub x14, x14, x13, lsl #2
    lsr w15, w10, w14
    and w15, w15, #15
    ldrb w15, [x12, x15]
    strb w15, [x11, x13]
    add x13, x13, #1
    cmp x13, #8
    b.ne amfi_hex_loop
    adr x1, amfi_flags
    adr x2, amfi_flags_end
    sub x2, x2, x1
    bl write_all
    add x1, sp, #496
    mov x2, #8
    bl write_all
    adr x1, amfi_stage_newline
    mov x2, #1
    bl write_all
amfi_restore_stack:
    add sp, sp, #512
amfi_no_sp_failed:
    adr x1, amfi_stage
    adr x2, amfi_stage_end
    sub x2, x2, x1
    bl write_all
    sub sp, sp, #16
    strb w22, [sp]
    mov x1, sp
    mov x2, #1
    bl write_all
    add sp, sp, #16
    adr x1, amfi_stage_newline
    mov x2, #1
    bl write_all
    adr x1, amfi_error
    adr x2, amfi_error_end
    sub x2, x2, x1
    bl write_all
    b tick
/* The special device name exists only with the rootmount=1 diagnostic.
 * Mount over the synthetic RAM root's /etc after its initial marker check.
 * The server image and the block driver both independently reject writes.
 */
mount_probe:
    cbnz x24, mount_return_fast
    stp x25, x30, [sp, #-16]!
    adr x0, mount_device
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cc mount_device_found
    adr x0, real_device
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs mount_return
    mov x26, #1
mount_device_found:
    mov x16, #SYS_close
    svc #0x80
    mov x24, #1
    sub sp, sp, #64
    stp xzr, xzr, [sp]
    stp xzr, xzr, [sp, #16]
    stp xzr, xzr, [sp, #32]
    stp xzr, xzr, [sp, #48]
    adr x9, mount_device
    cbz x26, mount_arg_ready
    adr x9, real_device
mount_arg_ready:
    str x9, [sp]               /* hfs_mount_args.fspec */
    adr x0, mount_type
    adr x1, mount_path
    mov x2, #1                 /* MNT_RDONLY */
    mov x3, sp
    mov x16, #SYS_mount
    svc #0x80
    add sp, sp, #64
    b.cs mount_failed
    adr x1, mount_ok
    adr x2, mount_ok_end
    sub x2, x2, x1
    bl write_all
    cbnz x26, real_root_probe
    adr x0, mounted_marker
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs mount_marker_failed
    mov x25, x0
    sub sp, sp, #32
    mov x0, x25
    mov x1, sp
    mov x2, #19
    mov x16, #SYS_read
    svc #0x80
    b.cs mount_read_failed
    cmp x0, #19
    b.ne mount_read_failed
    adr x10, root_marker_expected
    ldr x11, [sp]
    ldr x12, [x10]
    cmp x11, x12
    b.ne mount_read_failed
    ldr x11, [sp, #8]
    ldr x12, [x10, #8]
    cmp x11, x12
    b.ne mount_read_failed
    ldrh w11, [sp, #16]
    ldrh w12, [x10, #16]
    cmp w11, w12
    b.ne mount_read_failed
    ldrb w11, [sp, #18]
    ldrb w12, [x10, #18]
    cmp w11, w12
    b.ne mount_read_failed
    add sp, sp, #32
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
    adr x1, mount_marker_ok
    adr x2, mount_marker_ok_end
    sub x2, x2, x1
    bl write_all
    adr x0, mounted_marker
    mov x1, #1                 /* O_WRONLY; no write is issued */
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cc mount_write_unexpected
    cmp x0, #30                /* EROFS */
    b.ne mount_write_failed
    adr x1, mount_ro_ok
    adr x2, mount_ro_ok_end
    sub x2, x2, x1
    bl write_all
    b mount_return
mount_write_unexpected:
    mov x16, #SYS_close
    svc #0x80
mount_write_failed:
    adr x1, mount_ro_error
    adr x2, mount_ro_error_end
    sub x2, x2, x1
    bl write_all
    b mount_return
mount_read_failed:
    add sp, sp, #32
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
mount_marker_failed:
    adr x1, mount_marker_error
    adr x2, mount_marker_error_end
    sub x2, x2, x1
    bl write_all
    b mount_return
mount_failed:
    mov x25, x0
    adr x1, mount_error
    adr x2, mount_error_end
    sub x2, x2, x1
    bl write_all
    /* Print the low byte of errno in hexadecimal. */
    sub sp, sp, #16
    adr x9, mount_hex_digits
    lsr x10, x25, #4
    and x10, x10, #15
    ldrb w11, [x9, x10]
    strb w11, [sp]
    and x10, x25, #15
    ldrb w11, [x9, x10]
    strb w11, [sp, #1]
    mov w11, #10
    strb w11, [sp, #2]
    mov x1, sp
    mov x2, #3
    bl write_all
    add sp, sp, #16
mount_return:
    ldp x25, x30, [sp], #16
mount_return_fast:
    ret
/* The real-root test validates file headers without executing Apple binaries. */
real_root_probe:
    adr x0, real_dyld
    bl real_check_macho
    cbnz x0, real_files_failed
    adr x0, real_launchd
    bl real_check_macho
    cbnz x0, real_files_failed
    adr x1, real_files_ok
    adr x2, real_files_ok_end
    sub x2, x2, x1
    bl write_all
    adr x0, real_cache
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs real_cache_failed
    mov x25, x0
    sub sp, sp, #16
    mov x0, x25
    mov x1, sp
    mov x2, #16
    mov x16, #SYS_read
    svc #0x80
    b.cs real_cache_close_failed
    cmp x0, #16
    b.ne real_cache_close_failed
    adr x9, real_cache_magic
    ldp x10, x11, [sp]
    ldp x12, x13, [x9]
    cmp x10, x12
    b.ne real_cache_close_failed
    cmp x11, x13
    b.ne real_cache_close_failed
    add sp, sp, #16
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
    adr x1, real_cache_ok
    adr x2, real_cache_ok_end
    sub x2, x2, x1
    bl write_all
    adr x0, real_launchd
    mov x1, #1
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cc mount_write_unexpected
    cmp x0, #30
    b.ne mount_write_failed
    adr x1, mount_ro_ok
    adr x2, mount_ro_ok_end
    sub x2, x2, x1
    bl write_all
    b mount_return
real_cache_close_failed:
    add sp, sp, #16
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
real_cache_failed:
    adr x1, real_cache_error
    adr x2, real_cache_error_end
    sub x2, x2, x1
    bl write_all
    b mount_return
real_files_failed:
    adr x1, real_files_error
    adr x2, real_files_error_end
    sub x2, x2, x1
    bl write_all
    b mount_return
/* x0 = pathname; x0 returns zero for an arm64 Mach-O magic. */
real_check_macho:
    stp x25, x30, [sp, #-16]!
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs real_macho_fail
    mov x25, x0
    sub sp, sp, #16
    mov x0, x25
    mov x1, sp
    mov x2, #4
    mov x16, #SYS_read
    svc #0x80
    b.cs real_macho_close_fail
    cmp x0, #4
    b.ne real_macho_close_fail
    ldr w9, [sp]
    mov w10, #0xfacf
    movk w10, #0xfeed, lsl #16
    cmp w9, w10
    b.ne real_macho_close_fail
    add sp, sp, #16
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
    mov x0, #0
    b real_macho_done
real_macho_close_fail:
    add sp, sp, #16
    mov x0, x25
    mov x16, #SYS_close
    svc #0x80
real_macho_fail:
    mov x0, #1
real_macho_done:
    ldp x25, x30, [sp], #16
    ret
hfs_probe:
    /* Optional secondary file check on HFS+ root (/etc/miami-root).
     * On single-binary mockfs, open returns ENOTDIR/ENOENT and is skipped.
     */
    adr x0, root_marker_path
    mov x1, #0
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs psynch_test
    mov x20, x0
    sub sp, sp, #32
    stp xzr, xzr, [sp]
    stp xzr, xzr, [sp, #16]
    mov x0, x20
    mov x1, sp
    mov x2, #19
    mov x16, #SYS_read
    svc #0x80
    mov x21, x0
    b.cs hfs_close_fail
    mov x0, x20
    mov x16, #SYS_close
    svc #0x80
    cmp x21, #19
    b.ne hfs_fail
    ldr x9, [sp]
    adr x10, root_marker_expected
    ldr x11, [x10]
    cmp x9, x11
    b.ne hfs_fail
    ldr x9, [sp, #8]
    ldr x11, [x10, #8]
    cmp x9, x11
    b.ne hfs_fail
    ldrh w9, [sp, #16]
    ldrh w11, [x10, #16]
    cmp w9, w11
    b.ne hfs_fail
    ldrb w9, [sp, #18]
    ldrb w11, [x10, #18]
    cmp w9, w11
    b.ne hfs_fail
    add sp, sp, #32
    /* On HFS+ root, /usr/lib/dyld (MH_DYLINKER) runs first via LC_LOAD_DYLINKER,
     * verifies the main binary's mach_header_64 pointer on the stack, sets
     * x28 = 0x44594c44 ("DYLD"), and jumps to _start.
     */
    mov x9, #0x4c44
    movk x9, #0x4459, lsl #16
    cmp x28, x9
    b.ne hfs_no_sp_fail
    adr x1, hfs_ok
    adr x2, hfs_ok_end
    sub x2, x2, x1
    bl write_all
    b psynch_test
hfs_close_fail:
    mov x0, x20
    mov x16, #SYS_close
    svc #0x80
hfs_fail:
    add sp, sp, #32
hfs_no_sp_fail:
    adr x1, hfs_error
    adr x2, hfs_error_end
    sub x2, x2, x1
    bl write_all
    b tick
psynch_test:
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
    bl mount_probe
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
sandbox_policy:
    .asciz "Sandbox"
root_marker_path:
    .asciz "/etc/miami-root"
root_marker_expected:
    .ascii "MIAMI HFS+ ROOT OK\n"
mount_device:
    .asciz "/dev/miamiusbmount0"
real_device:
    .asciz "/dev/miamiusbios0"
mount_type:
    .asciz "hfs"
mount_path:
    .asciz "/etc"
mounted_marker:
    .asciz "/etc/etc/miami-root"
real_dyld:
    .asciz "/etc/usr/lib/dyld"
real_launchd:
    .asciz "/etc/sbin/launchd"
real_cache:
    .asciz "/etc/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64"
real_cache_magic:
    .ascii "dyld_v1   arm64\0"
mount_hex_digits:
    .ascii "0123456789abcdef"
mount_ok:
    .ascii "MIAMI ROOT MOUNT: HFS mounted read-only\n"
mount_ok_end:
mount_marker_ok:
    .ascii "MIAMI ROOT MOUNT: remote marker verified\n"
mount_marker_ok_end:
mount_ro_ok:
    .ascii "MIAMI ROOT MOUNT: write open rejected EROFS\n"
mount_ro_ok_end:
mount_error:
    .ascii "MIAMI ROOT MOUNT: mount failed errno=0x"
mount_error_end:
mount_marker_error:
    .ascii "MIAMI ROOT MOUNT: marker read failed\n"
mount_marker_error_end:
mount_ro_error:
    .ascii "MIAMI ROOT MOUNT: write-open check failed\n"
mount_ro_error_end:
real_files_ok:
    .ascii "MIAMI IOS ROOT: dyld and launchd Mach-O magic verified\n"
real_files_ok_end:
real_files_error:
    .ascii "MIAMI IOS ROOT: dyld or launchd read failed\n"
real_files_error_end:
real_cache_ok:
    .ascii "MIAMI IOS ROOT: dyld cache header verified\n"
real_cache_ok_end:
real_cache_error:
    .ascii "MIAMI IOS ROOT: dyld cache read failed\n"
real_cache_error_end:
hello:
    .ascii "\n*** MIAMI USERSPACE: PID=1 (getpid verified) ***\n"
hello_end:
amfi_ok:
    .ascii "MIAMI AMFI: platform binary, XML entitlements and Sandbox verified\n"
amfi_ok_end:
amfi_error:
    .ascii "MIAMI AMFI ERROR: csops, entitlements or Sandbox check failed\n"
amfi_error_end:
amfi_stage:
    .ascii "MIAMI AMFI failure stage: "
amfi_stage_end:
amfi_stage_newline:
    .ascii "\n"
amfi_flags:
    .ascii "MIAMI AMFI csflags=0x"
amfi_flags_end:
hex_digits:
    .ascii "0123456789abcdef"
hfs_ok:
    .ascii "MIAMI HFS+: /usr/lib/dyld and /etc/miami-root verified\n"
hfs_ok_end:
hfs_error:
    .ascii "MIAMI HFS+ ERROR: /usr/lib/dyld or /etc/miami-root check failed\n"
hfs_error_end:
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
