"""Stage XNU minimal read-only USB state probe for MIAMI."""
import hashlib
from pathlib import Path

def stage(tree):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Update bsd/conf/files to compile bsd/dev/miami_usb.c
    files_bsd = tree / 'bsd/conf/files'
    files_content = files_bsd.read_text()
    if 'miami_usb.c' not in files_content:
        files_content = files_content.replace(
            'bsd/dev/miami_keys.c\t\t\tstandard\n',
            'bsd/dev/miami_keys.c\t\t\tstandard\nbsd/dev/miami_usb.c\t\t\tstandard\n'
        )
        files_bsd.write_text(files_content)
    protocol_entry = 'bsd/dev/remote_root_protocol.c\t\tstandard\n'
    if protocol_entry not in files_content:
        anchor = 'bsd/dev/miami_usb.c\t\t\tstandard\n'
        if anchor not in files_content:
            raise ValueError("Could not find miami_usb.c entry in bsd/conf/files")
        files_content = files_content.replace(anchor, anchor + protocol_entry, 1)
        files_bsd.write_text(files_content)
    client_entry = 'bsd/dev/remote_root_client.c\t\tstandard\n'
    if client_entry not in files_content:
        if protocol_entry not in files_content:
            raise ValueError('Could not find remote root protocol entry')
        files_content = files_content.replace(protocol_entry, protocol_entry + client_entry, 1)
        files_bsd.write_text(files_content)

    # 2. Stage clean driver source at bsd/dev/miami_usb.c
    source_c = (Path(__file__).resolve().parent / 'miami_usb.c').read_text()
    dest_c = tree / 'bsd/dev/miami_usb.c'
    dest_c.write_text(source_c)
    for name in ('remote_root_protocol.c', 'remote_root_protocol.h',
                 'remote_root_client.c', 'remote_root_client.h'):
        (tree / 'bsd/dev' / name).write_bytes(
            (Path(__file__).resolve().parent / name).read_bytes()
        )

    # 3. Hook miami_usb_probe() into bsd_init.c right after miami_keys_init()
    bsd_init = tree / 'bsd/kern/bsd_init.c'
    bsd_content = bsd_init.read_text()
    if 'miami_usb_probe' not in bsd_content:
        target = '\tmiami_keys_init();\n'
        hook = (
            '\tmiami_keys_init();\n'
            '#if defined(ARM64_BOARD_CONFIG_MIAMI)\n'
            '\textern void miami_usb_probe(void);\n'
            '\tmiami_usb_probe();\n'
            '#endif\n'
        )
        if target in bsd_content:
            bsd_content = bsd_content.replace(target, hook, 1)
            bsd_init.write_text(bsd_content)
        else:
            raise ValueError("Could not find miami_keys_init(); in bsd_init.c")

    return {
        'component': 'Read-Only USB State Probe (bsd/dev/miami_usb.c)',
        'dwc3_base': '0x04e00000',
        'dwc3_size': '0x0000d000',
        'hsphy_base': '0x0162b000',
        'source_sha256': hashlib.sha256(dest_c.read_bytes()).hexdigest()
    }
