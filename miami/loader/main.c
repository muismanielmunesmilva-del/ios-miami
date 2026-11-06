/* SPDX-License-Identifier: MIT
 * MMU-off single-CPU XNU handoff. No storage driver, reset or CPU_ON calls.
 */
#include "plan.h"
#include "../probe/display.h"
#include "../probe/layout.h"
#include <libfdt.h>
extern char _head[], _end[], _payload_start[], _payload_end[];
/* Linux persistent_ram_buffer: signature, start, size, then console bytes.
 * Use only the FDT-validated ramoops console. No persistent storage writes. */
static volatile uint32_t *trace_header;
static volatile uint8_t *trace_bytes;
static uint32_t trace_used;
static int exception_active;
static void put(char c)
{
    if (trace_header && trace_used < 4096) trace_bytes[trace_used++] = (uint8_t)c;
    screen_put(c);
}
static void commit(void)
{
    if (trace_header) {
        __asm__ volatile("dsb sy" ::: "memory");
        trace_header[1] = trace_used;
        trace_header[2] = trace_used;
        trace_header[0] = 0x43474244;
        __asm__ volatile("dsb sy" ::: "memory");
    }
    screen_commit();
}
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
    while (*label) put(*label++);
    put('='); put('0'); put('x');
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned v = (value >> shift) & 15;
        put(v < 10 ? '0' + v : 'a' + v - 10);
    }
    put('\n'); commit();
}
static void message(const char *text)
{
    while (*text) put(*text++);
    commit();
}
unsigned probe_exception(unsigned slot)
{
    if (exception_active) return 0;
    exception_active = 1;
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
    if (el != 4 || (control & 1)) return; /* physical accesses require MMU off */
    struct probe_layout layout;
    int valid_fdt = !fdt_check_header(fdt) && fdt_totalsize(fdt) <= 0x200000 &&
        !fdt_check_full(fdt, fdt_totalsize(fdt));
    int target = valid_fdt ? probe_layout_from_fdt(fdt, &layout) : -1;
    /* The ring is initialized before display access, but only after target
     * validation and with caches off, matching the proven probe console ABI. */
    if (!target && !(control & 0x1005) && layout.console_size >= 4108) {
        trace_header = (volatile uint32_t *)(uintptr_t)layout.console;
        trace_bytes = (volatile uint8_t *)(uintptr_t)(layout.console + 12);
        trace_header[0] = trace_header[1] = trace_header[2] = 0;
        message("MIAMI XNU loader 0004: before display\n");
    }
    screen_init(control);
    message("MIAMI XNU loader 0004\n");
    probe_hex("CurrentEL", el); probe_hex("SCTLR", control);
    probe_hex("IMAGE_BASE", (uintptr_t)_head);
    if (control & 0x1005) { message("Unexpected caches enabled; stopped\n"); return; }
    if (!valid_fdt) { message("Invalid live FDT; stopped\n"); return; }
    int result = miami_fdt_ram_allowed(fdt, fdt_totalsize(fdt));
    probe_hex("RAM_LAYOUT", (uint32_t)result);
    if (result || !live_objects_clear(fdt)) return;
    probe_hex("TARGET_LAYOUT", (uint32_t)target);
    if (target) return;
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
    message("XNU segment copy begin\n");
    for (unsigned i = 0; i < p->nsegs; ++i) {
        const struct miami_segment *s = &p->segs[i];
        uintptr_t dst = MIAMI_RAM_BASE + s->vmaddr - p->virt_base;
        copy_bytes(dst, _payload_start + s->file_off, s->file_size);
        zero_bytes(dst + s->file_size, s->vmsize - s->file_size);
        probe_hex("COPIED_SEGMENT", i);
    }
    __asm__ volatile("dsb sy" ::: "memory");
    for (unsigned i = 0; i < p->nsegs; ++i) {
        const struct miami_segment *s = &p->segs[i];
        uintptr_t dst = MIAMI_RAM_BASE + s->vmaddr - p->virt_base;
        result = miami_copy_matches((const volatile void *)dst,
            _payload_start + s->file_off, s->file_size, s->vmsize);
        if (result) {
            probe_hex("READBACK_BAD_SEGMENT", i);
            probe_hex("READBACK_RESULT", (uint32_t)result);
            return;
        }
    }
    probe_hex("READBACK_RESULT", 0);
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
    __asm__ volatile("dsb sy" ::: "memory");
    const volatile struct boot_args *rb = ba;
    result = rb->Revision != 2 || rb->Version != 2 || rb->virtBase != p->virt_base ||
        rb->physBase != MIAMI_RAM_BASE || rb->memSize != MIAMI_RAM_SIZE ||
        rb->topOfKernelData != plan.top || rb->deviceTreeP != p->virt_base + plan.adt_pa - MIAMI_RAM_BASE ||
        rb->deviceTreeLength != p->adt_size || rb->Video.base != video.base ||
        rb->Video.row_bytes != video.row_bytes || rb->Video.width != video.width ||
        rb->Video.height != video.height || rb->Video.depth != 32 || rb->bootFlags != 0 ||
        rb->memSizeActual != MIAMI_RAM_SIZE ||
        miami_copy_matches(rb->CommandLine, p->cmdline, sizeof(p->cmdline), sizeof(p->cmdline));
    probe_hex("BOOT_ARGS_READBACK", result);
    if (result) return;
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
