#!/usr/bin/env python3
"""Check ranges and refusal cases without proprietary data or a phone."""
import importlib.util
import os
from pathlib import Path
import struct
import tempfile

script = Path(__file__).resolve().parents[1] / "userspace" / "remote_root_server.py"
spec = importlib.util.spec_from_file_location("remote_root", script)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "root.img"
    original = bytes(range(256)) * 8
    path.write_bytes(original)
    fd = os.open(path, os.O_RDONLY)
    try:
        def query(offset, length):
            packet = server.REQUEST.pack(server.REQUEST_MAGIC, 9, offset, length)
            response = server.handle(fd, len(original), packet)
            return server.RESPONSE.unpack_from(response), response[server.RESPONSE.size:]

        header, data = query(0, 0)
        assert header == (server.RESPONSE_MAGIC, 9, 0, 0, 8)
        assert struct.unpack("!Q", data) == (len(original),)
        header, data = query(509, 1024)
        assert header == (server.RESPONSE_MAGIC, 9, 0, 509, 1024)
        assert data == original[509:1533]
        assert query(1, 0)[0][2] == 1
        assert query(0, 1025)[0][2] == 1
        assert query(len(original) - 1, 2)[0][2] == 2
        assert query((1 << 64) - 1, 1)[0][2] == 2
        assert server.handle(fd, len(original), b"bad") is None
        assert server.handle(fd, len(original), b"nope" + bytes(14)) is None
    finally:
        os.close(fd)
    assert path.read_bytes() == original
print("read-only remote-root range protocol checks passed")
