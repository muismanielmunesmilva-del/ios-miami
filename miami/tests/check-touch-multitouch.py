#!/usr/bin/env python3
"""Check real contact validation for ten fingers and malformed frames."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngoodix_finger_ids_valid(')
end = source.index('static void\ngoodix_log_bad_frame(', start)
checksum_start = source.index('static bool\ngoodix_checksum_valid(')
checksum_end = source.index('static bool\ngoodix_checksum_ok(', checksum_start)
prefix = '#include <stdint.h>\n#include <stdbool.h>\n#include <assert.h>\n#define GOODIX_MAX_TOUCHES 10u\n#define GOODIX_STATUS_TOUCH 0x80u\n'
suffix = r'''
int main(void) {
    uint8_t frame[90] = {0};
    assert(goodix_finger_ids_valid(frame, 0));
    for (unsigned i=0; i<10; i++) frame[8+8*i] = (uint8_t)((i<<4)|2);
    assert(goodix_finger_ids_valid(frame, 10));
    assert(!goodix_finger_ids_valid(frame, 11));
    frame[8+8*9] = frame[8];
    assert(!goodix_finger_ids_valid(frame, 10));
    frame[8+8*9] = 0xa2;
    assert(!goodix_finger_ids_valid(frame, 10));
    frame[8+8*9] = 0x91;
    assert(!goodix_finger_ids_valid(frame, 10));
    frame[8+8*9] = 0x92; frame[3] = 0x10;
    assert(!goodix_finger_ids_valid(frame, 10));
    for (unsigned i=0; i<90; i++) frame[i]=0;
    frame[0]=0x80; frame[2]=3; frame[6]=0x83;
    frame[8]=2; frame[16]=0x12; frame[24]=0x22; frame[32]=0x36;
    uint32_t count=0;
    assert(goodix_frame_valid(frame, &count) && count==3);
    frame[17]=1; assert(!goodix_frame_valid(frame, &count));
    frame[17]=0; frame[6]=0; assert(!goodix_frame_valid(frame, &count));
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-multitouch-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[checksum_start:checksum_end] + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
assert 'goodix_read(touch_report_addr, report, sizeof(report))' in source
assert 'goodix_read(touch_report_addr + 26u' not in source
print('PASS: complete report and validated distinct finger IDs')
