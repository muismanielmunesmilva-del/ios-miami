"""Stage XNU minimal polled hardware keys driver (Read-Only SPMI observer) for MIAMI."""
import hashlib
from pathlib import Path

def stage(tree):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Update bsd/conf/files to compile bsd/dev/miami_keys.c
    files_bsd = tree / 'bsd/conf/files'
    files_content = files_bsd.read_text()
    if 'miami_keys.c' not in files_content:
        files_content = files_content.replace(
            'bsd/dev/miami_ufs.c\t\t\tstandard\n',
            'bsd/dev/miami_ufs.c\t\t\tstandard\nbsd/dev/miami_keys.c\t\t\tstandard\n'
        )
        files_bsd.write_text(files_content)

    # 2. Stage clean driver source at bsd/dev/miami_keys.c
    source_c = (Path(__file__).resolve().parent / 'miami_keys.c').read_text()
    dest_c = tree / 'bsd/dev/miami_keys.c'
    dest_c.write_text(source_c)

    # 3. Hook miami_keys_init() into bsd_init.c right after vfsinit()
    bsd_init = tree / 'bsd/kern/bsd_init.c'
    bsd_content = bsd_init.read_text()
    if 'miami_keys_init' not in bsd_content:
        target = 'vfsinit();\n'
        hook = (
            'vfsinit();\n'
            '#if defined(ARM64_BOARD_CONFIG_MIAMI)\n'
            '\textern void miami_keys_init(void);\n'
            '\tmiami_keys_init();\n'
            '#endif\n'
        )
        if target in bsd_content:
            bsd_content = bsd_content.replace(target, hook, 1)
            bsd_init.write_text(bsd_content)
        else:
            raise ValueError("Could not find vfsinit(); in bsd_init.c")

    return {
        'component': 'Polled SPMI Keys Driver (bsd/dev/miami_keys.c)',
        'spmi_core': '0x01c40000',
        'spmi_obs': '0x03e00000',
        'spmi_cnfg': '0x01c0a000',
        'source_sha256': hashlib.sha256(dest_c.read_bytes()).hexdigest()
    }
