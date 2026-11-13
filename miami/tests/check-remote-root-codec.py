#!/usr/bin/env python3
"""Cross-check the C client codec against the Python read-only server."""
import ctypes
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("root_server", root / "userspace" / "remote_root_server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

with tempfile.TemporaryDirectory() as directory:
    library = Path(directory) / "codec.so"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC",
                    "-shared", str(root / "xnu" / "remote_root_protocol.c"),
                    "-o", str(library)], check=True)
    codec = ctypes.CDLL(str(library))
    byte = ctypes.c_ubyte
    ptr = ctypes.POINTER(byte)
    codec.miami_root_encode_request.argtypes = [ptr, ctypes.c_size_t, ctypes.c_uint32,
                                                ctypes.c_uint64, ctypes.c_uint16]
    codec.miami_root_decode_response.argtypes = [ptr, ctypes.c_size_t, ctypes.c_uint32,
                                                 ctypes.c_uint64, ctypes.c_uint16,
                                                 ctypes.POINTER(ptr)]
    image = bytes(range(256)) * 8
    path = Path(directory) / "root.img"
    path.write_bytes(image)
    fd = os.open(path, os.O_RDONLY)
    try:
        for sequence, offset, length in ((1, 0, 0), (0x12345678, 509, 1024)):
            request = (byte * server.REQUEST.size)()
            assert codec.miami_root_encode_request(request, len(request), sequence, offset, length) == 0
            assert bytes(request) == server.REQUEST.pack(server.REQUEST_MAGIC, sequence, offset, length)
            reply = server.handle(fd, len(image), bytes(request))
            packet = (byte * len(reply)).from_buffer_copy(reply)
            payload = ptr()
            expected = 8 if length == 0 else length
            decode = codec.miami_root_decode_response
            assert decode(packet, len(packet), sequence, offset, expected, ctypes.byref(payload)) == 0
            data = bytes(payload[:expected])
            assert data == (struct.pack("!Q", len(image)) if length == 0 else image[offset:offset + length])
            for forged in (reply[:4] + b"\0\0\0\0" + reply[8:],
                           reply[:8] + b"\1" + reply[9:],
                           reply[:-1], reply + b"x"):
                altered = (byte * len(forged)).from_buffer_copy(forged)
                assert decode(altered, len(altered), sequence, offset, expected, ctypes.byref(payload)) == -1
                assert not payload
        small = (byte * server.REQUEST.size)()
        assert codec.miami_root_encode_request(small, len(small), 1, 1, 0) == -1
        assert codec.miami_root_encode_request(small, len(small), 1, 0, 1025) == -1
        assert codec.miami_root_encode_request(small, len(small) - 1, 1, 0, 1) == -1
    finally:
        os.close(fd)

    # Stage the real USB component twice into an isolated miniature tree.
    stage_spec = importlib.util.spec_from_file_location("usb_component", root / "xnu" / "usb_component.py")
    stage = importlib.util.module_from_spec(stage_spec)
    stage_spec.loader.exec_module(stage)
    tree = Path(directory) / "xnu"
    for child in ("bsd/conf", "bsd/dev", "bsd/kern"):
        (tree / child).mkdir(parents=True)
    files = tree / "bsd/conf/files"
    files.write_text("bsd/dev/miami_keys.c\t\t\tstandard\n")
    bsd_init = tree / "bsd/kern/bsd_init.c"
    bsd_init.write_text("\tmiami_keys_init();\n")
    stage.stage(tree)
    stage.stage(tree)
    assert files.read_text().count("bsd/dev/remote_root_protocol.c") == 1
    assert (tree / "bsd/dev/remote_root_protocol.c").read_bytes() == (root / "xnu/remote_root_protocol.c").read_bytes()
    assert (tree / "bsd/dev/remote_root_protocol.h").read_bytes() == (root / "xnu/remote_root_protocol.h").read_bytes()
print("remote-root C codec and server interoperability checks passed")
