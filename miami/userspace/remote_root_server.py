#!/usr/bin/env python3
"""Serve bounded, read-only ranges of one local root image over UDP.

Transport prototype only: this is not yet an XNU block device or a root mount.
The caller must explicitly supply the image. No data is written to it.
"""
import argparse
import os
from pathlib import Path
import socket
import stat
import struct

REQUEST = struct.Struct("!4sIQH")
RESPONSE = struct.Struct("!4sIBQH")
REQUEST_MAGIC = b"MBR1"
RESPONSE_MAGIC = b"MBS1"
MAX_READ = 1024


def handle(fd, image_size, packet):
    if len(packet) != REQUEST.size:
        return None
    magic, sequence, offset, length = REQUEST.unpack(packet)
    if magic != REQUEST_MAGIC:
        return None

    def result(status, data=b""):
        return RESPONSE.pack(RESPONSE_MAGIC, sequence, status, offset, len(data)) + data

    # A zero-length request at offset zero discovers the exact image size.
    if not length:
        return result(0, struct.pack("!Q", image_size)) if offset == 0 else result(1)
    if length > MAX_READ:
        return result(1)
    if offset > image_size or length > image_size - offset:
        return result(2)
    try:
        data = os.pread(fd, length, offset)
    except OSError:
        return result(3)
    return result(0, data) if len(data) == length else result(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--bind", default="192.168.7.1")
    parser.add_argument("--port", type=int, default=5142)
    parser.add_argument("--peer", default="192.168.7.2")
    args = parser.parse_args()
    if args.image.is_symlink():
        parser.error("the image must not be a symlink")
    fd = os.open(args.image, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size == 0:
            parser.error("the image must be a nonempty regular file")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((args.bind, args.port))
            print(f"read-only root server {args.bind}:{args.port}, "
                  f"peer={args.peer}, bytes={st.st_size}", flush=True)
            while True:
                packet, peer = sock.recvfrom(2048)
                if peer[0] != args.peer:
                    continue
                data = handle(fd, st.st_size, packet)
                if data is not None:
                    sock.sendto(data, peer)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
