#pragma once
#include <stdint.h>
void screen_init(uint64_t control);
void screen_put(char c);
void screen_commit(void);
void screen_new_section(void);
struct screen_info { uint64_t base, row_bytes, width, height; };
int screen_handoff(struct screen_info *out);
