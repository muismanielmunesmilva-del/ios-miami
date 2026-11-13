#!/usr/bin/env python3
"""Check real contact validation for ten fingers and malformed frames."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngoodix_finger_ids_valid(')
end = source.index('/* Match Goodix Berlin', start)
prefix = '#include <stdint.h>\n#include <stdbool.h>\n#include <assert.h>\n#define GOODIX_MAX_TOUCHES 10u\n'
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
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-multitouch-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
assert 'goodix_read(touch_report_addr, report, sizeof(report))' in source
assert 'goodix_read(touch_report_addr + 26u' not in source
print('PASS: complete report and validated distinct finger IDs')
