#!/usr/bin/env python3
"""Exercise the actual SPI transfer routine with a mocked GENI engine."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'xnu/miami_touch.c').read_text()
start = source.index('static bool\ngeni_transfer(')
end = source.index('static bool\ngoodix_read(', start)
prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#define GENI_STATUS 1
#define GENI_M_IRQ_CLEAR 2
#define SPI_TX_TRANS_LEN 3
#define SPI_RX_TRANS_LEN 4
#define GENI_M_CMD0 5
#define GENI_TX_FIFO_STATUS 6
#define GENI_TX_FIFO 7
#define GENI_M_IRQ_STATUS 8
#define M_ERRORS 0x100u
#define M_CMD_DONE 1u
#define SPI_TX_ONLY 1u
#define SPI_FULL_DUPLEX (3u << 27)
#define NSEC_PER_MSEC 1000000
static unsigned touch_se, touch_fifo_depth=16, txwords, cmd, rxlen_writes, calls, drained;
static void touch_wr(unsigned b,unsigned r,unsigned v) {
    (void)b; if(r==GENI_M_CMD0) cmd=v; if(r==GENI_TX_FIFO) txwords++;
    if(r==SPI_RX_TRANS_LEN) rxlen_writes++;
}
static unsigned touch_rd(unsigned b,unsigned r) {
    (void)b; if(r==GENI_M_IRQ_STATUS) return txwords>=2 ? M_CMD_DONE : 0; return 0;
}
static void geni_drain(uint8_t *p,unsigned n,unsigned *v) {
    calls++; if(txwords>=2 && !drained) {
        for(unsigned i=0;i<n;i++) p[i]=(uint8_t)i;
        *v=n; drained=1;
    }
}
static int PE_parse_boot_argn(const char *s,void *p,unsigned n) {
    (void)s; (void)p; (void)n; return 0;
}
static void delay(int n) { (void)n; }
static void geni_recover(void) { assert(0); }
static void clock_interval_to_deadline(unsigned a,unsigned b,uint64_t *d) {
    (void)a; (void)b; *d=100;
}
static uint64_t mach_absolute_time(void) { return 0; }
'''
suffix = r'''
int main(void) {
    uint8_t tx[8]={0}, rx[8]={0};
    assert(geni_transfer(tx,0,8));
    assert(cmd==(SPI_TX_ONLY<<27) && rxlen_writes==0 && calls==0);
    txwords=cmd=rxlen_writes=calls=drained=0;
    assert(geni_transfer(tx,rx,8));
    assert(cmd==SPI_FULL_DUPLEX && rxlen_writes==1 && calls>0 && rx[7]==7);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-touch-spi-') as tmp:
    test = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    test.write_text(prefix + source[start:end] + suffix)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: TX-only write and full-duplex read use separate GENI commands')
