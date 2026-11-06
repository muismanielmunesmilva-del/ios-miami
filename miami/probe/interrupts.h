#pragma once
#include <stdint.h>
void probe_hex(const char *name, uint64_t value);
int gic_timer_test(void);
int gic_handle_irq(void);
