#!/usr/bin/env python3
"""Initial miami ADT: one CPU, no storage or peripheral drivers.

Framebuffer base/stride are placeholders patched by the bounded loader from
the active ABL pipe. The upper RAM bank is FDT-derived, not yet hardware-tested.
"""
import argparse
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import adt

RAM_BASE, RAM_TOTAL, PANIC_SIZE = 0x180000000, 0x40000000, 0x100000
RAM_SIZE = RAM_TOTAL - PANIC_SIZE
SOC_BASE = 0x01000000
UFS_BASE, UFS_SIZE = 0x04804000, 0x20000
BOOT_CPU_COMPAT = 'arm,cortex-a55'  # MIDR 0x412fd050 measured on the boot CPU


def u32(*values):
    return struct.pack('<' + 'I' * len(values), *values)


def u64(*values):
    return struct.pack('<' + 'Q' * len(values), *values)


def cstr(value):
    return value.encode() + b'\0'


def node(name, props=(), children=()):
    result = adt.Node()
    result.props = [('name', 0, cstr(name))] + [(key, 0, value) for key, value in props]
    result.children = list(children)
    return result


# Opt-in identity of the iPhone X (D22AP, iPhone10,3) whose iOS 16.7.16 20H392
# userland is staged on the remote root. Same layout as ios-sweet patch 0059:
# compatible[0] -> hw.model/hw.target, model -> hw.machine/hw.product, and
# target-type -> hw.targettype (IOPMrootDomain sysctl_targettype). The real
# launchd logs "sysctl hw.targettype was not set" and skipped its boot tasks
# (launchd_cache_loader included) without it. 'motorola,miami' stays in the
# compatible list: the platform expert matches it with IONameMatch.
IPHONE_IDENTITY = {
    'compatible': ('D22AP', 'iPhone10,3'),
    'model': 'iPhone10,3',
    'target-type': 'D22',
    'target-sub-type': 'D22AP',
    'manufacturer': 'Apple Inc.',
}


def build(seed=None, include_ufs=False, allow_unrestricted_fs=False, iphone_identity=False):
    seed = os.urandom(64) if seed is None else seed
    if len(seed) != 64:
        raise ValueError('Expected a fresh 64-byte kernel random seed')
    chosen_children = [node('memory-map')]
    if allow_unrestricted_fs:
        # Experimental local boot policy: CSR_ALLOW_UNRESTRICTED_FS only.
        # This is not Apple trust-cache or signature verification.
        chosen_children.append(node('asmb', [('lp-sip0', u64(2))]))
    chosen = node('chosen', [('dram-base', u64(RAM_BASE)), ('dram-size', u64(RAM_SIZE)),
                  ('random-seed', seed), ('debug-enabled', u32(1)),
                  ('embedded-panic-log-size', u32(PANIC_SIZE)),
                  ('firmware-version', cstr('miami-loader'))], chosen_children)
    cpu = node('cpu0', [('device_type', cstr('cpu')), ('compatible', cstr(BOOT_CPU_COMPAT) + cstr('ARM,v8')),
               ('reg', u32(0)), ('cpu-id', u32(0)), ('cluster-id', u32(0)),
               ('cluster-type', u32(0)), ('die-cluster-id', u32(0)),
               ('cluster-core-id', u32(0)), ('l2-cache-id', u32(0)), ('l3-cache-id', u32(0)),
               ('state', cstr('running')), ('timebase-frequency', u32(19200000)),
               # Preserve XNU pe_identify_machine.c's diagnostic fallback
               # rates, avoiding zero divisors. These are NOT measured CPU/
               # bus clocks and do not program any hardware clock controller.
               ('clock-frequency', u32(400000000)), ('bus-frequency', u32(100000000)),
               ('fixed-frequency', u32(19200000))])
    gic = node('gic', [('compatible', cstr('arm,gic-v3')), ('interrupt-controller', b''),
               ('virtual-timer-intid', u32(19)),
               ('reg', u64(0x0f200000 - SOC_BASE, 0x10000, 0x0f240000 - SOC_BASE, 0x100000))])
    disp = node('disp0', [
        ('device_type', cstr('display-subsystem')),
        ('compatible', cstr('miami,display')),
        ('canvas-width', u32(1080)),
        ('canvas-height', u32(2400)),
    ])
    # No effaceable storage (as ios-sweet tools/mkadt.py): keybagd then reads
    # /private/var/keybags/systembag.kb as a plain plist instead of failing
    # fatally ("FATAL KEYBAG ERROR" -> reboot). Only on the opt-in D22 identity.
    defaults = node('defaults', [('no-effaceable-storage', u32(1))] if iphone_identity else [])
    children = [chosen, defaults, node('cpus', [('#address-cells', u32(1)), ('#size-cells', u32(0))], [cpu]),
                 node('arm-io', [('device_type', cstr('miami-io')),
                      ('compatible', cstr('miami-io') + cstr('arm-io')),
                      ('#address-cells', u32(2)), ('#size-cells', u32(2)),
                      ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE))], [gic, disp]),
                 node('miami-fbcon', [('reg', u64(0, 0)), ('width', u32(1080)),
                      ('height', u32(2400)), ('stride', u32(0))]),
                 node('pram', [('reg', u64(RAM_BASE + RAM_SIZE, PANIC_SIZE))])]
    if include_ufs:
        children.append(node('miami-ufs', [('compatible', cstr('qcom,ufshc')),
                             ('reg', u64(UFS_BASE, UFS_SIZE))]))
    compatible = cstr('motorola,miami') + cstr('qcom,sm6375') + cstr('AppleARM')
    identity = [('model', cstr('Motorola Edge 30 Neo'))]
    if iphone_identity:
        compatible = b''.join(cstr(c) for c in IPHONE_IDENTITY['compatible']) + compatible
        identity = [(key, cstr(IPHONE_IDENTITY[key]))
                    for key in ('model', 'target-type', 'target-sub-type', 'manufacturer')]
    return node('device-tree', [('compatible', compatible)] + identity +
                [('#address-cells', u32(2)), ('#size-cells', u32(2))],
                children)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    blob = adt.serialize(build())
    root, end = adt.parse(blob)
    assert end == len(blob)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes, one CPU; framebuffer patched at runtime')
