/* SPDX-License-Identifier: MIT
 * MMU-off single-CPU XNU handoff. No storage driver, reset or CPU_ON calls.
 */
#include "plan.h"
#include "../probe/display.h"
#include "../probe/layout.h"
#include <libfdt.h>
extern char _head[], _end[], _payload_start[], _payload_end[];
struct boot_video { uint64_t base, display, row_bytes, width, height, depth; };
struct boot_args {
    uint16_t Revision, Version;
    uint64_t virtBase, physBase, memSize, topOfKernelData;
    struct boot_video Video;
    uint32_t machineType;
    uint64_t deviceTreeP;
    uint32_t deviceTreeLength;
    char CommandLine[608];
    uint64_t bootFlags, memSizeActual;
};
_Static_assert(sizeof(struct boot_args) == 736, "Apple boot_args v2");
_Static_assert(offsetof(struct boot_args, Video) == 40, "Apple video ABI");
_Static_assert(offsetof(struct boot_args, CommandLine) == 108, "Apple command line ABI");
void probe_hex(const char *label, uint64_t value)
{
    while (*label) screen_put(*label++);
    screen_put('='); screen_put('0'); screen_put('x');
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned v = (value >> shift) & 15;
        screen_put(v < 10 ? '0' + v : 'a' + v - 10);
    }
    screen_put('\n'); screen_commit();
}
static void message(const char *text)
{
    while (*text) screen_put(*text++);
    screen_commit();
}
unsigned probe_exception(unsigned slot)
{
    uint64_t esr, elr, far;
    __asm__ volatile("mrs %0, esr_el1; mrs %1, elr_el1; mrs %2, far_el1" : "=r"(esr), "=r"(elr), "=r"(far));
    probe_hex("EXCEPTION_SLOT", slot); probe_hex("ESR_EL1", esr);
    probe_hex("ELR_EL1", elr); probe_hex("FAR_EL1", far);
    message("MIAMI loader exception; manual reset\n");
    return 0;
}
static int intersects(uintptr_t first, uint64_t bytes)
{
    return bytes > UINT64_MAX - first || (bytes && first < MIAMI_RAM_BASE +
        MIAMI_RAM_SIZE + MIAMI_PANIC_SIZE && MIAMI_RAM_BASE < first + bytes);
}
static uint64_t fdt_number(const fdt32_t *p, int len)
{
    return len == 8 ? (uint64_t)fdt32_to_cpu(p[0]) << 32 | fdt32_to_cpu(p[1]) : fdt32_to_cpu(p[0]);
}
static int live_objects_clear(const void *fdt)
{
    if (intersects((uintptr_t)_head, (uintptr_t)_end - (uintptr_t)_head) ||
        intersects((uintptr_t)fdt, fdt_totalsize(fdt))) return 0;
    int chosen = fdt_path_offset(fdt, "/chosen"), a, b;
    const fdt32_t *lo = fdt_getprop(fdt, chosen, "linux,initrd-start", &a);
    const fdt32_t *hi = fdt_getprop(fdt, chosen, "linux,initrd-end", &b);
    if (!lo && !hi) return 1;
    if (!lo || !hi || (a != 4 && a != 8) || (b != 4 && b != 8)) return 0;
    uint64_t first = fdt_number(lo, a), end = fdt_number(hi, b);
    return end > first && !intersects(first, end - first);
}
static void copy_bytes(uintptr_t destination, const void *source, uint64_t size)
{
    volatile uint64_t *d = (volatile uint64_t *)destination;
    const uint64_t *s = source;
    uint64_t words = size / 8;
    for (uint64_t i = 0; i < words; ++i) d[i] = s[i];
    volatile uint8_t *tail = (volatile uint8_t *)(destination + words * 8);
    const uint8_t *stail = (const uint8_t *)source + words * 8;
    for (unsigned i = 0; i < size % 8; ++i) tail[i] = stail[i];
}
static void zero_bytes(uintptr_t destination, uint64_t size)
{
    volatile uint8_t *d = (volatile uint8_t *)destination;
    for (uint64_t i = 0; i < size; ++i) d[i] = 0;
}
void probe_main(const void *fdt)
{
    uint64_t control, el;
    __asm__ volatile("mrs %0, CurrentEL; mrs %1, sctlr_el1" : "=r"(el), "=r"(control));
    if (el != 4 || (control & 0x1005)) return; /* observed EL1, M/C/I off */
    screen_init(control);
    message("MIAMI XNU loader 0001\n");
    if (fdt_check_header(fdt) || fdt_totalsize(fdt) > 0x200000) return;
    int result = miami_fdt_ram_allowed(fdt, fdt_totalsize(fdt));
    probe_hex("RAM_LAYOUT", (uint32_t)result);
    if (result || !live_objects_clear(fdt)) return;
    struct probe_layout layout;
    result = probe_layout_from_fdt(fdt, &layout);
    probe_hex("TARGET_LAYOUT", (uint32_t)result);
    if (result) return;
    struct screen_info video;
    if (screen_handoff(&video)) { message("SDE autorefresh not confirmed; stopped\n"); return; }
    struct miami_plan plan;
    result = miami_payload_plan(_payload_start, _payload_end - _payload_start, &plan);
    probe_hex("PAYLOAD_PLAN", (uint32_t)result);
    if (result) return;
    const struct miami_payload *p = (const void *)_payload_start;
    probe_hex("XNU_PHYS_BASE", MIAMI_RAM_BASE);
    probe_hex("XNU_ENTRY_PA", plan.entry_pa);
    probe_hex("FB_BASE", video.base);
    probe_hex("FB_ROW_BYTES", video.row_bytes);
    /* All destination ranges, reservations, source spans, boot arguments and
     * active boot objects were validated before the first upper-RAM store. */
    for (unsigned i = 0; i < p->nsegs; ++i) {
        const struct miami_segment *s = &p->segs[i];
        uintptr_t dst = MIAMI_RAM_BASE + s->vmaddr - p->virt_base;
        copy_bytes(dst, _payload_start + s->file_off, s->file_size);
        zero_bytes(dst + s->file_size, s->vmsize - s->file_size);
    }
    copy_bytes(plan.adt_pa, _payload_start + p->adt_off, p->adt_size);
    miami_store_le((void *)(plan.adt_pa + plan.fb_reg_off), video.base, 8);
    miami_store_le((void *)(plan.adt_pa + plan.fb_reg_off + 8), video.row_bytes * video.height, 8);
    miami_store_le((void *)(plan.adt_pa + plan.fb_stride_off), video.row_bytes, 4);
    zero_bytes(plan.boot_args_pa, MIAMI_PAGE);
    struct boot_args *ba = (void *)(uintptr_t)plan.boot_args_pa;
    ba->Revision = ba->Version = 2;
    ba->virtBase = p->virt_base; ba->physBase = MIAMI_RAM_BASE;
    ba->memSize = ba->memSizeActual = MIAMI_RAM_SIZE;
    ba->topOfKernelData = plan.top;
    ba->Video = (struct boot_video){video.base, 1, video.row_bytes, video.width, video.height, 32};
    ba->deviceTreeP = p->virt_base + plan.adt_pa - MIAMI_RAM_BASE;
    ba->deviceTreeLength = p->adt_size;
    for (unsigned i = 0; i < sizeof(ba->CommandLine); ++i) ba->CommandLine[i] = p->cmdline[i];
    message("XNU: jumping; manual reset if stopped\n");
    __asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
    ((void (*)(uint64_t))(uintptr_t)plan.entry_pa)(plan.boot_args_pa);
    message("XNU returned unexpectedly\n");
}
int strcmp(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return (unsigned char)*a - (unsigned char)*b;
}
