/* SPDX-License-Identifier: MIT
 * Pure table builder shared by the probe and native invariant checks.
 * 36-bit identity VA space: L2[35:25] -> L3[24:14] -> 16K page.
 * Only the loaded image is Normal WB. Required MMIO/logs are Device;
 * the reserved splash is Normal NC. Other physical memory stays unmapped.
 */
#include "tables16k.h"

static int page(struct mmu_plan *p, uint64_t va, uint64_t pa, uint64_t flags)
{
    if ((va | pa) & (MMU_PAGE_SIZE - 1) || va >= (1ULL << 36) || pa >= (1ULL << 40)) return -1;
    unsigned root_index = (unsigned)(va >> 25);
    uint64_t root = p->tables[root_index];
    uint64_t *leaf;
    if (!root) {
        if (p->used >= MMU_TABLE_COUNT) return -1;
        unsigned index = p->used++;
        leaf = p->tables + (uint64_t)index * MMU_TABLE_ENTRIES;
        p->tables[root_index] = (p->tables_pa + (uint64_t)index * MMU_PAGE_SIZE) | 3;
    } else {
        uint64_t physical = root & MMU_PA_MASK;
        if ((root & 3) != 3 || physical < p->tables_pa ||
            physical >= p->tables_pa + (uint64_t)p->used * MMU_PAGE_SIZE) return -1;
        leaf = p->tables + (physical - p->tables_pa) / 8;
    }
    unsigned index = (unsigned)((va >> 14) & 2047);
    uint64_t descriptor = pa | flags | 3;
    if (leaf[index] && leaf[index] != descriptor) return -1;
    leaf[index] = descriptor;
    return 0;
}

static int identity(struct mmu_plan *p, uint64_t first, uint64_t end, uint64_t flags)
{
    if ((first | end) & (MMU_PAGE_SIZE - 1) || first >= end) return -1;
    for (uint64_t at = first; at < end; at += MMU_PAGE_SIZE)
        if (page(p, at, at, flags)) return -1;
    return 0;
}

int mmu_plan_build(struct mmu_plan *p, uint64_t lo, uint64_t hi, uint64_t scratch)
{
    uint64_t pool_end = p->tables_pa + MMU_TABLE_COUNT * MMU_PAGE_SIZE;
    if (!p->tables || ((lo | hi | p->tables_pa | scratch) & (MMU_PAGE_SIZE - 1)) ||
        lo >= hi || hi > (1ULL << 36) || hi - lo > 0x400000 ||
        p->tables_pa < lo || pool_end > hi || scratch < lo ||
        scratch + MMU_PAGE_SIZE > hi ||
        (scratch < pool_end && p->tables_pa < scratch + MMU_PAGE_SIZE)) return -1;
    p->used = 1;
    for (unsigned i = 0; i < MMU_TABLE_COUNT * MMU_TABLE_ENTRIES; ++i) p->tables[i] = 0;
    if (identity(p, lo, hi, MMU_NORMAL_WB) ||
        identity(p, 0x05e00000, 0x05e90000, MMU_DEVICE) || /* MDP */
        identity(p, 0x0f200000, 0x0f210000, MMU_DEVICE) || /* GICD */
        identity(p, 0x0f240000, 0x0f340000, MMU_DEVICE) || /* GICR */
        identity(p, 0x85200000, 0x85e00000, MMU_NORMAL_NC) || /* splash */
        identity(p, 0xaf000000, 0xaf0c0000, MMU_DEVICE) || /* ramoops */
        page(p, MMU_ALIAS, scratch, MMU_NORMAL_WB | MMU_PXN)) return -2;
    return 0;
}
