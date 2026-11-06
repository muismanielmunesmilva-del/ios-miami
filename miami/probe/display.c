/* SPDX-License-Identifier: MIT
 * Reuse ABL's linear splash pipe. Register offsets come from the live miami
 * FDT and Motorola's sde_hw_sspp.c/sde_hw_ctl.c; command-mode autorefresh
 * follows NWylynko/ios-flame's documented SDE bring-up.
 * No clocks, PHY, panel commands, format or source addresses are changed.
 */
#include <stdint.h>
#include "display.h"
#include "../../shim/font.h"

#define MDP 0x05e00000UL
#define CTL (MDP + 0x2000)
#define INTF (MDP + 0x6b800)
#define WIDTH 1080U
#define HEIGHT 2400U
static volatile uint32_t *fb;
static uint32_t stride, row, column;
static int cache_enabled, manual;
static uint32_t rd(uintptr_t address) { return *(volatile uint32_t *)address; }
static void wr(uintptr_t address, uint32_t value) { *(volatile uint32_t *)address = value; }

void screen_commit(void)
{
    if (!fb) return;
    if (cache_enabled) {
        uint64_t ctr;
        __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
        uintptr_t line = 4ULL << ((ctr >> 16) & 15);
        uintptr_t start = (uintptr_t)fb;
        uintptr_t end = start + (uint64_t)stride * 4 * HEIGHT;
        for (uintptr_t p = start & ~(line - 1); p < end; p += line)
            __asm__ volatile("dc cvac, %0" : : "r"(p) : "memory");
    }
    __asm__ volatile("dsb sy" ::: "memory");
    /* Never issue CTL_START while autorefresh is enabled. */
    if (manual && !(rd(INTF + 0x2b4) & 0x80000000U) && !rd(CTL + 0x1c))
        wr(CTL + 0x1c, 1);
}

void screen_init(uint64_t control)
{
    cache_enabled = (control & 4) != 0;
    const uintptr_t candidates[2] = { MDP + 0x5000, MDP + 0x25000 };
    for (unsigned i = 0; i < 2; ++i) {
        uintptr_t pipe = candidates[i];
        uint32_t source = rd(pipe + 0x14);
        uint32_t bytes_per_row = rd(pipe + 0x24) & 0xffff;
        uint32_t format = rd(pipe + 0x30);
        if (source < 0x85200000 || (source & 3) || bytes_per_row < WIDTH * 4 ||
            (bytes_per_row & 3) || bytes_per_row > 8192 ||
            (uint64_t)source + (uint64_t)bytes_per_row * HEIGHT > 0x85e00000 ||
            ((format >> 9) & 3) != 3 || (format >> 30) ||
            (format & ((1U << 15) | (1U << 22)))) continue;
        fb = (volatile uint32_t *)(uintptr_t)source;
        stride = bytes_per_row / 4;
        break;
    }
    if (!fb) return;
    /* Static visible marker; the top remains black for register text. */
    for (unsigned y = 0; y < HEIGHT; ++y)
        for (unsigned x = 0; x < WIDTH; ++x)
            fb[(uint64_t)y * stride + x] =
                y >= 2000 && (x < 360 || x >= 720) ? 0xffffffff : 0xff000000;
    uint32_t auto_refresh = rd(INTF + 0x2b4);
    if (!(auto_refresh & 0x80000000U) && rd(INTF + 0x284))
        wr(INTF + 0x2b4, 0x80000001U);
    else if (!(auto_refresh & 0x80000000U) && (rd(CTL + 0xf4) & 2))
        manual = 1;
    screen_commit();
}

void screen_put(char c)
{
    if (!fb) return;
    if (c == '\n') { ++row; column = 0; return; }
    if (c < 32 || c > 126) c = '?';
    unsigned x0 = 24 + column * 24, y0 = 120 + row * 48;
    ++column;
    if (x0 + 24 > WIDTH || y0 + 48 > 1950) return;
    const unsigned char *glyph = font8x16[(unsigned)c - 32];
    for (unsigned gy = 0; gy < 16; ++gy)
        for (unsigned gx = 0; gx < 8; ++gx)
            for (unsigned sy = 0; sy < 3; ++sy)
                for (unsigned sx = 0; sx < 3; ++sx)
                    fb[(uint64_t)(y0 + gy * 3 + sy) * stride + x0 + gx * 3 + sx] =
                        glyph[gy] & (0x80 >> gx) ? 0xffffffff : 0xff000000;
}

void screen_new_section(void)
{
    row = column = 0;
    if (!fb) return;
    for (unsigned y = 0; y < 2000; ++y)
        for (unsigned x = 0; x < WIDTH; ++x)
            fb[(uint64_t)y * stride + x] = 0xff000000;
    screen_commit();
}

int screen_handoff(struct screen_info *out)
{
    if (!fb || manual || !(rd(INTF + 0x2b4) & 0x80000000U)) return -1;
    out->base = (uintptr_t)fb;
    out->row_bytes = (uint64_t)stride * 4;
    out->width = WIDTH;
    out->height = HEIGHT;
    return 0;
}
