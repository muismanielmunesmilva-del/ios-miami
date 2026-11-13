#!/usr/bin/env python3
"""Exercise the driver's actual chip-select command sequence with mocks."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngeni_cs(')
end = source.index('static bool\ngoodix_read(', start)
prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
#define GENI_M_IRQ_CLEAR 1
#define GENI_M_CMD0 2
#define GENI_M_IRQ_STATUS 3
#define GENI_RX_FIFO_STATUS 4
#define GENI_RX_FIFO 5
#define SPI_CS_ASSERT 8u
#define SPI_CS_DEASSERT 9u
#define M_ERRORS 2u
#define M_CMD_DONE 1u
#define NSEC_PER_MSEC 1000000
static unsigned touch_se, current_cmd, cmds[4], ncmd, recovered, transfers;
static unsigned touch_fifo_depth=16, touch_fifo_stale_words, fifo_words, fifo_reads;
static bool fail_assert, fail_release, fail_transfer, disabled;
static void touch_wr(unsigned base, unsigned reg, unsigned value) {
    (void)base; if (reg==GENI_M_CMD0) { current_cmd=value>>27; cmds[ncmd++]=current_cmd; }
}
static unsigned touch_rd(unsigned base, unsigned reg) {
    (void)base;
    if (reg==GENI_RX_FIFO_STATUS) return fifo_words;
    if (reg==GENI_RX_FIFO) { fifo_reads++; return 0; }
    return ((current_cmd==SPI_CS_ASSERT && fail_assert) ||
            (current_cmd==SPI_CS_DEASSERT && fail_release)) ? M_ERRORS : M_CMD_DONE;
}
static void clock_interval_to_deadline(unsigned a,unsigned b,uint64_t *d) {(void)a;(void)b;*d=100;}
static uint64_t mach_absolute_time(void) {return 0;}
static void geni_recover(void) {recovered++;}
static int PE_parse_boot_argn(const char *s,void *p,unsigned n) {
    (void)s; (void)n; *(int *)p=disabled; return 0;
}
static bool geni_transfer(const uint8_t *tx,uint8_t *rx,uint32_t len) {
    (void)tx; (void)rx; (void)len; transfers++; return !fail_transfer;
}
'''
suffix = r'''
int main(void) {
    assert(geni_transaction(0,0,1));
    assert(ncmd==2 && cmds[0]==SPI_CS_ASSERT && cmds[1]==SPI_CS_DEASSERT && transfers==1);
    ncmd=transfers=0; fifo_words=2;
    assert(geni_transaction(0,0,1) && fifo_reads==2 && touch_fifo_stale_words==2);
    ncmd=transfers=0; fifo_words=17;
    assert(!geni_transaction(0,0,1) && ncmd==0 && transfers==0);
    fifo_words=0;
    ncmd=transfers=0; fail_transfer=true;
    assert(!geni_transaction(0,0,1) && ncmd==2 && cmds[1]==SPI_CS_DEASSERT && transfers==1);
    ncmd=transfers=0; fail_transfer=false; fail_assert=true;
    assert(!geni_transaction(0,0,1) && ncmd==1 && transfers==0 && recovered==1);
    ncmd=transfers=0; fail_assert=false; fail_release=true;
    assert(!geni_transaction(0,0,1) && ncmd==2 && transfers==1 && recovered==2);
    ncmd=transfers=0; fail_release=false; disabled=true;
    assert(!geni_transaction(0,0,1) && ncmd==0 && transfers==0);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-cs-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: chip-select command order and failure paths')
