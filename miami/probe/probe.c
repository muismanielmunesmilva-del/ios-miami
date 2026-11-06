/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include "layout.h"
#include "display.h"
#include "interrupts.h"
#include "tables16k.h"

#define READ_REG(name) ({ uint64_t v; __asm__ volatile("mrs %0, " name : "=r"(v)); v; })
static volatile uint32_t *log_header;
static volatile uint8_t *log_bytes;
static uint32_t log_used;
static int exception_active;

static void put(char c)
{
    if (log_used < 4096) log_bytes[log_used++] = (uint8_t)c;
    screen_put(c);
}
static void text(const char *s)
{
    while (*s) put(*s++);
}
static void commit(void)
{
    __asm__ volatile("dsb sy" ::: "memory");
    log_header[1] = log_used;
    log_header[2] = log_used;
    log_header[0] = 0x43474244;
    /* Use the architectural cache line size, including when ABL leaves
     * D-cache enabled despite the Linux handoff convention. */
    uint64_t line = 4ULL << ((READ_REG("ctr_el0") >> 16) & 15);
    uintptr_t base = (uintptr_t)log_header;
    for (uintptr_t at = base & ~(line - 1); at < base + 12 + log_used; at += line)
        __asm__ volatile("dc cvac, %0" : : "r"(at) : "memory");
    __asm__ volatile("dsb sy" ::: "memory");
    screen_commit();
}
static void hex(const char *name, uint64_t v)
{
    text(name);
    text("=0x");
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned digit = (v >> shift) & 15;
        put(digit < 10 ? '0' + digit : 'a' + digit - 10);
    }
    put('\n');
    commit();
}
void probe_hex(const char *name, uint64_t value) { hex(name, value); }

unsigned probe_exception(unsigned slot)
{
    if (slot == 5 && gic_handle_irq()) return 1;
    if (!log_header || exception_active) return 0;
    exception_active = 1;
    text("MIAMI exception; manual reset\n");
    hex("EXCEPTION_SLOT", slot);
    hex("ESR_EL1", READ_REG("esr_el1"));
    hex("ELR_EL1", READ_REG("elr_el1"));
    hex("FAR_EL1", READ_REG("far_el1"));
    return 0;
}
static uint64_t smc(uint64_t fn)
{
    register uint64_t x0 __asm__("x0") = fn;
    register uint64_t x1 __asm__("x1") = 0;
    register uint64_t x2 __asm__("x2") = 0;
    register uint64_t x3 __asm__("x3") = 0;
    __asm__ volatile("smc #0" : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
        : : "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11", "x12",
            "x13", "x14", "x15", "x16", "x17", "memory");
    return x0;
}

void probe_main(const void *fdt)
{
    uint64_t el = READ_REG("CurrentEL");
    if (el != 4 && el != 8) return;
    uint64_t control = el == 4 ? READ_REG("sctlr_el1") : READ_REG("sctlr_el2");
    /* Physical-address accesses require an MMU-off handoff. */
    if (control & 1) return;
    screen_init(control);
    struct probe_layout layout;
    /* Build-time validation and fastboot product selection pin this probe
     * to XT2245-1. Log the runtime validation result before aborting, so a
     * different FDT can be diagnosed without enabling any device driver. */
    log_header = (volatile uint32_t *)(uintptr_t)0xaf03f800;
    log_bytes = (volatile uint8_t *)(uintptr_t)0xaf03f80c;
    log_header[0] = log_header[1] = log_header[2] = 0;
    text("MIAMI_PROBE_V5 begin\n");
    commit();
    hex("CurrentEL", el);
    hex("SCTLR", control);
    extern char _head[];
    hex("IMAGE_BASE", (uintptr_t)_head);
    int validation = probe_layout_from_fdt(fdt, &layout);
    hex("FDT_LAYOUT_RESULT", (uint32_t)validation);
    if (validation) { for (;;) __asm__ volatile("wfe"); }
    hex("MPIDR_EL1", READ_REG("mpidr_el1"));
    hex("MIDR_EL1", READ_REG("midr_el1"));
    hex("ID_AA64PFR0_EL1", READ_REG("id_aa64pfr0_el1"));
    hex("ID_AA64MMFR0_EL1", READ_REG("id_aa64mmfr0_el1"));
    hex("ID_AA64MMFR1_EL1", READ_REG("id_aa64mmfr1_el1"));
    hex("ID_AA64ISAR0_EL1", READ_REG("id_aa64isar0_el1"));
    hex("ID_AA64ISAR1_EL1", READ_REG("id_aa64isar1_el1"));
    hex("CNTFRQ_EL0", READ_REG("cntfrq_el0"));
    hex("PSCI_VERSION", smc(0x84000000));
    if (el == 4) {
        screen_new_section();
        text("MIAMI_PROBE_V5 MMU16K\n");
        commit();
        int mmu = mmu16k_test();
        hex("MMU_TEST_RESULT", (uint32_t)mmu);
        if (!mmu) hex("GIC_AFTER_MMU_RESULT", (uint32_t)gic_timer_test());
    } else hex("MMU_TEST_SKIPPED_EL", el);
    text("MIAMI_PROBE_V5 complete; manual reset\n");
    commit();
    for (;;) __asm__ volatile("wfe");
}
