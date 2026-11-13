#!/usr/bin/env python3
"""Exercise bounded retry and validation using the actual driver helpers."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngoodix_checksum_valid(')
end = source.index('/* Goodix Berlin-D connectivity check:', start)
prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#define GOODIX_FW_VERSION 0x10014u
#define GOODIX_IC_INFO 0x10070u
static unsigned calls, succeed_on;
static bool goodix_read(uint32_t addr, uint8_t *p, uint32_t len) {
    calls++;
    memset(p, 0, len);
    if (calls < succeed_on) return true;
    if (addr == GOODIX_FW_VERSION) {
        assert(len == 28); p[0] = 1; p[26] = 1;
    } else {
        assert(addr == GOODIX_IC_INFO && len == 256);
        p[0] = 40; p[38] = 40;
    }
    return true;
}
static void delay(unsigned us) { (void)us; }
'''
suffix = r'''
int main(void) {
    uint8_t buf[256]; unsigned attempts=0; uint32_t len=0;
    succeed_on=2; assert(goodix_read_version_retry(buf,&attempts));
    assert(calls==2 && attempts==2);
    calls=0; succeed_on=3; assert(!goodix_read_version_retry(buf,&attempts));
    assert(calls==2 && attempts==2);
    calls=0; succeed_on=3; assert(goodix_read_info_retry(buf,&len,&attempts));
    assert(calls==3 && attempts==3 && len==40);
    calls=0; succeed_on=4; assert(!goodix_read_info_retry(buf,&len,&attempts));
    assert(calls==3 && attempts==3);
    assert(goodix_le32((const uint8_t[]){1,2,3,4})==0x04030201);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-retry-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: invalid responses retried within Goodix bounds')
