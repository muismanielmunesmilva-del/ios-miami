#pragma once
#include <stdint.h>
struct probe_layout {
    uint64_t console;
    uint32_t console_size;
    uint64_t restart_reason;
};
int probe_layout_from_fdt(const void *, struct probe_layout *);
