/* SPDX-License-Identifier: MIT
 * Validate the entire copy plan before the loader writes destination RAM.
 * Pure host-testable code. Payload format derives from ios-sweet mkpayload.
 */
#include "plan.h"
#include <string.h>
_Static_assert(offsetof(struct miami_payload, segs) == 0x2a8, "payload ABI");
static uint64_t le(const uint8_t *p, unsigned count)
{
    uint64_t value = 0;
    for (unsigned i = 0; i < count; ++i) value |= (uint64_t)p[i] << (i * 8);
    return value;
}
void miami_store_le(void *dst, uint64_t value, unsigned bytes)
{
    uint8_t *p = dst;
    for (unsigned i = 0; i < bytes; ++i) p[i] = value >> (i * 8);
}
int miami_copy_matches(const volatile void *dst, const void *source, size_t file_size, size_t memory_size)
{
    if (!dst || (!source && file_size) || file_size > memory_size || memory_size > MIAMI_RAM_SIZE) return -1;
    const volatile uint8_t *actual = dst;
    const uint8_t *expected = source;
    for (size_t i = 0; i < file_size; ++i) if (actual[i] != expected[i]) return -2;
    for (size_t i = file_size; i < memory_size; ++i) if (actual[i]) return -3;
    return 0;
}
static int span(uint64_t offset, uint64_t length, uint64_t size)
{
    return offset <= size && length <= size - offset;
}
struct adt_check {
    const uint8_t *data;
    uint64_t size, offset;
    unsigned nodes, fb_count, dram_base, dram_size, reg_count, stride_count, width_count, height_count;
    unsigned chosen_count, mmap_count, rd_count;
    uint64_t rd_pa, rd_size;
    struct miami_plan *plan;
};
static int adt_node(struct adt_check *c, unsigned depth, int parent_chosen)
{
    if (depth > 12 || ++c->nodes > 128 || !span(c->offset, 8, c->size)) return -1;
    uint32_t props = le(c->data + c->offset, 4), children = le(c->data + c->offset + 4, 4);
    c->offset += 8;
    if (!props || props > 128 || children > 64) return -1;
    int fb = 0, chosen = 0, mmap = 0;
    for (unsigned i = 0; i < props; ++i) {
        if (!span(c->offset, 36, c->size)) return -1;
        const uint8_t *key = c->data + c->offset;
        if (!memchr(key, 0, 32)) return -1;
        uint32_t len = le(key + 32, 4);
        if (len & 0x80000000U) return -1; /* no iBoot placeholders in this tree */
        c->offset += 36;
        uint64_t padded = ((uint64_t)len + 3) & ~3ULL;
        if (!span(c->offset, padded, c->size)) return -1;
        const uint8_t *value = c->data + c->offset;
        if (!i) {
            if (strcmp((const char *)key, "name") || !len || !memchr(value, 0, len)) return -1;
            fb = depth == 1 && !strcmp((const char *)value, "miami-fbcon");
            chosen = depth == 1 && !strcmp((const char *)value, "chosen");
            mmap = depth == 2 && parent_chosen && !strcmp((const char *)value, "memory-map");
            c->fb_count += fb;
            c->chosen_count += chosen;
            c->mmap_count += mmap;
        } else if (!strcmp((const char *)key, "RAMDisk")) {
            if (!mmap || len != 16 || c->rd_count++) return -1;
            c->rd_pa = le(value, 8);
            c->rd_size = le(value + 8, 8);
        } else if (fb && !strcmp((const char *)key, "reg")) {
            if (len != 16 || c->reg_count++) return -1;
            c->plan->fb_reg_off = (uint32_t)c->offset;
        } else if (fb && !strcmp((const char *)key, "stride")) {
            if (len != 4 || c->stride_count++) return -1;
            c->plan->fb_stride_off = (uint32_t)c->offset;
        } else if (fb && !strcmp((const char *)key, "width")) {
            if (len != 4 || le(value, 4) != 1080 || c->width_count++) return -1;
        } else if (fb && !strcmp((const char *)key, "height")) {
            if (len != 4 || le(value, 4) != 2400 || c->height_count++) return -1;
        } else if (chosen && !strcmp((const char *)key, "dram-base")) {
            if (len != 8 || le(value, 8) != MIAMI_RAM_BASE || c->dram_base++) return -1;
        } else if (chosen && !strcmp((const char *)key, "dram-size")) {
            if (len != 8 || le(value, 8) != MIAMI_RAM_SIZE || c->dram_size++) return -1;
        }
        c->offset += padded;
    }
    for (unsigned i = 0; i < children; ++i) if (adt_node(c, depth + 1, chosen)) return -1;
    return 0;
}
static uint64_t be(const uint8_t *p, unsigned count)
{
    uint64_t value = 0;
    for (unsigned i = 0; i < count; ++i) value = (value << 8) | p[i];
    return value;
}
static int valid_ramdisk_image(const uint8_t *image, uint64_t file_size)
{
    if (file_size >= MIAMI_PAGE && file_size <= 0x10000ULL &&
        le(image, 4) == 0xfeedfacf && le(image + 4, 4) == 0x100000c &&
        !le(image + 8, 4) && le(image + 12, 4) == 2 && le(image + 16, 4) == 5)
        return 1;
    if (file_size < 2 * MIAMI_PAGE || file_size > 0x4000000ULL || (file_size & (MIAMI_PAGE - 1)))
        return 0;
    uint16_t sig = (uint16_t)be(image + 1024, 2), ver = (uint16_t)be(image + 1026, 2);
    if (!((sig == 0x482b && ver == 4) || (sig == 0x4858 && ver == 5)))
        return 0;
    uint32_t blk_size = (uint32_t)be(image + 1024 + 40, 4);
    uint32_t total_blks = (uint32_t)be(image + 1024 + 44, 4);
    if (blk_size != 4096 || (uint64_t)total_blks * blk_size != file_size)
        return 0;
    if (memcmp(image + 1024, image + file_size - 1024, 512))
        return 0;
    return 1;
}
static int root_arg(const char *s)
{
    int roots = 0;
    while (*s) {
        while (*s == ' ') ++s;
        const char *start = s;
        while (*s && *s != ' ') ++s;
        size_t size = (size_t)(s - start);
        if (size >= 3 && !memcmp(start, "rd=", 3)) {
            if (size != 6 || memcmp(start, "rd=md0", 6) || roots++) return -1;
        }
    }
    return roots;
}
int miami_payload_plan(const void *bytes, size_t size, struct miami_plan *out)
{
    if (((uintptr_t)bytes & 7) || size < sizeof(struct miami_payload) || !out) return -1;
    const struct miami_payload *p = bytes;
    if (memcmp(p->magic, "MIAMIXNU", 8) || p->version != 1 || !p->nsegs ||
        p->nsegs > MIAMI_MAX_SEGS || (p->entry_va & 3) || p->phys_base != MIAMI_RAM_BASE || p->mem_size != MIAMI_RAM_SIZE ||
        (p->virt_base & 0x1ffffffULL) || p->virt_base < 0xffff000000000000ULL ||
        !memchr(p->cmdline, 0, sizeof(p->cmdline))) return -2;
    uint64_t header = sizeof(*p) + (uint64_t)p->nsegs * sizeof(p->segs[0]);
    if (header > size || !p->adt_size || p->adt_size > 0x10000 || (p->adt_off & 7) ||
        p->adt_off < header || !span(p->adt_off, p->adt_size, size)) return -3;
    if (p->kernel_end < p->virt_base || (p->kernel_end & (MIAMI_PAGE - 1))) return -4;
    uint64_t end = p->kernel_end - p->virt_base;
    if (!span(end, p->adt_size + 2 * MIAMI_PAGE, MIAMI_RAM_SIZE)) return -4;
    int entry = 0;
    for (unsigned i = 0; i < p->nsegs; ++i) {
        const struct miami_segment *s = &p->segs[i];
        if (s->vmaddr < p->virt_base || (s->vmaddr & (MIAMI_PAGE - 1)) ||
            !s->vmsize || (s->vmsize & (MIAMI_PAGE - 1)) || s->file_size > s->vmsize ||
            (s->file_off & 7) || s->file_off < header ||
            !span(s->file_off, s->file_size, p->adt_off) ||
            !span(s->vmaddr - p->virt_base, s->vmsize, end)) return -5;
        for (unsigned j = 0; j < i; ++j)
            if (s->vmaddr < p->segs[j].vmaddr + p->segs[j].vmsize &&
                p->segs[j].vmaddr < s->vmaddr + s->vmsize) return -6;
        entry |= p->entry_va >= s->vmaddr && p->entry_va - s->vmaddr < s->file_size;
    }
    if (!entry) return -7;
    struct adt_check c = { .data = (const uint8_t *)bytes + p->adt_off,
        .size = p->adt_size, .plan = out };
    if (adt_node(&c, 0, 0) || c.offset != c.size || c.fb_count != 1 || c.reg_count != 1 ||
        c.stride_count != 1 || c.width_count != 1 || c.height_count != 1 ||
        c.dram_base != 1 || c.dram_size != 1 || c.chosen_count != 1 || c.mmap_count > 1) return -8;
    if (root_arg(p->cmdline) != (int)c.rd_count) return -9;
    if (c.rd_count) {
        const struct miami_segment *s = &p->segs[p->nsegs - 1];
        if (p->nsegs < 2 || c.mmap_count != 1 || !s->file_size ||
            s->file_size > 0x4000000ULL || s->file_size < MIAMI_PAGE ||
            s->vmsize != ((s->file_size + MIAMI_PAGE - 1) & ~(MIAMI_PAGE - 1)) ||
            c.rd_pa != MIAMI_RAM_BASE + s->vmaddr - p->virt_base ||
            c.rd_size != s->vmsize || s->vmaddr + s->vmsize != p->kernel_end ||
            p->entry_va >= s->vmaddr) return -10;
        for (unsigned i = 0; i + 1 < p->nsegs; ++i)
            if (p->segs[i].vmaddr + p->segs[i].vmsize > s->vmaddr) return -10;
        const uint8_t *image = (const uint8_t *)bytes + s->file_off;
        if (!valid_ramdisk_image(image, s->file_size)) return -11;
    }
    out->entry_pa = MIAMI_RAM_BASE + p->entry_va - p->virt_base;
    out->adt_pa = MIAMI_RAM_BASE + end;
    out->boot_args_pa = (out->adt_pa + p->adt_size + MIAMI_PAGE - 1) & ~(MIAMI_PAGE - 1);
    out->top = out->boot_args_pa + MIAMI_PAGE;
    return 0;
}
