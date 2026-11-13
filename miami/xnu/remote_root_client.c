#include "remote_root_client.h"

#define MIAMI_ROOT_ATTEMPTS 5u
#define MIAMI_ROOT_PACKETS_PER_ATTEMPT 8u

static int
exchange(struct miami_root_client *client, uint64_t offset, uint16_t request_length,
    uint8_t *out, uint16_t expected_length)
{
    uint8_t request[MIAMI_ROOT_REQUEST_SIZE];
    uint8_t reply[MIAMI_ROOT_RESPONSE_HEADER_SIZE + MIAMI_ROOT_MAX_READ];
    uint32_t sequence;
    if (client == NULL || client->io.send == NULL || client->io.receive == NULL ||
        out == NULL || client->next_sequence == 0) {
        return -1;
    }
    sequence = client->next_sequence++;
    if (miami_root_encode_request(request, sizeof(request), sequence, offset,
        request_length) != 0) {
        return -1;
    }
    for (unsigned attempt = 0; attempt < MIAMI_ROOT_ATTEMPTS; attempt++) {
        if (client->io.send(client->io.context, request, sizeof(request)) != 0) {
            continue;
        }
        for (unsigned poll = 0; poll < MIAMI_ROOT_PACKETS_PER_ATTEMPT; poll++) {
            size_t received = 0;
            const uint8_t *payload = NULL;
            int status = client->io.receive(client->io.context, reply, sizeof(reply), &received);
            if (status < 0) return -1;
            if (status == 0) break;
            if (status != 1 || received > sizeof(reply) ||
                miami_root_decode_response(reply, received, sequence, offset,
                    expected_length, &payload) != 0) {
                continue;
            }
            for (unsigned i = 0; i < expected_length; i++) out[i] = payload[i];
            return 0;
        }
    }
    return -1;
}

int
miami_root_query_size(struct miami_root_client *client)
{
    uint8_t data[8];
    uint64_t size = 0;
    if (client == NULL) return -1;
    client->image_size = 0;
    if (exchange(client, 0, 0, data, sizeof(data)) != 0) return -1;
    for (unsigned i = 0; i < sizeof(data); i++) size = (size << 8) | data[i];
    if (size < 1536 || (size & 511) != 0) return -1;
    client->image_size = size;
    return 0;
}

int
miami_root_read(struct miami_root_client *client, uint64_t offset,
    uint8_t *destination, size_t length)
{
    if (client == NULL || destination == NULL || client->image_size == 0 ||
        offset > client->image_size || length > client->image_size - offset) return -1;
    while (length != 0) {
        uint16_t chunk = length > MIAMI_ROOT_MAX_READ ? MIAMI_ROOT_MAX_READ : (uint16_t)length;
        if (exchange(client, offset, chunk, destination, chunk) != 0) return -1;
        offset += chunk;
        destination += chunk;
        length -= chunk;
    }
    return 0;
}
