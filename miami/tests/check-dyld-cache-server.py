#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile

module_path = Path(__file__).resolve().parents[1] / "userspace" / "dyld_cache_server.py"
spec = importlib.util.spec_from_file_location("dyld_cache_server", module_path)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

def request(name, offset=0, length=16, seq=7):
    name = name.encode()
    return server.REQUEST.pack(server.MAGIC_REQUEST, seq, offset, length, len(name)) + name

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "dyld_shared_cache_arm64").write_bytes(b"dyld_v1   arm64\0payload")
    response = server.reply(root, request("dyld_shared_cache_arm64"))
    assert server.RESPONSE.unpack_from(response) == (server.MAGIC_RESPONSE, 7, 0, 16)
    assert response[server.RESPONSE.size:] == b"dyld_v1   arm64\0"
    assert server.reply(root, request("dyld_shared_cache_arm64", 999))[server.RESPONSE.size:] == b""
    for name in ("../secret", "dyld_shared_cache_arm64/secret", "dyld_shared_cache_arm64.bad"):
        assert server.RESPONSE.unpack(server.reply(root, request(name)))[2] == 1
    assert server.RESPONSE.unpack(server.reply(root, request("dyld_shared_cache_arm64", length=1025)))[2] == 1
    assert server.reply(root, b"bad") is None
    assert server.RESPONSE.unpack(server.reply(root, request("dyld_shared_cache_arm64.01")))[2] == 2
print("dyld cache read-only range protocol checks passed")
