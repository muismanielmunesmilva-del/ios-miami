/* SPDX-License-Identifier: MIT */
#include <stdio.h>
#include <stdlib.h>
#include "plan.h"
#ifndef MIAMI_PAYLOAD_ONLY
#include "../probe/layout.h"
#endif
static void *read_file(const char *path, size_t *size, size_t limit)
{
    FILE *f = fopen(path, "rb");
    if (!f || fseek(f, 0, SEEK_END)) exit(2);
    long n = ftell(f);
    if (n <= 0 || (unsigned long)n > limit || fseek(f, 0, SEEK_SET)) exit(2);
    void *p = malloc((size_t)n);
    if (!p || fread(p, 1, (size_t)n, f) != (size_t)n) exit(2);
    fclose(f); *size = n; return p;
}
int main(int argc, char **argv)
{
#ifdef MIAMI_PAYLOAD_ONLY
    if (argc != 2) return 2;
#else
    if (argc != 3) return 2;
#endif
    size_t size;
    void *payload = read_file(argv[1], &size, 90U * 1024 * 1024);
    struct miami_plan plan;
    int p = miami_payload_plan(payload, size, &plan);
#ifdef MIAMI_PAYLOAD_ONLY
    printf("payload copy/ADT plan=%d\n", p);
    free(payload); return p ? 1 : 0;
#else
    size_t fdt_size;
    void *fdt = read_file(argv[2], &fdt_size, 0x200000);
    if (fdt_size < 40) return 2;
    struct probe_layout layout;
    int r = miami_fdt_ram_allowed(fdt, fdt_size);
    if (r) { fprintf(stderr, "FDT RAM validation rejected input: %d\n", r); return 1; }
    int t = probe_layout_from_fdt(fdt, &layout);
    printf("payload=%d, upper-RAM/reservation-layout=%d, target=%d\n", p, r, t);
    free(payload); free(fdt);
    return p || r || t ? 1 : 0;
#endif
}
