#!/usr/bin/env python3
"""Host checks of actual loader rejection paths, plus an AArch64 link check.

The tiny synthetic Mach-O is NOT an XNU kernel. Compile-only mode never
packages a boot.img and this test never contacts a phone.
"""
import argparse
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

PORT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PORT / 'miami/loader'), str(PORT / 'miami/xnu'), str(PORT / 'tools')]
import payload
import mkadt
import adt

DTS = '''/dts-v1/;
/ { #address-cells=<2>; #size-cells=<2>;
 memory { device_type="memory"; reg=<1 0x80000000 1 0>; };
 reserved-memory { #address-cells=<2>; #size-cells=<2>; ranges;
  ramoops_mem { reg=<0 0xaf000000 0 0xbf800>; record-size=<0x3f800>; console-size=<0x40000>; pmsg-size=<0x40000>; };
  splash { reg=<0 0x85200000 0 0xc00000>; };
  dynamic { size=<0 0x100000>; alloc-ranges=<0 0x80000000 0 0x40000000>; };
 };
 soc { #address-cells=<1>; #size-cells=<1>;
  spi@4a80000 { goodix_ts_spi@0 { compatible="goodix,gt9916S"; }; };
  qcom,msm-imem@c125000 { reg=<0xc125000 0x1000>; restart_reason@65c { reg=<0x65c 4>; }; };
  interrupt-controller@f200000 { reg=<0xf200000 0x10000 0xf240000 0x100000>; };
  timer { clock-frequency=<19200000>; interrupts=<1 1 0xff08 1 2 0xff08 1 3 0xff08 1 0 0xff08>; };
 };
};'''


def run(*args, **kwargs):
    subprocess.run([str(v) for v in args], check=True, **kwargs)


def fixture_kernel(size=0x4000):
    blob = bytearray(size)
    va = 0xfffffe0007004000
    struct.pack_into('<8I', blob, 0, 0xfeedfacf, 0x100000c, 0, 2, 2, 72 + 288, 0, 0)
    struct.pack_into('<II16s4Q4I', blob, 32, 0x19, 72, b'__TEXT', va, size, 0, size, 5, 5, 0, 0)
    struct.pack_into('<4I', blob, 104, 5, 288, 6, 68)
    struct.pack_into('<Q', blob, 104 + 16 + 32 * 8, va + 0x200)
    return blob


def check(dtc, live_fdt=None):
    dtc = dtc.resolve()
    with tempfile.TemporaryDirectory(prefix='miami-host-') as folder:
        temp = Path(folder)
        shared = temp / 'libplan.so'
        libsrc = dtc / 'libfdt'
        run('gcc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror', '-I' + str(libsrc),
            PORT / 'miami/loader/plan.c', PORT / 'miami/loader/ram.c',
            libsrc / 'fdt.c', libsrc / 'fdt_ro.c', libsrc / 'fdt_check.c', '-o', shared)
        library = ctypes.CDLL(str(shared))
        library.miami_payload_plan.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
        library.miami_fdt_ram_allowed.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        kernel = temp / 'SYNTHETIC-NOT-XNU.macho'
        kernel.write_bytes(fixture_kernel())
        packed = temp / 'fixture.bin'
        payload.package(kernel, packed)
        valid = packed.read_bytes()

        def accepts(blob):
            buf = ctypes.create_string_buffer(bytes(blob))
            result = ctypes.create_string_buffer(64)
            return library.miami_payload_plan(buf, len(blob), result) == 0

        assert accepts(valid)
        assert not accepts(valid[:32])
        adt_off, adt_size = struct.unpack_from('<2Q', valid, 0x20)
        assert not accepts(valid[:adt_off + adt_size - 1])
        mutations = [(0, '<8s', b'SWEETXNU'), (12, '<I', 65), (0x38, '<Q', 0x9c000000),
                     (0x40, '<Q', 0xffffffffffffffff), (0x20, '<Q', len(valid) + 8),
                     (0x18, '<Q', 0xfffffe00f0000000), (0x2a8 + 8, '<Q', 0x40000000),
                     (0x2a8 + 16, '<Q', len(valid) + 8), (0x2a8 + 24, '<Q', 0x8000)]
        for offset, fmt, value in mutations:
            bad = bytearray(valid)
            struct.pack_into(fmt, bad, offset, value)
            assert not accepts(bad), (offset, fmt, value)
        root = mkadt.build(seed=bytes(range(64)))
        assert len(next(c for c in root.children if c.name == 'cpus').children) == 1
        assert all('ufs' not in c.name and 'usb' not in c.name for c in root.children)
        encoded = adt.serialize(root)
        assert adt.parse(encoded)[1] == len(encoded)

        def compile_dts(text, name):
            source, output = temp / (name + '.dts'), temp / (name + '.dtb')
            source.write_text(text)
            run('dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', output, source)
            return output

        fdt = compile_dts(DTS, 'fixture')
        def ram_ok(path):
            data = ctypes.create_string_buffer(path.read_bytes())
            return library.miami_fdt_ram_allowed(data, len(path.read_bytes())) == 0
        assert ram_ok(fdt)
        assert not ram_ok(compile_dts(DTS.replace('0 0x85200000 0 0xc00000', '1 0x80000000 0 0x4000'), 'reserved-overlap'))
        assert not ram_ok(compile_dts(DTS.replace('0 0x80000000 0 0x40000000', '1 0x80000000 0 0x40000000'), 'pool-overlap'))
        assert not ram_ok(compile_dts(DTS.replace('alloc-ranges=<0 0x80000000 0 0x40000000>;', ''), 'unbounded-pool'))
        assert not ram_ok(compile_dts(DTS.replace('reg=<1 0x80000000 1 0>', 'reg=<0 0x80000000 0 0x40000000>'), 'missing-bank'))
        if live_fdt:
            assert ram_ok(live_fdt), 'Private live FDT rejects the upper-RAM plan'
        # Exercise BSS/stack references beyond ADR's +/-1-MiB reach. A real
        # kernel is much larger than the diagnostic probes used previously.
        kernel.write_bytes(fixture_kernel(0x204000))
        run('bash', PORT / 'miami/loader/build.sh', kernel, dtc, '/not-used-in-compile-only', fdt,
            env={**os.environ, 'MIAMI_COMPILE_ONLY': '1'})
        print('PASS: valid payload; 11 malformed/truncated payloads rejected; one-CPU ADT; '
              'four reservation/bank failures rejected; >2-MiB payload loader cross-compiled and linked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtc', required=True, type=Path)
    parser.add_argument('--live-fdt', type=Path)
    args = parser.parse_args()
    check(args.dtc, args.live_fdt)
