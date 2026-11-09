#!/usr/bin/env python3
"""Build and independently verify a deterministic HFS+ RAMDisk root image."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as build_init

BLOCK_SIZE = 4096
TOTAL_BLOCKS = 32
IMAGE_BYTES = BLOCK_SIZE * TOTAL_BLOCKS  # 131072 bytes (8 x 16-KiB pages)
SIG_HFSPLUS = 0x482B
SIG_HFSX = 0x4858
ATTR_UNMOUNTED = 0x00000100
ATTR_UNUSED_NODE_FIX = 0x80000000
ROOT_MARKER_BYTES = b'MIAMI HFS+ ROOT OK\n'


def u16_name(text):
    encoded = text.encode('utf-16-be')
    return struct.pack('>H', len(text)) + encoded


def catalog_key(parent_id, name):
    uname = u16_name(name)
    key_len = 4 + len(uname)
    raw = struct.pack('>HI', key_len, parent_id) + uname
    if len(raw) & 1:
        raw += b'\0'
    return raw


def folder_record(folder_id, valence, mode=0o040755):
    bsd = struct.pack('>IIBBHI', 0, 0, 0, 0, mode, 0)
    return struct.pack('>hhIIIIIII', 1, 2, valence, folder_id, 0, 0, 0, 0, 0) + bsd + bytes(32) + struct.pack('>II', 0, 0)


def fork_data(logical_size, start_block, block_count, clump_size=BLOCK_SIZE):
    extents = struct.pack('>II', start_block, block_count) + bytes(56)
    return struct.pack('>QII', logical_size, clump_size, block_count) + extents


def file_record(file_id, data_bytes, start_block, mode=0o100755):
    blocks = (len(data_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE if data_bytes else 0
    bsd = struct.pack('>IIBBHI', 0, 0, 0, 0, mode, 1)
    header = struct.pack('>hhIIIIIII', 2, 2, 0, file_id, 0, 0, 0, 0, 0) + bsd + bytes(32) + struct.pack('>II', 0, 0)
    data_fork = fork_data(len(data_bytes), start_block if blocks else 0, blocks)
    rsrc_fork = fork_data(0, 0, 0)
    return header + data_fork + rsrc_fork


def thread_record(record_type, parent_id, name):
    raw = struct.pack('>hhI', record_type, 0, parent_id) + u16_name(name)
    if len(raw) & 1:
        raw += b'\0'
    return raw


def btree_node(kind, height, records):
    node = bytearray(BLOCK_SIZE)
    struct.pack_into('>IIbBHH', node, 0, 0, 0, kind, height, len(records), 0)
    offset = 14
    offsets = []
    for rec in records:
        if len(rec) & 1:
            rec = rec + b'\0'
        offsets.append(offset)
        node[offset:offset + len(rec)] = rec
        offset += len(rec)
    offsets.append(offset)
    trailer = BLOCK_SIZE - 2 * len(offsets)
    if offset > trailer:
        raise ValueError('B-tree node records overflow 4096-byte node')
    for i, off in enumerate(offsets):
        struct.pack_into('>H', node, BLOCK_SIZE - 2 * (i + 1), off)
    return bytes(node)


def btree_header_node(tree_depth, root_node, leaf_records, first_leaf, last_leaf,
                      max_key_len, total_nodes, free_nodes, clump_size,
                      key_compare_type, attributes, alloc_bitmap_byte0):
    hdr = struct.pack('>HIIIIHHIIHIBBI',
                      tree_depth, root_node, leaf_records, first_leaf, last_leaf,
                      BLOCK_SIZE, max_key_len, total_nodes, free_nodes, 0,
                      clump_size, 0, key_compare_type, attributes) + bytes(64)
    user_data = bytes(128)
    map_rec = bytearray(3840)
    map_rec[0] = alloc_bitmap_byte0
    return btree_node(1, 0, [hdr, user_data, bytes(map_rec)])


def build_image(launchd_bytes, marker_bytes=ROOT_MARKER_BYTES):
    init_info = build_init.validate(launchd_bytes)
    launchd_blocks = (len(launchd_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE
    marker_blocks = (len(marker_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE
    launchd_start = 5
    marker_start = launchd_start + launchd_blocks
    used_low_blocks = marker_start + marker_blocks
    if used_low_blocks >= TOTAL_BLOCKS - 1:
        raise ValueError('HFS+ root image contents exceed 32-block allocation')
    free_blocks = (TOTAL_BLOCKS - 1) - used_low_blocks

    # Extents Overflow B-Tree (block 2): 1 header node, empty tree.
    extents_node0 = btree_header_node(
        tree_depth=0, root_node=0, leaf_records=0, first_leaf=0, last_leaf=0,
        max_key_len=10, total_nodes=1, free_nodes=0, clump_size=BLOCK_SIZE,
        key_compare_type=0, attributes=0x00000002, alloc_bitmap_byte0=0x80)

    # Catalog B-Tree (blocks 3..4): header node 0 + leaf node 1.
    # Sorted by (parentID ascending, case-folded UTF-16 name ascending):
    #   (1, "MiamiRoot") -> folderID 2 (valence 3: dev, etc, sbin)
    #   (2, "")          -> folder thread (1, "MiamiRoot")
    #   (2, "dev")       -> folderID 16 (valence 0)
    #   (2, "etc")       -> folderID 17 (valence 1: miami-root)
    #   (2, "sbin")      -> folderID 18 (valence 1: launchd)
    #   (16, "")         -> folder thread (2, "dev")
    #   (17, "")         -> folder thread (2, "etc")
    #   (17, "miami-root")-> fileID 20 (/etc/miami-root)
    #   (18, "")         -> folder thread (2, "sbin")
    #   (18, "launchd")  -> fileID 19 (/sbin/launchd)
    #   (19, "")         -> file thread (18, "launchd")
    #   (20, "")         -> file thread (17, "miami-root")
    leaf_items = [
        (1, 'MiamiRoot', folder_record(2, 3, 0o040755)),
        (2, '', thread_record(3, 1, 'MiamiRoot')),
        (2, 'dev', folder_record(16, 0, 0o040755)),
        (2, 'etc', folder_record(17, 1, 0o040755)),
        (2, 'sbin', folder_record(18, 1, 0o040755)),
        (16, '', thread_record(3, 2, 'dev')),
        (17, '', thread_record(3, 2, 'etc')),
        (17, 'miami-root', file_record(20, marker_bytes, marker_start, 0o100644)),
        (18, '', thread_record(3, 2, 'sbin')),
        (18, 'launchd', file_record(19, launchd_bytes, launchd_start, 0o100755)),
        (19, '', thread_record(4, 18, 'launchd')),
        (20, '', thread_record(4, 17, 'miami-root')),
    ]
    sort_keys = [(pid, name.lower()) for pid, name, _ in leaf_items]
    if sort_keys != sorted(sort_keys):
        raise ValueError('Catalog leaf records are not strictly sorted')
    catalog_records = [catalog_key(pid, name) + rec for pid, name, rec in leaf_items]
    catalog_node0 = btree_header_node(
        tree_depth=1, root_node=1, leaf_records=len(catalog_records),
        first_leaf=1, last_leaf=1, max_key_len=516, total_nodes=2, free_nodes=0,
        clump_size=2 * BLOCK_SIZE, key_compare_type=0xCF, attributes=0x00000006,
        alloc_bitmap_byte0=0xC0)
    catalog_node1 = btree_node(-1, 1, catalog_records)

    # Allocation Bitmap (block 1): mark blocks 0..used_low_blocks-1 and TOTAL_BLOCKS-1.
    bitmap = bytearray(BLOCK_SIZE)
    for b in list(range(used_low_blocks)) + [TOTAL_BLOCKS - 1]:
        bitmap[b // 8] |= 1 << (7 - (b % 8))

    # Volume Header (512 bytes at offset 1024 and alternate at IMAGE_BYTES - 1024).
    vh = bytearray(512)
    struct.pack_into('>HH17IQ', vh, 0,
                     SIG_HFSPLUS, 4, ATTR_UNMOUNTED | ATTR_UNUSED_NODE_FIX,
                     0x4846532B, 0, 0, 0, 0, 0,
                     2, 3, BLOCK_SIZE, TOTAL_BLOCKS, free_blocks,
                     used_low_blocks, BLOCK_SIZE, BLOCK_SIZE, 21,
                     1, 1)
    vh[112:192] = fork_data(BLOCK_SIZE, 1, 1, BLOCK_SIZE)          # allocationFile
    vh[192:272] = fork_data(BLOCK_SIZE, 2, 1, BLOCK_SIZE)          # extentsFile
    vh[272:352] = fork_data(2 * BLOCK_SIZE, 3, 2, 2 * BLOCK_SIZE)  # catalogFile
    vh[352:432] = fork_data(0, 0, 0, 0)                            # attributesFile
    vh[432:512] = fork_data(0, 0, 0, 0)                            # startupFile

    image = bytearray(IMAGE_BYTES)
    image[1024:1536] = vh
    image[BLOCK_SIZE:2 * BLOCK_SIZE] = bitmap
    image[2 * BLOCK_SIZE:3 * BLOCK_SIZE] = extents_node0
    image[3 * BLOCK_SIZE:4 * BLOCK_SIZE] = catalog_node0
    image[4 * BLOCK_SIZE:5 * BLOCK_SIZE] = catalog_node1
    image[launchd_start * BLOCK_SIZE:launchd_start * BLOCK_SIZE + len(launchd_bytes)] = launchd_bytes
    image[marker_start * BLOCK_SIZE:marker_start * BLOCK_SIZE + len(marker_bytes)] = marker_bytes
    image[IMAGE_BYTES - 1024:IMAGE_BYTES - 512] = vh
    validate_hfs(image)
    return bytes(image), init_info


def validate_hfs(data):
    if len(data) < 8 * BLOCK_SIZE or len(data) > 64 * 1024 * 1024 or len(data) % 0x4000:
        raise ValueError('HFS+ root image size out of bounds or not 16K-aligned')
    sig, version, attrs, _, jnl, _, _, _, _, file_cnt, dir_cnt, blk_size, total_blks, free_blks = (
        struct.unpack_from('>HHIIIIIIIIIIII', data, 1024))
    if (sig, version) not in ((SIG_HFSPLUS, 4), (SIG_HFSX, 5)):
        raise ValueError('Invalid HFS+/HFSX volume signature or version')
    if blk_size != BLOCK_SIZE or total_blks * blk_size != len(data):
        raise ValueError('HFS+ volume block geometry mismatch')
    if jnl != 0 or not (attrs & ATTR_UNMOUNTED) or free_blks >= total_blks:
        raise ValueError('HFS+ volume header attributes or block counts invalid')
    if data[1024:1536] != data[len(data) - 1024:len(data) - 512]:
        raise ValueError('HFS+ alternate volume header mismatch')
    alloc_size, _, alloc_blks, alloc_start, alloc_cnt = struct.unpack_from('>QIIII', data, 1024 + 112)
    ext_size, _, ext_blks, ext_start, ext_cnt = struct.unpack_from('>QIIII', data, 1024 + 192)
    cat_size, _, cat_blks, cat_start, cat_cnt = struct.unpack_from('>QIIII', data, 1024 + 272)
    if (alloc_size, alloc_blks, alloc_start, alloc_cnt) != (BLOCK_SIZE, 1, 1, 1):
        raise ValueError('HFS+ allocation bitmap fork invalid')
    if (ext_size, ext_blks, ext_start, ext_cnt) != (BLOCK_SIZE, 1, 2, 1):
        raise ValueError('HFS+ extents overflow fork invalid')
    if (cat_size, cat_blks, cat_start, cat_cnt) != (2 * BLOCK_SIZE, 2, 3, 2):
        raise ValueError('HFS+ catalog fork invalid')
    # Verify Catalog leaf node contains /sbin/launchd and /etc/miami-root and
    # validate the embedded /sbin/launchd Mach-O signature and page hashes.
    leaf = data[4 * BLOCK_SIZE:5 * BLOCK_SIZE]
    _, _, kind, height, nrecs, _ = struct.unpack_from('>IIbBHH', leaf, 0)
    if (kind, height) != (-1, 1) or nrecs < 6:
        raise ValueError('HFS+ catalog leaf node header invalid')
    launchd_found = None
    marker_found = None
    for i in range(nrecs):
        rec_off = struct.unpack_from('>H', leaf, BLOCK_SIZE - 2 * (i + 1))[0]
        next_off = struct.unpack_from('>H', leaf, BLOCK_SIZE - 2 * (i + 2))[0]
        if rec_off < 14 or next_off <= rec_off or next_off > BLOCK_SIZE - 2 * (nrecs + 1):
            raise ValueError('HFS+ catalog leaf record offset out of bounds')
        key_len, parent_id, name_chars = struct.unpack_from('>HIH', leaf, rec_off)
        name = leaf[rec_off + 8:rec_off + 8 + 2 * name_chars].decode('utf-16-be')
        val_off = rec_off + 2 + key_len
        if val_off & 1:
            val_off += 1
        rec_type, = struct.unpack_from('>h', leaf, val_off)
        if rec_type == 2:
            logical_size, _, total_fblks, fstart, fcnt = struct.unpack_from('>QIIII', leaf, val_off + 88)
            if fcnt != total_fblks or (fstart + fcnt) * BLOCK_SIZE > len(data) - BLOCK_SIZE:
                raise ValueError('HFS+ catalog file extent out of bounds')
            file_bytes = data[fstart * BLOCK_SIZE:fstart * BLOCK_SIZE + logical_size]
            if (parent_id, name) == (18, 'launchd'):
                launchd_found = build_init.validate(file_bytes)
            elif (parent_id, name) == (17, 'miami-root'):
                marker_found = file_bytes
    if not launchd_found or marker_found != ROOT_MARKER_BYTES:
        raise ValueError('HFS+ image missing verified /sbin/launchd or /etc/miami-root')
    return {'type': 'hfsplus', 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data), 'block_size': BLOCK_SIZE, 'total_blocks': total_blks,
            'files': int(file_cnt), 'folders': int(dir_cnt), 'launchd': launchd_found}


def build(output, launchd_path=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    if launchd_path is not None:
        launchd_bytes = launchd_path.read_bytes()
    else:
        init_out = output.with_name('miami-init.macho')
        build_init.build(init_out)
        launchd_bytes = init_out.read_bytes()
    image, _ = build_image(launchd_bytes)
    result = validate_hfs(image)
    output.write_bytes(image)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--launchd', type=Path, help='existing verified miami-init.macho binary')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.launchd), indent=2))
