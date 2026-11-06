/* Runtime alignment also covers Mach-O linkers placing this array at 4K. */
static tt_entry_t miami_final_splash_storage[4096] __attribute__((aligned(4096)));

static void
miami_early_map_final(void)
{
    const vm_map_address_t va = MIAMI_EARLY_FB_VA;
    tt_entry_t *const l3 = (tt_entry_t *)(((vm_offset_t)miami_final_splash_storage + 16383ULL) & ~16383ULL);
    assert(va + ARM_TT_L2_SIZE <= gVirtBase);
    tt_entry_t l1 = cpu_tte[(va & ARM_TT_L1_INDEX_MASK) >> ARM_TT_L1_SHIFT];
    assert((l1 & (ARM_TTE_VALID | ARM_TTE_TYPE_MASK)) == (ARM_TTE_VALID | ARM_TTE_TYPE_TABLE));
    tt_entry_t *l2 = (tt_entry_t *)phystokv(l1 & ARM_TTE_TABLE_MASK);
    tt_entry_t *slot = &l2[(va & ARM_TT_L2_INDEX_MASK) >> ARM_TT_L2_SHIFT];
    assert(*slot == ARM_TTE_EMPTY);
    for (unsigned i = 0; i < 2048; ++i) {
        uint64_t pa = 0x84000000ULL + ((uint64_t)i << 14);
        l3[i] = pa >= 0x85200000ULL && pa < 0x85e00000ULL ?
            pa | ARM_TTE_TYPE_TABLE | ARM_TTE_VALID |
            ARM_TTE_BLOCK_SH(SH_OUTER_MEMORY) |
            ARM_TTE_BLOCK_ATTRINDX(CACHE_ATTRINDX_WRITECOMB) |
            ARM_TTE_BLOCK_AF | ARM_TTE_BLOCK_PNX | ARM_TTE_BLOCK_NX : 0;
    }
    const uint64_t table_pa = kvtophys((vm_offset_t)l3);
    assert((table_pa & 16383ULL) == 0);
    *slot = (table_pa & ARM_TTE_TABLE_MASK) |
        ARM_TTE_TYPE_TABLE | ARM_TTE_VALID;
    __asm__ volatile("dsb ishst" ::: "memory");
}
