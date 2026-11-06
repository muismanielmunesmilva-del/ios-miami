/* SPDX-License-Identifier: MIT
 * Single-CPU GICv3/virtual-timer test. Bases/INTID are from miami's live FDT.
 * Register definitions: Arm GICv3 and Linux include/linux/irqchip/arm-gic-v3.h.
 * No CPU_ON, storage access or external peripheral initialization.
 */
#include "interrupts.h"
#define R(name) ({ uint64_t v; __asm__ volatile("mrs %0, " name : "=r"(v)); v; })
#define W(name, value) __asm__ volatile("msr " name ", %0" : : "r"((uint64_t)(value)) : "memory")
#define GICD 0x0f200000UL
#define GICR 0x0f240000UL
#define TIMER_ID 19U
#define TIMER_BIT (1U << TIMER_ID)
#define SGI_PAGE 0x10000UL
static volatile uint32_t timer_irqs, other_irqs, last_irq;
static volatile int active;
static uintptr_t redistributor;
static uint64_t timer_period;
static uint32_t rd(uintptr_t p) { return *(volatile uint32_t *)p; }
static uint64_t rd64(uintptr_t p) { return *(volatile uint64_t *)p; }
static void wr(uintptr_t p, uint32_t value) { *(volatile uint32_t *)p = value; }
static void barrier(void) { __asm__ volatile("dsb sy; isb" ::: "memory"); }
static uint64_t ticks(void) { __asm__ volatile("isb" ::: "memory"); return R("cntvct_el0"); }

static int poll_clear(uintptr_t p, uint32_t mask)
{
    /* Iteration bound remains effective even if the clock later stops. */
    for (unsigned tries = 0; tries < 1000000; ++tries)
        if (!(rd(p) & mask)) return 1;
    return 0;
}

int gic_handle_irq(void)
{
    if (!active) return 0;
    uint64_t acknowledge = R("icc_iar1_el1");
    uint32_t id = acknowledge & 0xffffff;
    if (id >= 1020 && id <= 1023) return 1;
    last_irq = id;
    if (id == TIMER_ID) {
        ++timer_irqs;
        W("cntv_tval_el0", timer_period);
        __asm__ volatile("isb" ::: "memory");
    } else {
        ++other_irqs;
        /* Mask an unexpected NS source to avoid an unserviced level storm. */
        if (id < 32) wr(redistributor + SGI_PAGE + 0x180, 1U << id);
        else if (id < 1020) wr(GICD + 0x180 + (id / 32) * 4, 1U << (id % 32));
        __asm__ volatile("dsb sy" ::: "memory");
    }
    W("icc_eoir1_el1", acknowledge);
    __asm__ volatile("isb" ::: "memory");
    return 1;
}

int gic_timer_test(void)
{
    uint64_t frequency = R("cntfrq_el0");
    if (frequency != 19200000) return -1;
    probe_hex("COUNTER_READ_BEGIN", 1);
    uint64_t before = ticks();
    for (unsigned i = 0; i < 100000; ++i) __asm__ volatile("nop");
    uint64_t delta = ticks() - before;
    probe_hex("VIRTUAL_COUNTER_DELTA", delta);
    if (!delta) return -2;

    uint64_t sre = R("icc_sre_el1");
    W("icc_sre_el1", sre | 1);
    barrier();
    probe_hex("GIC_SRE_EL1", R("icc_sre_el1"));
    if (!(R("icc_sre_el1") & 1)) return -3;
    uint64_t mpidr = R("mpidr_el1");
    uint32_t affinity = (mpidr & 0xffffff) | ((mpidr >> 8) & 0xff000000);
    for (uintptr_t offset = 0; offset < 0x100000; offset += 0x20000) {
        uint64_t typer = rd64(GICR + offset + 8);
        if ((uint32_t)(typer >> 32) == affinity) {
            redistributor = GICR + offset;
            break;
        }
        if (typer & (1U << 4)) break;
    }
    if (!redistributor) return -4;
    probe_hex("GIC_REDISTRIBUTOR", redistributor);
    uint32_t distributor_control = rd(GICD);
    probe_hex("GIC_DIST_BEFORE", distributor_control);
    /* Do not change affinity routing or security mode during a diagnostic. */
    if (!(distributor_control & 0x10)) return -5;
    uint32_t wake = rd(redistributor + 0x14);
    wr(redistributor + 0x14, wake & ~2U);
    if (!poll_clear(redistributor + 0x14, 4)) return -6;
    uintptr_t sgi = redistributor + SGI_PAGE;
    uint32_t enabled = rd(sgi + 0x100), group = rd(sgi + 0x80);
    uint32_t config = rd(sgi + 0xc04);
    volatile uint8_t *priority = (volatile uint8_t *)(sgi + 0x400 + TIMER_ID);
    uint8_t saved_priority = *priority;
    uint64_t saved_pmr = R("icc_pmr_el1"), saved_bpr = R("icc_bpr1_el1");
    uint64_t saved_ctlr = R("icc_ctlr_el1"), saved_enable = R("icc_igrpen1_el1");
    uint64_t saved_timer_control = R("cntv_ctl_el0"), saved_compare = R("cntv_cval_el0");

    W("cntv_ctl_el0", 0);
    wr(sgi + 0x180, 0xffffffffU);
    wr(sgi + 0x80, group | TIMER_BIT);
    *priority = 0x80;
    wr(sgi + 0xc04, config & ~(1U << 7)); /* PPI19 level trigger */
    wr(sgi + 0x280, TIMER_BIT);
    wr(GICD, distributor_control | 3U);
    int distributor_ready = poll_clear(GICD, 1U << 31);
    if (distributor_ready) {
        wr(sgi + 0x100, TIMER_BIT);
        W("icc_ctlr_el1", saved_ctlr & ~2ULL); /* EOImode 0 */
        W("icc_pmr_el1", 0xf0);
        W("icc_bpr1_el1", 0);
        W("icc_igrpen1_el1", 1);
        timer_period = frequency / 100;
        timer_irqs = other_irqs = 0;
        last_irq = 0x3ff;
        active = 1;
        W("cntv_tval_el0", timer_period);
        W("cntv_ctl_el0", 1);
        barrier();
        uint64_t started = ticks();
        __asm__ volatile("msr daifclr, #2" ::: "memory");
        for (unsigned spin = 0; spin < 10000000; ++spin)
            if (ticks() - started >= frequency / 10) break;
        __asm__ volatile("msr daifset, #2" ::: "memory");
        W("cntv_ctl_el0", 0);
        active = 0;
        barrier();
    }
    /* Restore local configuration with IRQ masked; leave the result on screen. */
    wr(sgi + 0x180, 0xffffffffU);
    wr(sgi + 0x280, TIMER_BIT);
    wr(sgi + 0x80, group);
    wr(sgi + 0xc04, config);
    *priority = saved_priority;
    wr(sgi + 0x100, enabled);
    W("icc_pmr_el1", saved_pmr);
    W("icc_bpr1_el1", saved_bpr);
    W("icc_ctlr_el1", saved_ctlr);
    W("icc_igrpen1_el1", saved_enable);
    W("cntv_cval_el0", saved_compare);
    W("cntv_ctl_el0", saved_timer_control);
    wr(GICD, distributor_control);
    (void)poll_clear(GICD, 1U << 31);
    barrier();
    probe_hex("GIC_TIMER_IRQS", timer_irqs);
    probe_hex("GIC_OTHER_IRQS", other_irqs);
    probe_hex("GIC_LAST_IRQ", last_irq);
    if (!distributor_ready) return -7;
    return timer_irqs >= 2 && !other_irqs ? 0 : -8;
}
