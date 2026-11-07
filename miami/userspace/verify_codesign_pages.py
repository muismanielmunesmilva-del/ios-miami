"""Verify Mach-O CodeDirectory page hashes; this does not verify Apple trust."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect(data):
    if len(data) < 32:
        raise ValueError('Short Mach-O')
    magic, cpu, subtype, _, count, commands, _, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, subtype) != (0xfeedfacf, 0x100000c, 0) or count > 2048 or commands > len(data) - 32:
        raise ValueError('Expected bounded plain-arm64 Mach-O')
    off, signature = 32, None
    for _ in range(count):
        if off + 8 > 32 + commands:
            raise ValueError('Truncated load command')
        cmd, size = struct.unpack_from('<II', data, off)
        if size < 8 or off + size > 32 + commands:
            raise ValueError('Invalid load command')
        if cmd == 0x1d:
            if signature is not None or size < 16:
                raise ValueError('Invalid signature command')
            signature = struct.unpack_from('<II', data, off + 8)
        off += size
    if off != 32 + commands or signature is None:
        raise ValueError('Missing or malformed signature command')
    start, length = signature
    if length < 12 or start > len(data) or length > len(data) - start:
        raise ValueError('Signature outside file')
    magic, total, entries = struct.unpack_from('>III', data, start)
    if magic != 0xfade0cc0 or total > length or total < 12 or entries > 100 or 12 + entries * 8 > total:
        raise ValueError('Invalid signature superblob')
    directories = []
    for index in range(entries):
        slot, rel = struct.unpack_from('>II', data, start + 12 + index * 8)
        if rel > total - 8:
            raise ValueError('Blob outside signature')
        kind, size = struct.unpack_from('>II', data, start + rel)
        if size < 8 or size > total - rel:
            raise ValueError('Invalid signature blob size')
        if kind != 0xfade0c02:
            continue
        if size < 40:
            raise ValueError('Short CodeDirectory')
        cd = memoryview(data)[start + rel:start + rel + size]
        _, _, hashoff, _, special, slots, limit = struct.unpack_from('>7I', cd, 8)
        hashsize, hashtype, _, shift = struct.unpack_from('>4B', cd, 36)
        algorithm = {1:'sha1', 2:'sha256', 3:'sha256', 4:'sha384'}.get(hashtype)
        if (algorithm is None or not hashsize or shift > 30 or limit > start or
                slots != (limit + (1 << shift) - 1) // (1 << shift) or
                hashoff < special * hashsize or hashoff + slots * hashsize > size or
                hashsize > hashlib.new(algorithm).digest_size):
            raise ValueError('Unsupported or malformed CodeDirectory')
        for page in range(slots):
            chunk = data[page * (1 << shift):min(limit, (page + 1) * (1 << shift))]
            actual = hashlib.new(algorithm, chunk).digest()[:hashsize]
            if actual != cd[hashoff + page * hashsize:hashoff + (page + 1) * hashsize]:
                raise ValueError('CodeDirectory page hash mismatch')
        directories.append({'slot':slot, 'hash_type':hashtype, 'page_bytes':1 << shift,
                            'pages_verified':slots, 'code_limit':limit})
    if not directories:
        raise ValueError('No supported CodeDirectory')
    return {'sha256':hashlib.sha256(data).hexdigest(), 'code_directories':directories,
            'page_hashes':'PASS', 'cms_or_trust_chain_verified':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps({str(p):inspect(p.read_bytes()) for p in args.files}, indent=2))
