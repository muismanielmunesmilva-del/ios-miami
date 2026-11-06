#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
libfdt=${1:?Pass the pinned dtc checkout directory}
target_dtb=${2:?Pass the live miami DTB for mandatory host validation}
avbtool=${3:?Pass AOSP avbtool.py}
expected_dtc=54e547173bf0f2a4cc35eba8b5738caf38b9230f
test "$(git -C "$libfdt" rev-parse HEAD)" = "$expected_dtc"
mkdir -p out
gcc -O2 -Wall -Wextra -Werror -I"$libfdt/libfdt" verify-layout.c layout.c \
    "$libfdt/libfdt/fdt.c" "$libfdt/libfdt/fdt_ro.c" -o out/verify-layout
out/verify-layout "$target_dtb"
gcc -O2 -Wall -Wextra -Werror verify-tables.c tables16k.c -o out/verify-tables
out/verify-tables
flags=(-O2 -Wall -Wextra -Werror -ffreestanding -nostdlib -fno-pic -fno-pie
       -fno-builtin -fno-stack-protector -fno-asynchronous-unwind-tables
       -mgeneral-regs-only -mstrict-align -ffunction-sections -fdata-sections
       -I"$libfdt/libfdt")
for source in start.S probe.c display.c interrupts.c tables16k.c mmu16k.c layout.c memory.c "$libfdt/libfdt/fdt.c" "$libfdt/libfdt/fdt_ro.c"; do
    name=$(basename "${source%.*}")
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$source" -o "out/$name.o"
done
if aarch64-linux-gnu-readelf -r out/probe.o out/display.o out/interrupts.o out/tables16k.o out/mmu16k.o out/layout.o out/memory.o out/fdt.o out/fdt_ro.o | grep -q ABS64; then
    echo 'C objects contain absolute pointers; refusing to build' >&2
    exit 1
fi
aarch64-linux-gnu-gcc -nostdlib -static -no-pie -Wl,--gc-sections,--build-id=none,--no-warn-rwx-segments \
    -T probe.ld out/start.o out/probe.o out/display.o out/interrupts.o out/tables16k.o out/mmu16k.o out/layout.o out/memory.o out/fdt.o out/fdt_ro.o -o out/probe.elf
aarch64-linux-gnu-objcopy -O binary out/probe.elf out/Image
size=$(aarch64-linux-gnu-nm out/probe.elf | awk '$3=="_end" {print "0x"$1}')
truncate -s "$((size))" out/Image
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
    --os_version 11.0.0 --os_patch_level 2025-09 --cmdline 'miami_probe=1' \
    -o out/miami-probe-0005.img
mkdir -p out/avb
cp out/miami-probe-0005.img out/avb/boot.img
python3 "$avbtool" add_hash_footer --image out/avb/boot.img --partition_name boot \
    --partition_size 100663296 --algorithm NONE --hash_algorithm sha256 \
    --salt 0000000000000000000000000000000000000000000000000000000000000000 \
    --prop com.android.build.boot.os_version:11.0.0 \
    --prop com.android.build.boot.fingerprint:local/miami-probe/miami:11/MIAMI_PROBE/0005:eng/test-keys
python3 "$avbtool" verify_image --image out/avb/boot.img
sha256sum out/Image out/miami-probe-0005.img out/avb/boot.img
