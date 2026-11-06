#!/usr/bin/env python3
"""Execute the staged panic/serial console on guarded host framebuffer memory.

Only the ARM barrier and external _doprnt API are mocked. Rendered pixels use
the actual Apple font and are decoded back to text independently of the writer.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def check(source):
    early = (source / 'osfmk/arm64/miami_early.c').read_text()
    early = '\n'.join(line for line in early.splitlines() if not line.startswith('#include'))
    early = early.replace('__asm__ volatile("dsb sy" ::: "memory");', '')
    serial = (source / 'pexpert/arm/pe_serial.c').read_text()
    serial = serial[serial.index('extern unsigned char iso_font[256 * 16];'):]
    serial = serial[:serial.index('static unsigned int\nfbcon_receive_ready')]
    declarations = '''
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define MIAMI 1
unsigned int miami_panic_reserved_rows(void);
static void _doprnt(const char *fmt, va_list *args, void (*put)(char), int radix) {
    char text[8192];
    assert(radix == 16);
    int n = vsnprintf(text, sizeof(text), fmt, *args);
    assert(n >= 0 && (unsigned)n < sizeof(text));
    for (char *p = text; *p; p++) put(*p);
}
'''
    harness = r'''
static uint32_t *allocation, *pixels, *snapshot;
static size_t words;
static void reset(unsigned stride) {
    words = stride * 2400;
    allocation = malloc((words + 2) * sizeof(uint32_t)); assert(allocation);
    for (size_t i = 0; i < words + 2; i++) allocation[i] = 0xdeadbeef;
    pixels = allocation + 1;
    early_fb = pixels; early_stride = stride;
    early_disabled = early_started = early_panicking = early_row = early_col = 0;
    panic_screen_fb = NULL; panic_screen_stride = panic_screen_latched = 0;
    fbcon_base = pixels; fbcon_width = 1080; fbcon_height = 2400; fbcon_stride = stride * 4;
    fbcon_init();
    assert(miami_panic_reserved_rows() == 0);
}
static void guards(void) {
    assert(allocation[0] == 0xdeadbeef && allocation[words + 1] == 0xdeadbeef);
    for (unsigned y = 0; y < 2400; y++)
        for (unsigned x = 1080; x < early_stride; x++)
            assert(pixels[y * early_stride + x] == 0xdeadbeef);
}
static void text(char *out) {
    for (unsigned row = 0; row < 18; row++) {
        for (unsigned col = 0; col < 67; col++) {
            int found = 0;
            for (unsigned c = 32; c <= 126; c++) {
                int equal = 1;
                for (unsigned y = 0; y < 16 && equal; y++)
                    for (unsigned x = 0; x < 8; x++) {
                        unsigned actual = pixels[(row * 32 + y * 2) * early_stride + col * 16 + x * 2] == 0xffffffff;
                        if (actual != ((iso_font[c * 16 + y] >> x) & 1)) { equal = 0; break; }
                    }
                if (equal) { *out++ = (char)c; found = 1; break; }
            }
            assert(found);
        }
        *out++ = '\n';
    }
    *out = 0;
}
static void unchanged(void) {
    assert(!memcmp(snapshot, pixels, early_stride * 576 * sizeof(uint32_t)));
    guards();
}
static void generic(const char *fmt, ...) {
    va_list args; va_start(args, fmt);
    miami_panic_reason(fmt, &args, 0x12345678);
    /* The diagnostic copy must not consume the native panic's arguments. */
    assert(va_arg(args, unsigned) == 42);
    va_end(args);
}
int main(void) {
    for (unsigned stride = 1080; stride <= 1104; stride += 24) {
        reset(stride);
        /* Capture remains usable after the early console has been disabled. */
        miami_early_disable();
        miami_panic_use_framebuffer((uintptr_t)pixels, stride * 4);
        miami_panic_saved_state("Synchronous data abort", 0xfffffe00078f5a88ULL,
            0x1122334455667788ULL, 0xaabbccdd, 0x1234, 0x96000005, 0x78);
        char rendered[18 * 68 + 1]; text(rendered);
        assert(strstr(rendered, "MIAMI FIRST PANIC v1"));
        assert(strstr(rendered, "PC  = 0xfffffe00078f5a88"));
        assert(strstr(rendered, "LR  = 0x1122334455667788"));
        assert(strstr(rendered, "ESR = 0x0000000096000005"));
        assert(strstr(rendered, "FAR = 0x0000000000000078"));
        assert(strstr(rendered, "REASON: Synchronous data abort"));
        snapshot = malloc(stride * 576 * sizeof(uint32_t)); assert(snapshot);
        memcpy(snapshot, pixels, stride * 576 * sizeof(uint32_t));
        for (unsigned i = 0; i < 10000; i++) {
            fbcon_transmit_data('x'); fbcon_transmit_data('\r'); fbcon_transmit_data('\n');
        }
        fbcon_init(); assert(fbcon_transmit_ready());
        early_disabled = 0;
        for (unsigned i = 0; i < 12000; i++) miami_early_putc(i % 11 ? 'z' : '\n');
        miami_panic_saved_state("nested panic", 0, 0, 0, 0, 0, 0);
        generic("nested %u", 42u);
        unchanged(); free(snapshot); free(allocation);

        reset(stride);
        /* Exercise the persistent early alias fallback and generic format. */
        generic("assertion failed: %u", 42u);
        text(rendered);
        assert(strstr(rendered, "STATE: generic panic; no saved registers"));
        assert(strstr(rendered, "CALLER = 0x0000000012345678"));
        assert(strstr(rendered, "assertion failed: 42"));
        guards(); free(allocation);

        reset(stride);
        char huge[6000]; memset(huge, 'A', sizeof(huge) - 1); huge[sizeof(huge) - 1] = 0;
        miami_panic_saved_state(huge, 1, 2, 3, 4, 5, 6);
        guards();
        for (unsigned y = 576; y < 2400; y++)
            for (unsigned x = 0; x < 1080; x++) assert(pixels[y * stride + x] == FBCON_BG);
        free(allocation);
    }
    panic_screen_latched = 0; panic_screen_fb = NULL; early_fb = NULL;
    miami_panic_use_framebuffer(1, 4320);
    miami_panic_use_framebuffer(4, 4316);
    miami_panic_use_framebuffer(4, 8196);
    miami_panic_saved_state("no framebuffer", 0, 0, 0, 0, 0, 0);
    assert(!miami_panic_reserved_rows());
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='miami-panic-') as folder:
        temp = Path(folder)
        c = temp / 'panic.c'
        c.write_text('\n'.join((declarations, (source / 'osfmk/console/iso_font.c').read_text(), early, serial, harness)))
        binary = temp / 'panic'
        subprocess.run(['gcc', '-O2', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: first-panic pixels decode to exact registers/reason; survive 10,000 serial lines, early wrap, reinit and nested panic; guarded strides and long reason stay bounded')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
