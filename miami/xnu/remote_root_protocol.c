#include "remote_root_protocol.h"

static void
put_be(uint8_t *out, uint64_t value, unsigned size)
{
    for (unsigned i = 0; i < size; i++) {
        out[size - i - 1] = (uint8_t)value;
        value >>= 8;
    }
}

static uint64_t
get_be(const uint8_t *in, unsigned size)
{
    uint64_t value = 0;
    for (unsigned i = 0; i < size; i++) {
        value = (value << 8) | in[i];
    }
    return value;
}

int
miami_root_encode_request(uint8_t *out, size_t capacity, uint32_t sequence,
    uint64_t offset, uint16_t length)
{
    if (out == NULL || capacity < MIAMI_ROOT_REQUEST_SIZE ||
        length > MIAMI_ROOT_MAX_READ || (length == 0 && offset != 0)) {
        return -1;
    }
    out[0] = 'M'; out[1] = 'B'; out[2] = 'R'; out[3] = '1';
    put_be(out + 4, sequence, 4);
    put_be(out + 8, offset, 8);
    put_be(out + 16, length, 2);
    return 0;
}

int
miami_root_decode_response(const uint8_t *packet, size_t packet_size,
    uint32_t sequence, uint64_t offset, uint16_t expected_length,
    const uint8_t **payload)
{
    if (payload != NULL) {
        *payload = NULL;
    }
    if (packet == NULL || payload == NULL || expected_length == 0 ||
        expected_length > MIAMI_ROOT_MAX_READ ||
        packet_size != MIAMI_ROOT_RESPONSE_HEADER_SIZE + (size_t)expected_length ||
        packet[0] != 'M' || packet[1] != 'B' || packet[2] != 'S' || packet[3] != '1' ||
        get_be(packet + 4, 4) != sequence || packet[8] != 0 ||
        get_be(packet + 9, 8) != offset || get_be(packet + 17, 2) != expected_length) {
        return -1;
    }
    *payload = packet + MIAMI_ROOT_RESPONSE_HEADER_SIZE;
    return 0;
}
