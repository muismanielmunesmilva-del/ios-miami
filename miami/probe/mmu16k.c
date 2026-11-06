/* SPDX-License-Identifier: MIT
 * Single-CPU identity mapping test. No external RAM is written: the alias
 * maps a private page inside this loaded Image, including its last word.
 * Translation fields follow Arm's memory-management guide and Linux's
 * arch/arm64/include/asm/pgtable-hwdef.h; no blanket Normal RAM mappings.
 */
#include "tables16k.h"
#include "interrupts.h"
#define R(name) ({ uint64_t v; __asm__ volatile("mrs %0, " name : "=r"(v)); v; })
#define W(name, value) __asm__ volatile("msr " name ", %0" : : "r"((uint64_t)(value)) : "memory")
#define TCR_VALUE (28ULL | (1ULL << 8) | (1ULL << 10) | (3ULL << 12) | \
                   (2ULL << 14) | (28ULL << 16) | (1ULL << 23) | \
                   (1ULL << 30) | (2ULL << 32))
#define MAIR_VALUE 0x44ff00ULL
extern char _head[], _end[];
/* One extra page supplies runtime alignment even if the linker placement
 * of either object is only cache-line aligned. All storage is in the Image. */
static uint64_t table_storage[(MMU_TABLE_COUNT + 1) * MMU_TABLE_ENTRIES] __attribute__((aligned(64)));
static uint64_t scratch_storage[2 * MMU_TABLE_ENTRIES] __attribute__((aligned(64)));

static uint64_t translate(uintptr_t va)
{
    __asm__ volatile("at s1e1r, %0; isb" : : "r"(va) : "memory");
    return R("par_el1");
}

int mmu16k_test(void)
{
    uint64_t features = R("id_aa64mmfr0_el1");
    if (R("CurrentEL") != 4 || (R("sctlr_el1") & 5) ||
        ((features >> 20) & 15) != 1 || (features & 15) < 2 ||
        (features & 15) > 6) return -1;
    uintptr_t image_lo = (uintptr_t)_head, image_hi = (uintptr_t)_end;
    if ((image_lo | image_hi) & (MMU_PAGE_SIZE - 1)) return -2;
    uintptr_t table_pa = ((uintptr_t)table_storage + MMU_PAGE_SIZE - 1) & ~(MMU_PAGE_SIZE - 1);
    uintptr_t scratch_pa = ((uintptr_t)scratch_storage + MMU_PAGE_SIZE - 1) & ~(MMU_PAGE_SIZE - 1);
    struct mmu_plan plan = { (uint64_t *)table_pa, table_pa, 0 };
    int built = mmu_plan_build(&plan, image_lo, image_hi, scratch_pa);
    probe_hex("MMU_PLAN_RESULT", (uint32_t)built);
    if (built) return -3;
    probe_hex("MMU_IMAGE_BASE", image_lo);
    probe_hex("MMU_IMAGE_END", image_hi);
    probe_hex("MMU_TABLE_PAGES", plan.used);
    probe_hex("MMU_TTBR0_PA", table_pa);
    probe_hex("MMU_SCRATCH_PA", scratch_pa);
    probe_hex("MMU_ALIAS_VA", MMU_ALIAS);
    probe_hex("MMU_ENABLE_BEGIN", 1);

    /* ABI has D-cache off, so table stores already reached memory. Remove
     * stale image lines left by ABL before selecting Normal WB attributes. */
    uint64_t line = 4ULL << ((R("ctr_el0") >> 16) & 15);
    __asm__ volatile("dsb sy" ::: "memory");
    for (uintptr_t at = image_lo; at < image_hi; at += line)
        __asm__ volatile("dc ivac, %0" : : "r"(at) : "memory");
    __asm__ volatile("ic iallu; dsb sy; isb" ::: "memory");
    W("mair_el1", MAIR_VALUE);
    W("tcr_el1", TCR_VALUE);
    W("ttbr0_el1", table_pa);
    W("ttbr1_el1", 0);
    __asm__ volatile("isb; tlbi vmalle1; dsb sy; isb" ::: "memory");
    uint64_t control = R("sctlr_el1");
    control &= ~((1ULL << 1) | (1ULL << 19)); /* alignment check and WXN */
    control |= (1ULL << 0) | (1ULL << 2) | (1ULL << 12);
    W("sctlr_el1", control);
    __asm__ volatile("isb" ::: "memory");
    probe_hex("MMU_SCTLR_AFTER", R("sctlr_el1"));
    probe_hex("MMU_TCR", R("tcr_el1"));

    const uint64_t par_mask = ((1ULL << 40) - 1) & ~0xfffULL;
    uint64_t first = translate(MMU_ALIAS);
    uint64_t last = translate(MMU_ALIAS + MMU_PAGE_SIZE - 8);
    uint64_t guard = translate(MMU_ALIAS + MMU_PAGE_SIZE);
    probe_hex("PAR_ALIAS_FIRST", first);
    probe_hex("PAR_ALIAS_LAST", last);
    probe_hex("PAR_ALIAS_GUARD", guard);
    if ((first & 1) || (last & 1) || !(guard & 1) ||
        (first & par_mask) != (scratch_pa & par_mask) ||
        (last & par_mask) != ((scratch_pa + MMU_PAGE_SIZE - 8) & par_mask)) return -4;

    volatile uint64_t *physical = (volatile uint64_t *)scratch_pa;
    volatile uint64_t *alias = (volatile uint64_t *)(uintptr_t)MMU_ALIAS;
    physical[0] = 0x4d49414d4931364bULL;
    __asm__ volatile("dsb sy" ::: "memory");
    int match = alias[0] == physical[0];
    alias[MMU_TABLE_ENTRIES - 1] = 0x50524f4245303035ULL;
    __asm__ volatile("dsb sy" ::: "memory");
    match &= physical[MMU_TABLE_ENTRIES - 1] == 0x50524f4245303035ULL;
    probe_hex("MMU_ALIAS_DATA_OK", (uint64_t)match);
    uint64_t after = R("sctlr_el1");
    return match && (after & 0x1005) == 0x1005 ? 0 : -5;
}
