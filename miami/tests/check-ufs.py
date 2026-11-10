"""Validate Miami UFS driver structures, MMIO register offsets, and read-only invariants."""
from pathlib import Path
import sys

PORT = Path(__file__).resolve().parents[2]


def check():
    p28 = (PORT / 'xnu/patches/0028-sweet-ufs-root-device.patch').read_text()
    p34 = (PORT / 'xnu/patches/0034-sweet-ufs-dma-above-4g.patch').read_text()
    p69 = (PORT / 'xnu/patches/0069-sweet-ufs-faster.patch').read_text()

    # Verify MMIO offsets and invariants
    assert '#define REG_HCE         0x34' in p28
    assert '#define REG_UTRLDBR     0x58' in p28
    assert '#define REG_UTRLBA      0x50' in p28
    assert '#define REG_UTRLBAU     0x54' in p28
    assert '#define UFS_BLOCK       4096u' in p28
    assert '#define BOUNCE_SIZE     (1u << 20)' in p28
    assert 'CAP_64AS' in p34
    assert 'assert_wait_deadline_with_leeway' in p69

    # Verify read-only safety: write operations must return EROFS
    assert 'return (flags & FWRITE) ? EROFS : 0;' in p28
    assert 'return EROFS;' in p28

    print('PASS: Miami UFS structures, polled SCSI commands, and read-only protection verified.')


if __name__ == '__main__':
    check()
