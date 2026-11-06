#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
kernel=${1:?Pass the compiled kernel.development.miami}
libfdt=${2:?Pass the pinned dtc checkout}
avbtool=${3:?Pass the official AOSP avbtool.py}
live_fdt=${4:?Pass the private live miami FDT for host validation}
test "$(git -C "$libfdt" rev-parse HEAD)" = 54e547173bf0f2a4cc35eba8b5738caf38b9230f
mkdir -p out
python3 payload.py "$kernel" out/payload.bin
gcc -O2 -Wall -Wextra -Werror -I"$libfdt/libfdt" verify-input.c plan.c ram.c ../probe/layout.c \
    "$libfdt/libfdt/fdt.c" "$libfdt/libfdt/fdt_ro.c" "$libfdt/libfdt/fdt_check.c" -o out/verify-input
out/verify-input out/payload.bin "$live_fdt"
python3 - <<'PY'
from pathlib import Path
text = Path('../probe/start.S').read_text()
for symbol in ('_stack_top', '_bss_start', '_bss_end'):
    reg = 'x2' if symbol == '_bss_end' else 'x1'
    before = f'    adr {reg}, {symbol}'
    assert text.count(before) == 1
    text = text.replace(before, f'    adrp {reg}, {symbol}\n    add {reg}, {reg}, :lo12:{symbol}')
Path('out/start.S').write_text(text)
Path('out/embed.S').write_text('.section .payload, "a"\n.incbin "out/payload.bin"\n')
PY
flags=(-O2 -Wall -Wextra -Werror -ffreestanding -nostdlib -fno-pic -fno-pie
       -fno-builtin -fno-stack-protector -fno-asynchronous-unwind-tables
       -mgeneral-regs-only -mstrict-align -ffunction-sections -fdata-sections
       -I"$libfdt/libfdt")
objects=()
for source in out/start.S out/embed.S main.c plan.c ram.c ../probe/display.c ../probe/layout.c ../probe/memory.c \
    "$libfdt/libfdt/fdt.c" "$libfdt/libfdt/fdt_ro.c" "$libfdt/libfdt/fdt_check.c"; do
    name=$(basename "${source%.*}")
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$source" -o "out/$name.o"
    objects+=("out/$name.o")
done
if aarch64-linux-gnu-readelf -r out/main.o out/plan.o out/ram.o out/display.o out/layout.o out/memory.o | grep -q ABS64; then
    echo 'Refusing absolute C pointers in position-independent loader' >&2
    exit 1
fi
aarch64-linux-gnu-gcc -nostdlib -static -no-pie -Wl,--gc-sections,--build-id=none,--no-warn-rwx-segments \
    -T loader.ld "${objects[@]}" -o out/loader.elf
aarch64-linux-gnu-objcopy -O binary out/loader.elf out/Image
size=$(aarch64-linux-gnu-nm out/loader.elf | awk '$3=="_end" {print "0x"$1}')
truncate -s "$((size))" out/Image
python3 - <<'PY'
import struct
from pathlib import Path
image = Path('out/Image').read_bytes()
assert image[56:60] == b'ARM\x64'
assert struct.unpack_from('<Q', image, 16)[0] == len(image)
assert struct.unpack_from('<Q', image, 24)[0] == 0xc
assert len(image) % 16384 == 0
PY
if aarch64-linux-gnu-readelf -r out/loader.elf | grep -q R_AARCH64; then
    echo 'Refusing unresolved relocations in final loader' >&2
    exit 1
fi
if [ "${MIAMI_COMPILE_ONLY:-0}" = 1 ]; then
    echo 'Compile-only check: no Android boot image generated.'
    exit 0
fi
python3 - <<'PY'
import gzip
from pathlib import Path
name = b'TRAILER!!!\0'
fields = [0] * 13
fields[11] = len(name)
archive = b'070701' + b''.join(f'{v:08x}'.encode() for v in fields) + name
archive += b'\0' * (-len(archive) % 4)
Path('out/ramdisk.gz').write_bytes(gzip.compress(archive, mtime=0))
PY
mkbootimg --header_version 3 --kernel out/Image --ramdisk out/ramdisk.gz \
    --os_version 11.0.0 --os_patch_level 2025-09 --cmdline 'miami_xnu=1' -o out/miami-xnu-raw.img
cp out/miami-xnu-raw.img out/boot.img
python3 "$avbtool" add_hash_footer --image out/boot.img --partition_name boot \
    --partition_size 100663296 --algorithm NONE --hash_algorithm sha256 \
    --salt 0000000000000000000000000000000000000000000000000000000000000000 \
    --prop com.android.build.boot.os_version:11.0.0 \
    --prop com.android.build.boot.fingerprint:local/miami-xnu/miami:11/MIAMI_XNU/0004:eng/test-keys
python3 "$avbtool" verify_image --image out/boot.img
sha256sum out/Image out/payload.bin out/boot.img
echo 'Built a temporary image; no phone command has been issued.'
