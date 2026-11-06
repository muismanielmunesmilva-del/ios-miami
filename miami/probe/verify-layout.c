/* SPDX-License-Identifier: MIT
 * Validate the actual target dump with the same guards as the bare-metal probe.
 */
#include <stdio.h>
#include <stdlib.h>
#include "layout.h"
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    if (fseek(f, 0, SEEK_END)) return 2;
    long size = ftell(f);
    if (size < 40 || size > 0x200000 || fseek(f, 0, SEEK_SET)) return 2;
    void *blob = malloc((size_t)size);
    if (!blob || fread(blob, 1, (size_t)size, f) != (size_t)size) return 2;
    fclose(f);
    struct probe_layout layout;
    int result = probe_layout_from_fdt(blob, &layout);
    free(blob);
    if (result) { fprintf(stderr, "layout rejected: %d\n", result); return 1; }
    printf("validated: console=0x%llx size=0x%x restart_reason=0x%llx\n",
        (unsigned long long)layout.console, layout.console_size,
        (unsigned long long)layout.restart_reason);
    return 0;
}
