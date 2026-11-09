#!/usr/bin/env python3
"""Package a plain arm64 MIAMI XNU kernel; never includes an iOS filesystem."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

PORT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PORT / 'miami/xnu'), str(PORT / 'tools')]
import mkadt
import mkpayload
import adt
sys.path.insert(0, str(PORT / 'miami'))
from userspace.build import validate as validate_init
from userspace.mkhfs import validate_hfs

CMDLINE = 'debug=0xc serial=3 cpus=1 keepsyms=1 startup_debug=1 -enable_kprintf_spam -noprogress'


def validate_ramdisk(data):
    if len(data) >= 4 and struct.unpack_from('<I', data)[0] == 0xfeedfacf:
        return validate_init(data)
    return validate_hfs(data)


def package(kernel, output, ramdisk=None):
    data = kernel.read_bytes()
    if len(data) < 32 or len(data) > 80 * 1024 * 1024:
        raise ValueError('Unexpected kernel size')
    magic, cpu, subtype, _, count, commands, _, _ = struct.unpack_from('<8I', data)
    if magic != 0xfeedfacf or cpu != 0x100000c or (subtype & 0xffffff) not in (0, 1):
        raise ValueError('Expected a plain arm64 Mach-O, not arm64e')
    if count > 2048 or commands > len(data) - 32:
        raise ValueError('Mach-O load commands out of bounds')
    offset = 32
    executable = []
    for _ in range(count):
        if offset + 8 > 32 + commands:
            raise ValueError('Truncated Mach-O command')
        cmd, size = struct.unpack_from('<II', data, offset)
        if size < 8 or size & 7 or size > 32 + commands - offset:
            raise ValueError('Bad Mach-O command length')
        if cmd == mkpayload.LC_SEGMENT_64:
            if size < 72:
                raise ValueError('Short segment command')
            va, vsize, off, fsize = struct.unpack_from('<4Q', data, offset + 24)
            maximum, initial = struct.unpack_from('<2I', data, offset + 56)
            name = data[offset + 8:offset + 24].split(b'\0')[0]
            # Apple's ctf_insert adds read-only, file-backed __CTF metadata
            # with zero VM size. dyld documents this non-loaded segment; the
            # upstream payload builder already excludes all zero-VM segments.
            file_only_ctf = name == b'__CTF' and vsize == 0 and maximum == initial == 1
            if off > len(data) or fsize > len(data) - off or (fsize > vsize and not file_only_ctf):
                raise ValueError('Segment file range out of bounds')
            if initial & 4:
                executable.append((va, va + fsize))
        offset += size
    if offset != 32 + commands:
        raise ValueError('Mach-O command count mismatch')
    parsed = mkpayload.parse_macho(data)
    if parsed['entry'] is None or not any(lo <= parsed['entry'] < hi for lo, hi in executable):
        raise ValueError('Kernel entry is not in file-backed executable memory')
    root_info = validate_ramdisk(ramdisk.read_bytes()) if ramdisk else None
    command_line = CMDLINE + (' rd=md0' if ramdisk else '')
    output.parent.mkdir(parents=True, exist_ok=True)
    tree = output.with_suffix('.adt')
    tree.write_bytes(adt.serialize(mkadt.build()))
    blob, info = mkpayload.build(str(kernel), str(tree), command_line, str(ramdisk) if ramdisk else None)
    blob = b'MIAMIXNU' + blob[8:]
    adt_offset, adt_size = struct.unpack_from('<2Q', blob, 0x20)
    tree.write_bytes(blob[adt_offset:adt_offset + adt_size])
    output.write_bytes(blob)
    metadata = {'kernel_sha256': hashlib.sha256(data).hexdigest(),
                'payload_sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
                'machine': 'MIAMI', 'cpus': 1, 'cmdline': command_line, 'layout': info,
                'ram_root': root_info}
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'MIAMI payload: {len(blob)} bytes; ' + ('bounded RAM-only PID1 root' if ramdisk else 'no root filesystem') + '; no storage driver')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ramdisk', type=Path, help='verified small static MIAMI PID1 executable for mockfs')
    args = parser.parse_args()
    package(args.kernel, args.output, args.ramdisk)
