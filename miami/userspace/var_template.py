#!/usr/bin/env python3
"""Writable RAM /private/var template for the rootpid1 bring-up.

On iOS /private/var is the data volume, created at restore; the OS root only
has the /var -> private/var and /tmp -> private/var/tmp links. The MIAMI root
is a read-only remote HFS+, so the kernel exposes a zeroed RAM disk
(/dev/miamivar0, xnu/var_ram_block.c) initialised from this template, and
init mounts it read-write on /private/var before the chroot. Nothing persists.

The template holds only directories, owners and modes, logd's .migrated
markers and the plain-plist system keybag read with
/defaults/no-effaceable-storage (both as in ios-sweet tools/mkiosroot.sh).
No IPSW content.

  var_template.py build OUT.hfs        (Linux: mkfs.hfsplus + guestfish)
  var_template.py header IN.hfs OUT.h  (sparse C header for the kernel)
"""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_BYTES = 128 * 1024 * 1024
BLOCK = 4096
MOBILE = 501

# (path relative to /private/var, uid, gid, mode)
DIRECTORIES = [
    ('', 0, 0, 0o755),
    ('mobile', MOBILE, MOBILE, 0o755),
    ('mobile/Library', MOBILE, MOBILE, 0o755),
    ('mobile/Library/Preferences', MOBILE, MOBILE, 0o755),
    ('mobile/Library/Caches', MOBILE, MOBILE, 0o755),
    ('mobile/Library/Logs', MOBILE, MOBILE, 0o755),
    ('mobile/Library/Logs/CrashReporter', MOBILE, MOBILE, 0o755),
    ('mobile/Library/Application Support', MOBILE, MOBILE, 0o755),
    ('mobile/Media', MOBILE, MOBILE, 0o755),
    ('mobile/Documents', MOBILE, MOBILE, 0o755),
    ('mobile/tmp', MOBILE, MOBILE, 0o755),
    ('root', 0, 0, 0o755),
    ('root/Library', 0, 0, 0o755),
    ('root/Library/Preferences', 0, 0, 0o755),
    ('root/Library/Caches', 0, 0, 0o755),
    ('root/Library/Logs', 0, 0, 0o755),
    ('tmp', 0, 0, 0o1777),
    ('run', 0, 1, 0o775),
    ('db', 0, 0, 0o755),
    ('db/diagnostics', 272, 272, 0o751),
    ('db/diagnostics/timesync', 272, 272, 0o755),
    ('db/uuidtext', 272, 272, 0o755),
    ('db/lockdown', 0, 0, 0o755),
    ('db/timed', 266, 266, 0o755),
    ('db/analyticsd', 263, 263, 0o755),
    ('db/datadetectors', 257, 257, 0o755),
    ('db/rmd', 277, 277, 0o755),
    ('db/coreml', 280, 280, 0o755),
    ('db/knowledgegraphd', 279, 279, 0o755),
    ('db/mmaintenanced', 283, 283, 0o755),
    ('db/darwindaemon', 284, 284, 0o755),
    ('db/accessoryupdater', 278, 278, 0o755),
    ('db/diskimagesiod', 271, 271, 0o755),
    ('db/gpsd', 267, 267, 0o755),
    ('db/findmydevice', 254, 254, 0o755),
    ('db/ondemand', 249, 249, 0o755),
    ('db/astris', 245, 245, 0o755),
    ('log', 0, 0, 0o755),
    ('logs', 0, 0, 0o755),
    ('containers', 0, 0, 0o755),
    ('containers/Bundle', 33, 33, 0o755),
    ('containers/Data', 0, 0, 0o755),
    ('containers/Data/System', 0, 0, 0o755),
    ('containers/Shared', 0, 0, 0o755),
    ('containers/Shared/SystemGroup', 0, 0, 0o755),
    ('containers/Temp', 0, 0, 0o755),
    ('keybags', 0, 0, 0o700),
    ('preferences', 0, 0, 0o755),
    ('preferences/SystemConfiguration', 0, 0, 0o755),
    ('Keychains', 64, 64, 0o755),
    ('MobileAsset', 0, 0, 0o755),
    ('MobileSoftwareUpdate', 0, 0, 0o755),
    ('Managed Preferences', 0, 0, 0o755),
    ('installd', 33, 33, 0o755),
    ('networkd', 24, 24, 0o755),
    ('wireless', 25, 25, 0o755),
    ('empty', 0, 0, 0o555),
    ('folders', 0, 0, 0o755),
    ('vm', 0, 0, 0o755),
    ('spool', 0, 0, 0o755),
    ('cache', 0, 0, 0o755),
    ('local', 0, 0, 0o755),
    ('lib', 0, 0, 0o755),
    ('hardware', 0, 0, 0o755),
    ('protected', 0, 0, 0o755),
    ('staged_system_apps', 0, 0, 0o755),
]

SYSTEMBAG = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    b'<plist version="1.0"><dict><key>KeyBagKeys</key><data>U1dFRVQ=</data></dict></plist>\n')

# (path, uid, gid, mode, contents)
FILES = [
    ('db/diagnostics/.migrated', 272, 272, 0o644, b''),
    ('db/diagnostics/timesync/.migrated', 272, 272, 0o644, b''),
    ('db/uuidtext/.migrated', 272, 272, 0o644, b''),
    ('keybags/systembag.kb', 0, 0, 0o600, SYSTEMBAG),
]


def quote(path):
    return '"/' + path.replace('"', '\\"') + '"'


def guestfish_script(staging):
    lines = ['run', 'mount /dev/sda /']
    for path, uid, gid, mode in DIRECTORIES:
        if path:
            lines.append(f'mkdir {quote(path)}')
        lines += [f'chown {uid} {gid} {quote(path)}', f'chmod 0{mode:o} {quote(path)}']
    for index, (path, uid, gid, mode, data) in enumerate(FILES):
        local = staging / f'file{index}'
        local.write_bytes(data)
        lines += [f'upload {local} {quote(path)}', f'chown {uid} {gid} {quote(path)}',
                  f'chmod 0{mode:o} {quote(path)}']
    lines += ['umount /', 'exit']
    return '\n'.join(lines) + '\n'


def build(out):
    out = Path(out)
    if out.exists():
        raise SystemExit(f'refusing to overwrite {out}')
    with open(out, 'wb') as f:
        f.truncate(IMAGE_BYTES)
    subprocess.run(['mkfs.hfsplus', '-s', '-b', str(BLOCK), '-v', 'MiamiVar', str(out)], check=True)
    with tempfile.TemporaryDirectory(prefix='miami-var-') as folder:
        staging = Path(folder)
        script = staging / 'populate.guestfish'
        script.write_text(guestfish_script(staging))
        subprocess.run(['guestfish', '--format=raw', '-a', str(out), '-f', str(script)], check=True)
    subprocess.run(['fsck.hfsplus', '-f', '-n', str(out)], check=True)


def runs(image):
    """Maximal runs of non-zero 4 KiB blocks: [(first_block, block_count)]."""
    result, start = [], None
    for i in range(len(image) // BLOCK):
        nonzero = any(image[i * BLOCK:(i + 1) * BLOCK])
        if nonzero and start is None:
            start = i
        elif not nonzero and start is not None:
            result.append((start, i - start))
            start = None
    if start is not None:
        result.append((start, len(image) // BLOCK - start))
    return result


def header(src, out):
    image = Path(src).read_bytes()
    if len(image) != IMAGE_BYTES:
        raise SystemExit('unexpected template size')
    if image[1024:1026] not in (b'H+', b'HX'):
        raise SystemExit('not an HFS+ image')
    spans = runs(image)
    data = b''.join(image[s * BLOCK:(s + n) * BLOCK] for s, n in spans)
    text = [
        '/* Generated by miami/userspace/var_template.py; do not edit. */',
        f'/* Template SHA-256 {hashlib.sha256(image).hexdigest()} */',
        f'#define MIAMI_VAR_IMAGE_BYTES {IMAGE_BYTES}u',
        f'#define MIAMI_VAR_BLOCK {BLOCK}u',
        f'#define MIAMI_VAR_RUNS {len(spans)}u',
        'static const uint32_t miami_var_runs[MIAMI_VAR_RUNS][2] = {',
    ]
    text += [f'\t{{{s}u, {n}u}},' for s, n in spans]
    text += ['};', f'static const uint8_t miami_var_data[{len(data)}] = {{']
    for i in range(0, len(data), 24):
        text.append('\t' + ', '.join(f'0x{b:02x}' for b in data[i:i + 24]) + ',')
    text.append('};')
    Path(out).write_text('\n'.join(text) + '\n')
    print(f'{len(spans)} runs, {len(data)} bytes of non-zero blocks')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'build':
        build(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == 'header':
        header(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
