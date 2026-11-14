#ifndef MIAMI_REMOTE_ROOT_BOUNDS_H
#define MIAMI_REMOTE_ROOT_BOUNDS_H
#include <stdint.h>

/* Return 0 only for a bounded, read-only request. */
static inline int
miami_root_block_bounds(int is_read, int64_t sector, uint32_t count,
    uint64_t image_size, uint64_t *offset)
{
    if (!is_read) return 1;
    if (!offset || sector < 0 || (uint64_t)sector > UINT64_MAX / 512u || count > 65536u)
        return 2;
    uint64_t pos = (uint64_t)sector * 512u;
    if (pos > image_size || count > image_size - pos) return 2;
    *offset = pos;
    return 0;
}
#endif
