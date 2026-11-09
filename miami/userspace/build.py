#!/usr/bin/env python3
"""Assemble and independently verify a small static signed PID1 test image."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

PORT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PORT / 'tools'))
import mkinit

MAX_IMAGE = 65536
ENTITLEMENTS_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
    b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    b'<plist version="1.0">\n'
    b'<dict>\n'
    b'\t<key>com.motorola.miami.pid1</key>\n'
    b'\t<true/>\n'
    b'\t<key>com.apple.private.miami.test-bool</key>\n'
    b'\t<true/>\n'
    b'\t<key>com.apple.private.miami.test-string</key>\n'
    b'\t<string>hello</string>\n'
    b'</dict>\n'
    b'</plist>\n'
)


def validate(data):
    if len(data) < 16384 or len(data) > MAX_IMAGE:
        raise ValueError('PID1 image size out of bounds')
    magic, cpu, subtype, kind, count, cmdbytes, flags, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, subtype, kind, count) != (0xfeedfacf, 0x100000c, 0, 2, 5):
        raise ValueError('Expected static plain arm64 PID1 executable')
    if cmdbytes > 1024 - 32 or flags != 1:
        raise ValueError('Unexpected PID1 Mach-O header')
    offset, entry, sig, text = 32, None, None, None
    segments = []
    for _ in range(count):
        cmd, size = struct.unpack_from('<II', data, offset)
        if size < 8 or size % 8 or offset + size > 32 + cmdbytes:
            raise ValueError('Malformed PID1 load command')
        if cmd == 0x19:
            name = data[offset + 8:offset + 24].split(b'\0')[0].decode()
            va, vs, fo, fs, maximum, initial, nsects, _ = struct.unpack_from('<4Q4I', data, offset + 24)
            segments.append((name, va, vs, fo, fs, maximum, initial))
            if name == '__TEXT':
                if nsects != 1 or size != 152:
                    raise ValueError('Unexpected PID1 text section')
                section = offset + 72
                _, _, code_va, code_size, code_off = struct.unpack_from('<16s16sQQI', data, section)
                text = code_va, code_size, code_off
        elif cmd == 5:
            if size != 288 or struct.unpack_from('<II', data, offset + 8) != (6, 68):
                raise ValueError('Invalid initial thread state')
            entry = struct.unpack_from('<Q', data, offset + 16 + 32 * 8)[0]
        elif cmd == 0x1d:
            sig = struct.unpack_from('<II', data, offset + 8)
        else:
            raise ValueError('PID1 imports or unsupported load command')
        offset += size
    if offset != 32 + cmdbytes or segments[:2] != [
            ('__PAGEZERO', 0, 0x100000000, 0, 0, 0, 0),
            ('__TEXT', 0x100000000, 0x4000, 0, 0x4000, 5, 5)]:
        raise ValueError('PID1 segment layout changed')
    if not text or not (text[0] <= entry < text[0] + text[1]) or text[2] != 1024:
        raise ValueError('PID1 entry outside executable code')
    if not sig or sig[0] != 16384 or sig[0] + sig[1] != len(data):
        raise ValueError('PID1 signature location invalid')
    if len(segments) != 3 or segments[2] != ('__LINKEDIT', 0x100004000, 0x4000, 0x4000, sig[1], 1, 1):
        raise ValueError('PID1 linkedit layout invalid')
    if text[0] != 0x100000400 or not text[1] or text[1] > 16384 - 1024 or entry % 4:
        raise ValueError('PID1 code bounds invalid')
    # mov x9,sp; and x9,x9,#~15; mov sp,x9 -- hardware checks SP alignment
    # more strictly than the QEMU control used for this bring-up.
    if entry != text[0] or data[1024:1036] != bytes.fromhex('e903009129ed7c923f010091'):
        raise ValueError('PID1 entry does not align SP before stack access')
    sb = data[sig[0]:]
    sb_magic, sb_len, sb_count = struct.unpack_from('>3I', sb)
    if sb_magic != 0xfade0cc0 or sb_len != len(sb) or sb_count not in (1, 2):
        raise ValueError('PID1 signature superblob malformed')
    cd_type, cd_off = struct.unpack_from('>II', sb, 12)
    expected_cd_off = 12 + 8 * sb_count
    if cd_type != 0 or cd_off != expected_cd_off:
        raise ValueError('PID1 CodeDirectory index invalid')
    ent_blob = None
    if sb_count == 2:
        ent_type, ent_off = struct.unpack_from('>II', sb, 20)
        if ent_type != 5 or ent_off <= cd_off or ent_off >= len(sb):
            raise ValueError('PID1 entitlements index invalid')
        cd = sb[cd_off:ent_off]
        ent_blob = sb[ent_off:]
        ent_magic, ent_len = struct.unpack_from('>II', ent_blob)
        if ent_magic != 0xfade7171 or ent_len != len(ent_blob) or ent_blob[8:] != ENTITLEMENTS_XML:
            raise ValueError('PID1 XML entitlements blob invalid')
    else:
        cd = sb[cd_off:]
    fields = struct.unpack_from('>9I4B', cd)
    magic, length, version, csflags, hash_off, ident_off, specials, slots, limit, hash_size, hash_type, _, page_shift = fields
    expected_specials = 5 if ent_blob is not None else 0
    if (magic, length, version, csflags, specials, slots, limit, hash_size, hash_type, page_shift) != (
            0xfade0c02, len(cd), 0x20400, 2, expected_specials, 4, 16384, 32, 2, 12):
        raise ValueError('Unsupported PID1 CodeDirectory')
    if cd[ident_off:hash_off - specials * hash_size] != b'org.miami.init\0' or hash_off + slots * hash_size != len(cd):
        raise ValueError('PID1 identity/hash bounds invalid')
    if ent_blob is not None:
        special_region = cd[hash_off - specials * hash_size:hash_off]
        expected_special = hashlib.sha256(ent_blob).digest() + bytes(32 * 4)
        if special_region != expected_special:
            raise ValueError('PID1 entitlements special-slot hash mismatch')
    for page in range(slots):
        if hashlib.sha256(data[page * 4096:(page + 1) * 4096]).digest() != cd[hash_off + page * 32:hash_off + (page + 1) * 32]:
            raise ValueError('PID1 signed page hash mismatch')
    if b'MIAMI USERSPACE: PID=1 (getpid verified)' not in data[:limit]:
        raise ValueError('Wrong PID1 test executable')
    if b'MIAMI AMFI: platform binary and XML entitlements verified' not in data[:limit]:
        raise ValueError('Missing AMFI entitlements probe')
    if b'MIAMI PSYNCH: cvwait timed out as expected' not in data[:limit]:
        raise ValueError('Missing pthread wait probe')
    if b'MIAMI THREADS: waiting thread signaled successfully' not in data[:limit]:
        raise ValueError('Missing cross-thread signal probe')
    return {'type': 'mockfs-macho', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'entry': hex(entry), 'identity': 'org.miami.init',
            'entitlements_xml': ent_blob is not None, 'signature_pages_verified': slots}


def build(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='miami-init-') as folder:
        obj = Path(folder) / 'init.o'
        subprocess.run(['clang', '-target', 'arm64-apple-ios16.0', '-c', str(Path(__file__).with_name('init.S')), '-o', str(obj)], check=True)
        mkinit.IDENT = b'org.miami.init\0'
        image = mkinit.build(obj.read_bytes(), ENTITLEMENTS_XML)
        result = validate(image)
        output.write_bytes(image)
    return result


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
