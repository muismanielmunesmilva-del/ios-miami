"""Check the real static probe and reject signed-code and metadata corruption."""
import importlib.util
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'userspace'))
import build
import verify_codesign_pages as verifier

with tempfile.TemporaryDirectory(prefix='miami-codesign-') as folder:
    p = Path(folder) / 'init.macho'
    build.build(p)
    data = p.read_bytes()
    result = verifier.inspect(data)
    assert result['page_hashes'] == 'PASS' and not result['cms_or_trust_chain_verified']
    for offset in (1024, len(data) - 1, 0):
        broken = bytearray(data)
        broken[offset] ^= 1
        try:
            verifier.inspect(broken)
        except (ValueError, AssertionError):
            pass
        else:
            raise AssertionError(f'Corruption accepted at {offset}')
print('PASS: CodeDirectory pages checked; code, hash and header corruption rejected')
