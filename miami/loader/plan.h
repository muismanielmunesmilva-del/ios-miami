/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#define MIAMI_RAM_BASE 0x180000000ULL
#define MIAMI_RAM_SIZE 0x3ff00000ULL
#define MIAMI_PANIC_SIZE 0x100000ULL
#define MIAMI_PAGE 0x4000ULL
#define MIAMI_MAX_SEGS 64
struct miami_segment { uint64_t vmaddr, vmsize, file_off, file_size; };
struct miami_payload {
    char magic[8];
    uint32_t version, nsegs;
    uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
    uint64_t phys_base, mem_size;
    char cmdline[608];
    struct miami_segment segs[];
};
struct miami_plan {
    uint64_t entry_pa, adt_pa, boot_args_pa, top;
    uint32_t fb_reg_off, fb_stride_off;
};
int miami_payload_plan(const void *bytes, size_t size, struct miami_plan *out);
int miami_fdt_ram_allowed(const void *fdt, size_t available);
void miami_store_le(void *dst, uint64_t value, unsigned bytes);
