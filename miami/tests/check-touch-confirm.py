#!/usr/bin/env python3
"""Exercise the Goodix confirmation routine with mocked SPI transfers."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngoodix_confirm(')
end = source.index('static bool\ngoodix_probe(', start)
prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define GOODIX_BOOTOPTION 0x10000u
static int writes, reads, mode;
static bool goodix_write(uint32_t a, const uint8_t *p, unsigned n) {
    assert(a == GOODIX_BOOTOPTION && n == 8 && p[0] == 0xaa);
    writes++; return mode != 2;
}
static bool goodix_read(uint32_t a, uint8_t *p, unsigned n) {
    assert(a == GOODIX_BOOTOPTION && n == 8); reads++;
    memset(p, (mode == 0 || (mode == 1 && reads == 3)) ? 0xaa : 0, n);
    return true;
}
static void delay(unsigned n) { assert(n == 5000); }
'''
suffix = r'''
int main(void) {
    mode = 0; assert(goodix_confirm() && writes == 1 && reads == 1);
    mode = 1; writes = reads = 0;
    assert(goodix_confirm() && writes == 3 && reads == 3);
    mode = 2; writes = reads = 0;
    assert(!goodix_confirm() && writes == 3 && reads == 0);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-confirm-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: Goodix confirmation success, bounded retries and failed-write handling')
