/* SPDX-License-Identifier: MIT
 * Fail closed on overlapping or unbounded reservations in the live FDT.
 */
#include "plan.h"
#include <libfdt.h>
static uint64_t cell64(const fdt32_t *p)
{
    return ((uint64_t)fdt32_to_cpu(p[0]) << 32) | fdt32_to_cpu(p[1]);
}
static int overlap(uint64_t first, uint64_t size)
{
    const uint64_t end = MIAMI_RAM_BASE + MIAMI_RAM_SIZE + MIAMI_PANIC_SIZE;
    if (size > UINT64_MAX - first) return 1;
    return size && first < end && MIAMI_RAM_BASE < first + size;
}
int miami_fdt_ram_allowed(const void *fdt, size_t available)
{
    if (available < 40 || fdt_check_header(fdt) || fdt_totalsize(fdt) > 0x200000 ||
        fdt_totalsize(fdt) > available || fdt_check_full(fdt, available)) return -1;
    int len, memory = fdt_path_offset(fdt, "/memory");
    const fdt32_t *reg = fdt_getprop(fdt, memory, "reg", &len);
    if (!reg || len <= 0 || len % 16) return -2;
    int covered = 0;
    for (int i = 0; i < len / 4; i += 4) {
        uint64_t lo = cell64(reg + i), size = cell64(reg + i + 2);
        covered |= lo <= MIAMI_RAM_BASE && size >= MIAMI_RAM_BASE - lo &&
            MIAMI_RAM_SIZE + MIAMI_PANIC_SIZE <= size - (MIAMI_RAM_BASE - lo);
    }
    if (!covered) return -3;
    int reservations = fdt_num_mem_rsv(fdt);
    if (reservations < 0) return -4;
    for (int i = 0; i < reservations; ++i) {
        uint64_t lo, size;
        if (fdt_get_mem_rsv(fdt, i, &lo, &size) || overlap(lo, size)) return -4;
    }
    int reserved = fdt_path_offset(fdt, "/reserved-memory"), node;
    if (reserved < 0) return -5;
    fdt_for_each_subnode(node, fdt, reserved) {
        reg = fdt_getprop(fdt, node, "reg", &len);
        if (reg) {
            if (len <= 0 || len % 16) return -6;
            for (int i = 0; i < len / 4; i += 4)
                if (overlap(cell64(reg + i), cell64(reg + i + 2))) return -7;
        } else {
            const void *dynamic_size = fdt_getprop(fdt, node, "size", &len);
            if (!dynamic_size) continue;
            reg = fdt_getprop(fdt, node, "alloc-ranges", &len);
            if (!reg || len <= 0 || len % 16) return -8;
            for (int i = 0; i < len / 4; i += 4)
                if (overlap(cell64(reg + i), cell64(reg + i + 2))) return -9;
        }
    }
    return node == -FDT_ERR_NOTFOUND ? 0 : -10;
}
