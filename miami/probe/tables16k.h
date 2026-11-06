#pragma once
#include <stdint.h>
#define MMU_PAGE_SIZE 16384ULL
#define MMU_TABLE_ENTRIES 2048U
#define MMU_TABLE_COUNT 9U
#define MMU_ALIAS 0x0f00000000ULL
#define MMU_PA_MASK (((1ULL << 40) - 1) & ~(MMU_PAGE_SIZE - 1))
#define MMU_AF (1ULL << 10)
#define MMU_PXN (1ULL << 53)
#define MMU_UXN (1ULL << 54)
#define MMU_DEVICE (MMU_AF | MMU_PXN | MMU_UXN)
#define MMU_NORMAL_WB (MMU_AF | (1ULL << 2) | (3ULL << 8) | MMU_UXN)
#define MMU_NORMAL_NC (MMU_AF | (2ULL << 2) | (2ULL << 8) | MMU_PXN | MMU_UXN)
struct mmu_plan {
    uint64_t *tables;
    uint64_t tables_pa;
    unsigned used;
};
int mmu_plan_build(struct mmu_plan *, uint64_t image_lo, uint64_t image_hi,
                   uint64_t scratch_pa);
int mmu16k_test(void);
