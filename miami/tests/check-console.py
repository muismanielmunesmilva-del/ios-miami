#!/usr/bin/env python3
"""Compile the actual bootstrap fragment as Darwin arm64 assembly, and execute
the actual final splash-table function with mocked page-table access on host.
Only the architecture barrier is removed for the host execution.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1] / 'xnu'
DEFINES = '''
#define MIAMI 1
#define EXT(x) _##x
#define ARM_TTE_TYPE_TABLE 2
#define ARM_TTE_VALID 1
#define ARM_TTE_TYPE_MASK 2
#define ARM_TTE_EMPTY 0
#define ARM_TTE_TABLE_MASK 0x0000fffffffff000
#define SH_OUTER_MEMORY 2
#define ARM_TTE_BLOCK_SH(x) ((x) << 8)
#define CACHE_ATTRINDX_WRITECOMB 1
#define ARM_TTE_BLOCK_ATTRINDX(x) ((x) << 2)
#define ARM_TTE_BLOCK_AF 0x400
#define ARM_TTE_BLOCK_PNX 0x0020000000000000
#define ARM_TTE_BLOCK_NX 0x0040000000000000
#define BA_VIDEO_BASE 40
#define BA_VIDEO_ROW_BYTES 56
'''

with tempfile.TemporaryDirectory(prefix='miami-console-') as folder:
    temp = Path(folder)
    assembly = DEFINES + (ROOT / 'boot-marks.S.inc').read_text() + r'''
.macro MOV64 reg, val
    movz \reg, #((\val) & 0xffff)
    movk \reg, #(((\val) >> 16) & 0xffff), lsl #16
    movk \reg, #(((\val) >> 32) & 0xffff), lsl #32
    movk \reg, #(((\val) >> 48) & 0xffff), lsl #48
.endm
.text
.globl _test
_test:
    miami_boot_mark x0, 1
    miami_boot_mark x20, 2
    miami_boot_mark x20, 3
    miami_boot_mark x20, 4
    miami_boot_mark x20, 5
    miami_boot_mark x20, 6
    miami_boot_mark x0, 7
''' + (ROOT / 'bootstrap-splash.S.inc').read_text() + '''
    ret
.section __DATA,__data
.p2align 14
_miami_boot_splash_storage:
.space 32768
'''
    source = temp / 'bootstrap.S'
    source.write_text(assembly)
    subprocess.run(['clang', '-target', 'arm64-apple-macos13.5', '-c', str(source),
                    '-o', str(temp / 'bootstrap.o')], check=True)
    c = '''#include <stdint.h>
#include <assert.h>
typedef uint64_t tt_entry_t;
typedef uint64_t vm_map_address_t;
typedef uint64_t vm_offset_t;
''' + DEFINES + '''
#define MIAMI_EARLY_FB_VA 0xfffffe0002000000ULL
#define ARM_TT_L2_SIZE 0x2000000ULL
#define ARM_TT_L1_INDEX_MASK 0x7000000000ULL
#define ARM_TT_L1_SHIFT 36
#define ARM_TT_L2_INDEX_MASK 0xffe000000ULL
#define ARM_TT_L2_SHIFT 25
static uint64_t gVirtBase = 0xfffffe0006000000ULL;
static tt_entry_t cpu_tte[2048], l2_test[2048];
static void *phystokv(uint64_t pa) { assert(pa == 0x180004000ULL); return l2_test; }
static void *expected_table;
static uint64_t kvtophys(uint64_t va) { assert(va == (uintptr_t)expected_table); assert(!(va & 16383)); return 0x180008000ULL; }
'''
    body = (ROOT / 'final-splash.c.inc').read_text()
    barrier = '__asm__ volatile("dsb ishst" ::: "memory");'
    assert body.count(barrier) == 1
    declaration = 'static tt_entry_t miami_final_splash_storage[4096] __attribute__((aligned(4096)));'
    assert body.count(declaration) == 1
    # Exercise the actual mapping function with deliberately misplaced backing
    # storage, reproducing the linked kernel's 4K/8K/12K offsets within a 16K page.
    backing = '''static unsigned char test_storage[49152] __attribute__((aligned(16384)));
static unsigned test_offset;
#define miami_final_splash_storage (test_storage + test_offset)'''
    c += body.replace(barrier, '').replace(declaration, backing) + '''
int main(void) {
    const unsigned offsets[] = {0, 8, 4096, 8192, 12288, 16376};
    for (unsigned test = 0; test < sizeof(offsets) / sizeof(offsets[0]); ++test) {
    test_offset = offsets[test];
    expected_table = test_storage + (test_offset ? 16384 : 0);
    for (unsigned i = 0; i < sizeof(test_storage); ++i) test_storage[i] = 0xa5;
    for (unsigned i = 0; i < 2048; ++i) l2_test[i] = 0;
    cpu_tte[(MIAMI_EARLY_FB_VA & ARM_TT_L1_INDEX_MASK) >> ARM_TT_L1_SHIFT] = 0x180004003ULL;
    miami_early_map_final();
    assert(l2_test[(MIAMI_EARLY_FB_VA & ARM_TT_L2_INDEX_MASK) >> ARM_TT_L2_SHIFT] == 0x180008003ULL);
    unsigned mapped = 0;
    for (unsigned i = 0; i < 2048; ++i) {
        uint64_t pa = 0x84000000ULL + ((uint64_t)i << 14), pte = ((tt_entry_t *)expected_table)[i];
        if (pa < 0x85200000ULL || pa >= 0x85e00000ULL) { assert(pte == 0); continue; }
        ++mapped;
        assert((pte & 0x0000ffffffffc000ULL) == pa);
        assert((pte & 0x60000000000407ULL) == 0x60000000000407ULL);
    }
    assert(mapped == 768);
    for (unsigned i = 0; i < (uintptr_t)expected_table - (uintptr_t)test_storage; ++i) assert(test_storage[i] == 0xa5);
    for (unsigned i = (uintptr_t)expected_table - (uintptr_t)test_storage + 16384; i < sizeof(test_storage); ++i) assert(test_storage[i] == 0xa5);
    }
    return 0;
}
'''
    source = temp / 'final.c'
    source.write_text(c)
    binary = temp / 'final'
    subprocess.run(['gcc', '-O2', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: Darwin arm64 bootstrap assembly; six backing-storage offsets produce aligned final tables, exactly 768 NC/XN splash pages and untouched guards')
