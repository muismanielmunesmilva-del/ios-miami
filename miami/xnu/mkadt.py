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


def build(seed=None):
    seed = os.urandom(64) if seed is None else seed
    if len(seed) != 64:
        raise ValueError('Expected a fresh 64-byte kernel random seed')
    chosen = node('chosen', [('dram-base', u64(RAM_BASE)), ('dram-size', u64(RAM_SIZE)),
                  ('random-seed', seed), ('debug-enabled', u32(1)),
                  ('embedded-panic-log-size', u32(PANIC_SIZE)),
                  ('firmware-version', cstr('miami-loader'))], [node('memory-map')])
    cpu = node('cpu0', [('device_type', cstr('cpu')), ('compatible', cstr('ARM,v8')),
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
    return node('device-tree', [('compatible', cstr('motorola,miami') + cstr('qcom,sm6375') + cstr('AppleARM')),
                ('model', cstr('Motorola Edge 30 Neo')), ('#address-cells', u32(2)), ('#size-cells', u32(2))],
                [chosen, node('defaults'), node('cpus', [('#address-cells', u32(1)), ('#size-cells', u32(0))], [cpu]),
                 node('arm-io', [('device_type', cstr('miami-io')),
                      ('compatible', cstr('miami-io') + cstr('arm-io')),
                      ('#address-cells', u32(2)), ('#size-cells', u32(2)),
                      ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE))], [gic]),
                 node('miami-fbcon', [('reg', u64(0, 0)), ('width', u32(1080)),
                      ('height', u32(2400)), ('stride', u32(0))]),
                 node('pram', [('reg', u64(RAM_BASE + RAM_SIZE, PANIC_SIZE))])])


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
