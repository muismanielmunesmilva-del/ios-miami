#!/usr/bin/env python3
"""Exercise fork/chroot/exec/wait control flow with simulated Darwin syscalls."""
import re
import subprocess
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_INTR, UC_HOOK_CODE
from unicorn.arm64_const import *

src = Path(__file__).resolve().parents[1] / 'userspace' / 'init.S'
obj, raw = '/tmp/miami-init-flow.o', '/tmp/miami-init-flow.bin'
subprocess.run(['clang', '-target', 'aarch64-linux-gnu', '-c', str(src), '-o', obj], check=True)
subprocess.run(['aarch64-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', obj, raw], check=True)
nm = subprocess.check_output(['aarch64-linux-gnu-nm', '-n', obj], text=True)
symbols = {m.group(2): int(m.group(1), 16) for m in re.finditer(r'^([0-9a-f]+)\s+\w\s+(\w+)$', nm, re.M)}
code = Path(raw).read_bytes()
BASE, STOP, STACK = 0x100000, 0x300000, 0x400000

def cstring(uc, ptr):
    out = bytearray()
    while True:
        b = bytes(uc.mem_read(ptr + len(out), 1))
        if b == b'\0': return out.decode()
        out += b

def run(entry, scenario):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(BASE, 0x10000); uc.mem_write(BASE, code)
    uc.mem_map(STOP, 0x1000); uc.mem_map(STACK, 0x10000)
    uc.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
    uc.reg_write(UC_ARM64_REG_X30, STOP)
    uc.reg_write(UC_ARM64_REG_X19, 3)
    if scenario.startswith('pid1'):
        uc.reg_write(UC_ARM64_REG_X23, 2)
        uc.mem_write(STACK + 0x8000, (0).to_bytes(8, 'little') + STOP.to_bytes(8, 'little'))
    uc.reg_write(UC_ARM64_REG_X28, 42 if entry == 'launchd_child_poll' else 0)
    calls, output = [], bytearray()
    def stop_on_return(u, addr, size, user):
        if addr == STOP: u.emu_stop()
    def syscall(u, interrupt, user):
        n = u.reg_read(UC_ARM64_REG_X16)
        x0, x1, x2 = (u.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
        calls.append(n)
        # Clear carry by default; explicitly set it for simulated failures.
        u.reg_write(UC_ARM64_REG_NZCV, 0)
        if n == 2:
            u.reg_write(UC_ARM64_REG_X0, 42)
            u.reg_write(UC_ARM64_REG_X1, 1 if scenario.startswith('child') else 0)
            if scenario.startswith('child'): u.reg_write(UC_ARM64_REG_NZCV, 0x20000000)
            if scenario == 'fork_fail':
                u.reg_write(UC_ARM64_REG_X0, 11); u.reg_write(UC_ARM64_REG_NZCV, 0x20000000)
        elif n == 4:
            output.extend(bytes(u.mem_read(x1, x2))); u.reg_write(UC_ARM64_REG_X0, x2)
        elif n == 90:
            assert x0 == 3 and x1 in (1, 2); u.reg_write(UC_ARM64_REG_X0, x1)
        elif n == 61:
            assert cstring(u, x0) == '/etc'
            if scenario in ('child_chroot_fail', 'pid1_chroot_fail'):
                u.reg_write(UC_ARM64_REG_X0, 13); u.reg_write(UC_ARM64_REG_NZCV, 0x20000000)
            else: u.reg_write(UC_ARM64_REG_X0, 0)
        elif n == 12:
            assert cstring(u, x0) == '/'; u.reg_write(UC_ARM64_REG_X0, 0)
        elif n == 59:
            assert cstring(u, x0) == '/sbin/launchd'
            assert int.from_bytes(u.mem_read(x1, 8), 'little') == x0
            assert int.from_bytes(u.mem_read(x1 + 8, 8), 'little') == 0
            assert int.from_bytes(u.mem_read(x2, 8), 'little') == 0
            if scenario in ('child_exec_fail', 'pid1_exec_fail'):
                u.reg_write(UC_ARM64_REG_X0, 2); u.reg_write(UC_ARM64_REG_NZCV, 0x20000000)
            else: u.emu_stop()
        elif n == 7:
            assert x0 == 42 and x2 == 1
            if scenario == 'wait_exited':
                u.mem_write(x1, (0x7e00).to_bytes(4, 'little')); u.reg_write(UC_ARM64_REG_X0, 42)
            else: u.reg_write(UC_ARM64_REG_X0, 0)
        elif n == 1:
            assert x0 == 126; u.emu_stop()
        else: raise AssertionError(f'unexpected syscall {n}')
    uc.hook_add(UC_HOOK_INTR, syscall); uc.hook_add(UC_HOOK_CODE, stop_on_return)
    uc.emu_start(BASE + symbols[entry], STOP + 4, count=100000)
    return uc, calls, output.decode()

u, calls, out = run('launchd_child_start', 'parent')
assert calls == [2, 4] and u.reg_read(UC_ARM64_REG_X28) == 42 and 'child started' in out
u, calls, out = run('launchd_child_start', 'fork_fail')
assert calls == [2, 4] and u.reg_read(UC_ARM64_REG_X28) == 0 and 'fork failed' in out
u, calls, out = run('launchd_child_start', 'child_ok')
assert calls == [2, 90, 90, 4, 61, 12, 4, 59] and 'execve /sbin/launchd' in out
u, calls, out = run('launchd_child_start', 'child_chroot_fail')
assert calls == [2, 90, 90, 4, 61, 4, 4, 1] and 'errno=0x0d' in out
u, calls, out = run('launchd_child_start', 'child_exec_fail')
assert calls == [2, 90, 90, 4, 61, 12, 4, 59, 4, 4, 1] and 'errno=0x02' in out
u, calls, out = run('launchd_child_poll', 'wait_pending')
assert calls == [7] and u.reg_read(UC_ARM64_REG_X28) == 42
u, calls, out = run('launchd_child_poll', 'wait_exited')
assert calls == [7, 4, 4] and u.reg_read(UC_ARM64_REG_X28) == 0 and '00007e00' in out
print('launchd child fork, root, exec, error and wait control flow verified in emulator')

u, calls, out = run('launchd_pid1', 'pid1_ok')
assert calls == [4, 90, 90, 4, 61, 12, 4, 59] and 'replacing diagnostic PID1' in out
u, calls, out = run('launchd_pid1', 'pid1_chroot_fail')
assert calls == [4, 90, 90, 4, 61, 4, 4] and 'errno=0x0d' in out and 1 not in calls
u, calls, out = run('launchd_pid1', 'pid1_exec_fail')
assert calls == [4, 90, 90, 4, 61, 12, 4, 59, 4, 4] and 'errno=0x02' in out and 1 not in calls
print('PID1 direct exec and failure retention verified in emulator')
