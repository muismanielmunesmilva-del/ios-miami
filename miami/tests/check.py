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
from userspace.build import build as build_init, validate as validate_init

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


def fixture_ctf(name=b'__CTF', protections=1):
    blob = fixture_kernel() + bytes(0x4000)
    va = 0xfffffe0007004000
    struct.pack_into('<II', blob, 16, 3, 72 + 72 + 288)
    blob[104:464] = bytes(360)
    struct.pack_into('<II16s4Q4I', blob, 104, 0x19, 72, name, va + 0x4000,
                     0, 0x4000, 0x4000, protections, protections, 0, 0)
    struct.pack_into('<4I', blob, 176, 5, 288, 6, 68)
    struct.pack_into('<Q', blob, 176 + 16 + 32 * 8, va + 0x200)
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
        library.miami_copy_matches.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
        reference = ctypes.create_string_buffer(b'kernel')
        copied = ctypes.create_string_buffer(b'kernel\0\0\0\0', 10)
        assert library.miami_copy_matches(copied, reference, 6, 10) == 0
        copied[2] = b'X'
        assert library.miami_copy_matches(copied, reference, 6, 10) == -2
        copied[2] = b'r'
        copied[9] = b'X'
        assert library.miami_copy_matches(copied, reference, 6, 10) == -3
        assert library.miami_copy_matches(copied, reference, 11, 10) == -1
        assert library.miami_copy_matches(copied, reference, 0, 0x40000000) == -1
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
        # Real signed EL0 probe appended after synthetic kernel segments. This
        # exercises the actual C handoff validator; no phone or storage IO.
        init = temp / 'miami-init.macho'
        init_info = build_init(init)
        root_payload = temp / 'ram-root.bin'
        payload.package(kernel, root_payload, init)
        rooted = root_payload.read_bytes()
        assert accepts(rooted)
        ao, az = struct.unpack_from('<2Q', rooted, 0x20)
        assert root_payload.with_suffix('.adt').read_bytes() == rooted[ao:ao + az]
        tree, _ = adt.parse(rooted[ao:ao + az])
        chosen = next(c for c in tree.children if c.name == 'chosen')
        mmap = next(c for c in chosen.children if c.name == 'memory-map')
        rd = mmap.prop('RAMDisk')
        rd_offset = rooted.index(b'RAMDisk' + bytes(25), ao) + 36
        n = struct.unpack_from('<I', rooted, 12)[0]
        last = 0x2a8 + (n - 1) * 32
        va, size, fileoff, filesize = struct.unpack_from('<4Q', rooted, last)
        assert rooted[fileoff:fileoff + filesize] == init.read_bytes()
        assert filesize == init_info['bytes'] and struct.unpack('<2Q', rd)[1] == size == 0x8000
        root_bad = [(rd_offset, '<Q', 0x85200000), (rd_offset + 8, '<Q', 0x4000),
                    (rd_offset + 8, '<Q', 0x100000), (last + 24, '<Q', 0),
                    (fileoff, '<I', 0), (fileoff + 4, '<I', 0x1000007),
                    (0x18, '<Q', va), (0x30, '<Q', va + size + 0x4000)]
        for offset, fmt, value in root_bad:
            bad = bytearray(rooted); struct.pack_into(fmt, bad, offset, value)
            assert not accepts(bad), ('RAM root', offset, value)
        for old, new in [(b'rd=md0', b'rd=md1'), (b'rd=md0', b'xx=md0')]:
            assert not accepts(rooted.replace(old, new))
        duplicate_arg = bytearray(rooted)
        line = (payload.CMDLINE + ' rd=md0 rd=md0').encode()
        duplicate_arg[0x48:0x2a8] = line + bytes(608 - len(line))
        assert not accepts(duplicate_arg)
        def changed_adt(change):
            t, _ = adt.parse(rooted[ao:ao + az])
            ch = next(c for c in t.children if c.name == 'chosen')
            mm = next(c for c in ch.children if c.name == 'memory-map')
            change(ch, mm)
            encoded = adt.serialize(t)
            result = bytearray(rooted[:ao] + encoded)
            struct.pack_into('<Q', result, 0x28, len(encoded))
            result += bytes(-len(result) % 16)
            return result
        def duplicate(ch, mm):
            mm.props.append(('RAMDisk', 0, rd))
        def misplaced(ch, mm):
            mm.props = [p for p in mm.props if p[0] != 'RAMDisk']
            ch.props.append(('RAMDisk', 0, rd))
        assert not accepts(changed_adt(duplicate))
        assert not accepts(changed_adt(misplaced))
        assert not accepts(valid[:0x48] + valid[0x48:].replace(b'debug=0xc', b'rd=md0   ', 1))
        damaged = bytearray(init.read_bytes()); damaged[1024] ^= 1
        try:
            validate_init(damaged)
        except ValueError:
            pass
        else:
            raise AssertionError('PID1 signed code corruption accepted')
        damaged[1024] ^= 1
        damaged[8] = 2  # arm64e is not executable on this boot CPU.
        try:
            validate_init(damaged)
        except ValueError:
            pass
        else:
            raise AssertionError('arm64e PID1 accepted')
        ctf_kernel = temp / 'SYNTHETIC-CTF-NOT-XNU.macho'
        ctf_kernel.write_bytes(fixture_ctf())
        ctf_payload = temp / 'ctf.bin'
        payload.package(ctf_kernel, ctf_payload)
        assert accepts(ctf_payload.read_bytes())
        assert struct.unpack_from('<I', ctf_payload.read_bytes(), 12)[0] == 1, 'CTF must not be loaded'
        for bad in (fixture_ctf(b'__DATA'), fixture_ctf(protections=5)):
            ctf_kernel.write_bytes(bad)
            try:
                payload.package(ctf_kernel, ctf_payload)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid zero-VM segment was accepted')
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
        print('PASS: valid payload and signed RAM-root handoff; root range/size/entry/type/argument failures and signed-code corruption rejected; 11 malformed/truncated payloads rejected; one-CPU ADT; '
              'file-only CTF skipped with invalid variants rejected; four reservation/bank failures rejected; '
              '>2-MiB payload loader cross-compiled and linked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtc', required=True, type=Path)
    parser.add_argument('--live-fdt', type=Path)
    args = parser.parse_args()
    check(args.dtc, args.live_fdt)
