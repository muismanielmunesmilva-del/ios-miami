#!/usr/bin/env python3
"""Exercise the portable client against the actual server with loss and stale replies."""
import ctypes as C
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("root_server", root / "userspace/remote_root_server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
byte = C.c_ubyte
ptr = C.POINTER(byte)
SEND = C.CFUNCTYPE(C.c_int, C.c_void_p, ptr, C.c_size_t)
RECV = C.CFUNCTYPE(C.c_int, C.c_void_p, ptr, C.c_size_t, C.POINTER(C.c_size_t))


class Transport(C.Structure):
    _fields_ = [("context", C.c_void_p), ("send", SEND), ("receive", RECV)]


class Client(C.Structure):
    _fields_ = [("io", Transport), ("image_size", C.c_uint64), ("next_sequence", C.c_uint32)]


with tempfile.TemporaryDirectory() as directory:
    libfile = Path(directory) / "client.so"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                    str(root / "xnu/remote_root_protocol.c"), str(root / "xnu/remote_root_client.c"),
                    "-o", str(libfile)], check=True)
    lib = C.CDLL(str(libfile))
    lib.miami_root_query_size.argtypes = [C.POINTER(Client)]
    lib.miami_root_read.argtypes = [C.POINTER(Client), C.c_uint64, ptr, C.c_size_t]
    image = bytes(range(256)) * 16
    path = Path(directory) / "image"
    path.write_bytes(image)
    fd = os.open(path, os.O_RDONLY)
    queue = []
    sends = [0]
    drop_all = [False]

    @SEND
    def send(_context, data, length):
        packet = bytes(data[:length])
        sends[0] += 1
        if not drop_all[0] and sends[0] != 1:
            reply = server.handle(fd, len(image), packet)
            # A stale response must be ignored, then the correct reply accepted.
            queue.append(reply[:4] + b"\0\0\0\0" + reply[8:])
            queue.append(reply)
        return 0

    @RECV
    def receive(_context, target, capacity, length):
        if not queue:
            return 0
        data = queue.pop(0)
        assert len(data) <= capacity
        C.memmove(target, data, len(data))
        length[0] = len(data)
        return 1

    client = Client(Transport(None, send, receive), 0, 1)
    try:
        assert lib.miami_root_query_size(C.byref(client)) == 0
        assert client.image_size == len(image) and sends[0] == 2
        out = (byte * 2500)()
        assert lib.miami_root_read(C.byref(client), 507, out, len(out)) == 0
        assert bytes(out) == image[507:3007]
        before = sends[0]
        assert lib.miami_root_read(C.byref(client), len(image) - 1, out, 2) == -1
        assert sends[0] == before
        drop_all[0] = True
        assert lib.miami_root_read(C.byref(client), 0, out, 1) == -1
        assert sends[0] == before + 5
    finally:
        os.close(fd)
    assert path.read_bytes() == image
print("remote-root client handles chunks, loss, stale replies and bounds")
