/* Wire codec shared by the remote-root bring-up and its host-side tests.
 * This does not initiate network I/O or register a block device.
 */
#ifndef MIAMI_REMOTE_ROOT_PROTOCOL_H
#define MIAMI_REMOTE_ROOT_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define MIAMI_ROOT_REQUEST_SIZE 18u
#define MIAMI_ROOT_RESPONSE_HEADER_SIZE 19u
#define MIAMI_ROOT_MAX_READ 1024u

int miami_root_encode_request(uint8_t *out, size_t capacity, uint32_t sequence,
    uint64_t offset, uint16_t length);

/* Returns 0 for a matching successful reply and -1 otherwise.
 * expected_length is 8 for a size query and the requested count for a read.
 * On success the payload pointer is inside the provided packet.
 */
int miami_root_decode_response(const uint8_t *packet, size_t packet_size,
    uint32_t sequence, uint64_t offset, uint16_t expected_length,
    const uint8_t **payload);

#endif
