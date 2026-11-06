/* SPDX-License-Identifier: MIT
 * Independent architectural walk of generated tables: every permitted leaf
 * must have the expected PA/attributes; protected RAM and guard pages must
 * remain unmapped. Covers a 32MB boundary and several boot placements.
 */
#include <stdio.h>
#include <stdlib.h>
#include "tables16k.h"
static uint64_t storage[MMU_TABLE_COUNT * MMU_TABLE_ENTRIES];
static uint64_t walk(const struct mmu_plan *p, uint64_t va)
{
    if (va >= (1ULL << 36)) return 0;
    uint64_t root = p->tables[va >> 25];
    if ((root & 3) != 3) return 0;
    uint64_t offset = (root & MMU_PA_MASK) - p->tables_pa;
    if (offset % MMU_PAGE_SIZE || offset >= MMU_TABLE_COUNT * MMU_PAGE_SIZE) abort();
    const uint64_t *leaf = p->tables + offset / 8;
    return leaf[(va >> 14) & 2047];
}
static uint64_t expected(uint64_t va, uint64_t lo, uint64_t hi, uint64_t scratch)
{
    if (va >= lo && va < hi) return va | MMU_NORMAL_WB | 3;
    if ((va >= 0x05e00000 && va < 0x05e90000) ||
        (va >= 0x0f200000 && va < 0x0f210000) ||
        (va >= 0x0f240000 && va < 0x0f340000) ||
        (va >= 0xaf000000 && va < 0xaf0c0000)) return va | MMU_DEVICE | 3;
    if (va >= 0x85200000 && va < 0x85e00000) return va | MMU_NORMAL_NC | 3;
    if (va == MMU_ALIAS) return scratch | MMU_NORMAL_WB | MMU_PXN | 3;
    return 0;
}
int main(void)
{
    const uint64_t bases[] = {0xa00b0000, 0xa1ffc000, 0x180000000, 0x27ffc0000};
    unsigned cases = 0;
    for (unsigned n = 0; n < sizeof(bases)/sizeof(bases[0]); ++n) {
        uint64_t lo = bases[n], hi = lo + 0x40000;
        uint64_t pool = lo + MMU_PAGE_SIZE, scratch = lo + 11 * MMU_PAGE_SIZE;
        struct mmu_plan plan = {storage, pool, 0};
        if (mmu_plan_build(&plan, lo, hi, scratch)) return 1;
        /* Check every potential leaf, including invalid roots, independently
         * of the builder's traversal order and region functions. */
        unsigned present = 0;
        for (uint64_t ri = 0; ri < 2048; ++ri) {
            if (!storage[ri]) continue;
            for (uint64_t li = 0; li < 2048; ++li) {
                uint64_t va = (ri << 25) | (li << 14);
                uint64_t descriptor = walk(&plan, va);
                if (descriptor != expected(va, lo, hi, scratch)) return 2;
                present += descriptor != 0;
            }
        }
        if (present != (hi-lo)/MMU_PAGE_SIZE + 36 + 4 + 64 + 48 + 768 + 1) return 3;
        const uint64_t guards[] = {0x80000000,0x80880000,0x8b800000,0xc0000000,
                                  MMU_ALIAS-MMU_PAGE_SIZE,MMU_ALIAS+MMU_PAGE_SIZE};
        for (unsigned i = 0; i < sizeof(guards)/sizeof(guards[0]); ++i)
            if (walk(&plan, guards[i])) return 4;
        ++cases;
    }
    struct mmu_plan bad = {storage, 0xa00b4000, 0};
    if (!mmu_plan_build(&bad, 0xa00b0001, 0xa00f0000, 0xa00dc000)) return 5;
    if (!mmu_plan_build(&bad, 0xa00b0000, 0xa00f0000, 0xa00b4000)) return 6;
    printf("16K table invariants passed: %u placements, protected regions and alias guards\n", cases);
    return 0;
}
