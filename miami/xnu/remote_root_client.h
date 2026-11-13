/* Transport-independent, read-only remote-image client.
 * The caller supplies bounded send/receive operations and serialization.
 */
#ifndef MIAMI_REMOTE_ROOT_CLIENT_H
#define MIAMI_REMOTE_ROOT_CLIENT_H
#include "remote_root_protocol.h"

struct miami_root_transport {
    void *context;
    /* send returns 0 on acceptance, nonzero on failure. */
    int (*send)(void *context, const uint8_t *packet, size_t length);
    /* receive returns 1 for a packet, 0 for timeout, -1 for fatal failure.
     * It must bound the wait itself. On success, *length <= capacity.
     */
    int (*receive)(void *context, uint8_t *packet, size_t capacity, size_t *length);
};

struct miami_root_client {
    struct miami_root_transport io;
    uint64_t image_size;
    uint32_t next_sequence;
};

/* These operations do not perform mounting, write requests or hardware I/O.
 * Callers must serialize calls and discard the entire output on read failure.
 * The transport adapter must bound each receive wait and validate its peer.
 */
int miami_root_query_size(struct miami_root_client *client);
int miami_root_read(struct miami_root_client *client, uint64_t offset,
    uint8_t *destination, size_t length);
#endif
