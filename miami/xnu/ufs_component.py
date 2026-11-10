"""Stage XNU Qualcomm UFSHCI 2.1 SCSI driver for MIAMI (read-only root device)."""
import hashlib
from pathlib import Path
import subprocess

PORT = Path(__file__).resolve().parents[2]


def stage(tree):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Apply bsd/conf/files and IOKitBSDInit.cpp configuration patch
    conf_patch = (Path(__file__).resolve().parent / '0028-miami-ufs-conf.patch').read_bytes()
    for flags in (['--check'], []):
        subprocess.run(['git', '-C', str(tree), 'apply', *flags,
                        '--whitespace=nowarn', '-'], input=conf_patch, check=True)
    (patch_dir / '0028-miami-ufs-root-device.patch').write_bytes(conf_patch)

    # 2. Stage clean read-only driver source at bsd/dev/miami_ufs.c
    source_c = (Path(__file__).resolve().parent / 'miami_ufs.c').read_text()
    dest_c = tree / 'bsd/dev/miami_ufs.c'
    dest_c.write_text(source_c)

    return {
        'driver': 'Qualcomm UFSHCI 2.1 SCSI read-only driver (bsd/dev/miami_ufs.c)',
        'mmio_base': '0x04804000',
        'mmio_size': '0x20000',
        'node': '/miami-ufs',
        'root_device': 'ufsroot0',
        'source_sha256': hashlib.sha256(dest_c.read_bytes()).hexdigest(),
        'patch_sha256': hashlib.sha256(conf_patch).hexdigest()
    }
