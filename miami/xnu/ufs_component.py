"""Stage XNU Qualcomm UFSHCI 2.1 SCSI driver for MIAMI (read-only root device)."""
import hashlib
from pathlib import Path
import subprocess

UFS_PATCHES = (
    '0028-sweet-ufs-root-device.patch',
    '0034-sweet-ufs-dma-above-4g.patch',
    '0069-sweet-ufs-faster.patch',
)


def apply_ufs_patches(tree):
    port = Path(__file__).resolve().parents[2]
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)
    records = []
    for name in UFS_PATCHES:
        original = (port / 'xnu/patches' / name).read_bytes().replace(b'\r\n', b'\n')
        patch = original.replace(b'SWEET', b'MIAMI').replace(b'sweet', b'miami')
        for flags in (['--check'], []):
            subprocess.run(['git', '-C', str(tree), 'apply', *flags,
                            '--whitespace=nowarn', '-'], input=patch, check=True)
        (patch_dir / name.replace('sweet', 'miami')).write_bytes(patch)
        records.append({
            'name': name,
            'input_sha256': hashlib.sha256(original).hexdigest(),
            'target_sha256': hashlib.sha256(patch).hexdigest()
        })
    return records


def stage(tree):
    records = apply_ufs_patches(tree)
    ufs_c = tree / 'bsd/dev/miami_ufs.c'
    if not ufs_c.exists():
        raise FileNotFoundError(f'Expected {ufs_c} to exist after applying UFS patches')
    return {
        'driver': 'Qualcomm UFSHCI 2.1 SCSI read-only driver (bsd/dev/miami_ufs.c)',
        'mmio_base': '0x04804000',
        'mmio_size': '0x20000',
        'node': '/miami-ufs',
        'root_device': 'ufsroot0',
        'source_sha256': hashlib.sha256(ufs_c.read_bytes()).hexdigest(),
        'patches': records
    }
