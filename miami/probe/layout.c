/* SPDX-License-Identifier: MIT
 * Read-only validation of the measured miami FDT. libfdt parses the blob.
 * The console layout follows Motorola's Linux 5.4 fs/pstore/ram.c.
 */
#include <libfdt.h>
#include "layout.h"

static const fdt32_t *cells(const void *fdt, const char *path,
                            const char *name, int bytes)
{
    int length;
    int node = fdt_path_offset(fdt, path);
    if (node < 0) return 0;
    const fdt32_t *p = fdt_getprop(fdt, node, name, &length);
    return p && length == bytes ? p : 0;
}

static int u32_value(const void *fdt, const char *path, const char *name,
                     uint32_t expected, int optional)
{
    int node = fdt_path_offset(fdt, path), length;
    if (node < 0) return 0;
    const fdt32_t *p = fdt_getprop(fdt, node, name, &length);
    if (!p) return optional && length == -FDT_ERR_NOTFOUND && expected == 0;
    return length == 4 && fdt32_to_cpu(*p) == expected;
}

int probe_layout_from_fdt(const void *fdt, struct probe_layout *out)
{
    if (fdt_check_header(fdt) || fdt_totalsize(fdt) > 0x200000) return -1;
    int touch = fdt_path_offset(fdt, "/soc/spi@4a80000/goodix_ts_spi@0");
    if (touch < 0 || fdt_node_check_compatible(fdt, touch, "goodix,gt9916S")) return -2;
    if (!u32_value(fdt, "/", "#address-cells", 2, 0) ||
        !u32_value(fdt, "/", "#size-cells", 2, 0) ||
        !u32_value(fdt, "/reserved-memory", "#address-cells", 2, 0) ||
        !u32_value(fdt, "/reserved-memory", "#size-cells", 2, 0)) return -3;
    int memory = fdt_path_offset(fdt, "/memory"), memory_bytes;
    const fdt32_t *ram = fdt_getprop(fdt, memory, "reg", &memory_bytes);
    if (!ram || memory_bytes <= 0 || memory_bytes % 16) return -4;
    int valid_ram = 0;
    for (int i = 0; i < memory_bytes / 4; i += 4)
        valid_ram |= fdt32_to_cpu(ram[i + 2]) || fdt32_to_cpu(ram[i + 3]);
    if (!valid_ram) return -4;

    const char *path = "/reserved-memory/ramoops_mem";
    const fdt32_t *reg = cells(fdt, path, "reg", 16);
    if (!reg || fdt32_to_cpu(reg[0]) || fdt32_to_cpu(reg[1]) != 0xaf000000 ||
        fdt32_to_cpu(reg[2]) || fdt32_to_cpu(reg[3]) != 0xbf800) return -5;
    if (!u32_value(fdt, path, "record-size", 0x3f800, 0) ||
        !u32_value(fdt, path, "console-size", 0x40000, 0) ||
        !u32_value(fdt, path, "pmsg-size", 0x40000, 0) ||
        !u32_value(fdt, path, "ftrace-size", 0, 1) ||
        !u32_value(fdt, path, "ecc-size", 0, 1)) return -6;
    /* Linux rounds record-size down to 0x20000. One dump zone consumes
     * the complete 0x3f800-byte remainder, then comes the console zone. */
    out->console = 0xaf03f800;
    out->console_size = 0x40000;
    const fdt32_t *imem = cells(fdt, "/soc/qcom,msm-imem@c125000", "reg", 8);
    const fdt32_t *reason = cells(fdt,
        "/soc/qcom,msm-imem@c125000/restart_reason@65c", "reg", 8);
    if (!imem || !reason || fdt32_to_cpu(imem[0]) != 0xc125000 ||
        fdt32_to_cpu(imem[1]) != 0x1000 || fdt32_to_cpu(reason[0]) != 0x65c ||
        fdt32_to_cpu(reason[1]) != 4) return -7;
    out->restart_reason = 0xc12565c;
    const fdt32_t *gic = cells(fdt, "/soc/interrupt-controller@f200000", "reg", 16);
    if (!gic || fdt32_to_cpu(gic[0]) != 0xf200000 ||
        fdt32_to_cpu(gic[1]) != 0x10000 || fdt32_to_cpu(gic[2]) != 0xf240000 ||
        fdt32_to_cpu(gic[3]) != 0x100000 ||
        !u32_value(fdt, "/soc/timer", "clock-frequency", 19200000, 0)) return -8;
    const fdt32_t *timer = cells(fdt, "/soc/timer", "interrupts", 48);
    if (!timer || fdt32_to_cpu(timer[6]) != 1 || fdt32_to_cpu(timer[7]) != 3) return -9;
    return 0;
}
