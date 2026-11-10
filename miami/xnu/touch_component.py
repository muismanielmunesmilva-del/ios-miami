"""Stage XNU native Touchscreen SPI Hardware Driver for MIAMI."""
import hashlib
from pathlib import Path

def stage(tree):
    # 1. Update bsd/conf/files to compile bsd/dev/miami_touch.c
    files_bsd = tree / 'bsd/conf/files'
    files_content = files_bsd.read_text()
    if 'miami_touch.c' not in files_content:
        files_content = files_content.replace(
            'bsd/dev/miami_usb.c\t\t\tstandard\n',
            'bsd/dev/miami_usb.c\t\t\tstandard\nbsd/dev/miami_touch.c\t\t\tstandard\n'
        )
        files_bsd.write_text(files_content)

    # 2. Stage clean driver source at bsd/dev/miami_touch.c
    source_c = (Path(__file__).resolve().parent / 'miami_touch.c').read_text()
    dest_c = tree / 'bsd/dev/miami_touch.c'
    dest_c.write_text(source_c)

    # 3. Hook miami_touch_init() into bsd_init.c right after miami_usb_probe()
    bsd_init = tree / 'bsd/kern/bsd_init.c'
    bsd_content = bsd_init.read_text()
    if 'miami_touch_init' not in bsd_content:
        target = '\tmiami_usb_probe();\n'
        hook = (
            '\tmiami_usb_probe();\n'
            '#if defined(ARM64_BOARD_CONFIG_MIAMI)\n'
            '\textern void miami_touch_init(void);\n'
            '\tmiami_touch_init();\n'
            '#endif\n'
        )
        if target in bsd_content:
            bsd_content = bsd_content.replace(target, hook, 1)
            bsd_init.write_text(bsd_content)
        else:
            raise ValueError("Could not find miami_usb_probe(); in bsd_init.c")

    return {
        'component': 'Hardware Touchscreen Driver (bsd/dev/miami_touch.c)',
        'se_pa': '0x04a80000',
        'gcc_pa': '0x01400000',
        'tlmm_pa': '0x00400000',
        'source_sha256': hashlib.sha256(dest_c.read_bytes()).hexdigest()
    }
