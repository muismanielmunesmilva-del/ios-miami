#!/usr/bin/env python3
"""Experimental read-only UDP range server for the local dyld cache.

This is a transport prototype, not a filesystem or a dyld integration.
"""
import argparse
import os
from pathlib import Path
import re
import socket
import stat
import struct

REQUEST = struct.Struct("!4sIQHH")
RESPONSE = struct.Struct("!4sIBH")
MAGIC_REQUEST = b"MDR1"
MAGIC_RESPONSE = b"MDS1"
MAX_READ = 1024
MAX_NAME = 80
NAME = re.compile(r"dyld_shared_cache_arm64(?:\.[0-9]{2}(?:\.dylddata|\.dyldlinkedit)?|\.symbols)?\Z")


def reply(root, packet):
    """Return one bounded response; do not open paths outside the cache."""
    if len(packet) < REQUEST.size:
        return None
    magic, sequence, offset, length, name_len = REQUEST.unpack_from(packet)
    if magic != MAGIC_REQUEST:
        return None
    def error(code):
        return RESPONSE.pack(MAGIC_RESPONSE, sequence, code, 0)
    if length == 0 or length > MAX_READ or name_len == 0 or name_len > MAX_NAME:
        return error(1)
    if len(packet) != REQUEST.size + name_len:
        return error(1)
    try:
        name = packet[REQUEST.size:].decode("ascii")
    except UnicodeDecodeError:
        return error(1)
    if not NAME.fullmatch(name):
        return error(1)
    path = root / name
    try:
        # Refuse symlinks even on platforms without O_NOFOLLOW.
        if path.is_symlink():
            return error(2)
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                     getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return error(2)
            os.lseek(fd, offset, os.SEEK_SET)
            data = os.read(fd, length)
        finally:
            os.close(fd)
    except (OSError, OverflowError, ValueError):
        return error(2)
    return RESPONSE.pack(MAGIC_RESPONSE, sequence, 0, len(data)) + data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache_dir", type=Path)
    parser.add_argument("--bind", default="192.168.7.1")
    parser.add_argument("--port", type=int, default=5141)
    parser.add_argument("--peer", default="192.168.7.2")
    args = parser.parse_args()
    if not args.cache_dir.is_dir():
        parser.error("cache_dir must be an existing directory")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        print(f"read-only cache prototype on {args.bind}:{args.port}, peer {args.peer}", flush=True)
        while True:
            packet, peer = sock.recvfrom(2048)
            if peer[0] != args.peer:
                continue
            data = reply(args.cache_dir, packet)
            if data is not None:
                sock.sendto(data, peer)


if __name__ == "__main__":
    main()
