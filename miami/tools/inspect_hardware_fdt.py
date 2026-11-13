#!/usr/bin/env python3
"""Read GPU and WLAN resources from an existing MIAMI flattened device tree.

This reads the supplied file only; it never maps MMIO or changes the device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

GPU = "/soc/qcom,kgsl-3d0@5900000"
GPU_IOMMU = "/soc/qcom,kgsl-iommu@5940000"
GPU_FIRMWARE = "/soc/qcom,kgsl-hyp"
WLAN = "/soc/qcom,icnss@C800000"


def read_property(dtb, node, name, kind):
    result = subprocess.run(
        ["fdtget", "-t", kind, str(dtb), node, name],
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError(f"Cannot read {node}/{name}: {result.stderr.strip()}")
    values = result.stdout.split()
    if not values:
        raise ValueError(f"Empty property {node}/{name}")
    return [int(value, 16) for value in values] if kind == "x" else values


def inspect(dtb):
    gpu_compatible = read_property(dtb, GPU, "compatible", "s")
    wlan_compatible = read_property(dtb, WLAN, "compatible", "s")
    if "qcom,adreno-gpu-a619-holi" not in gpu_compatible:
        raise ValueError("Device tree does not identify the MIAMI Adreno 619")
    if "qcom,icnss" not in wlan_compatible:
        raise ValueError("Device tree does not identify the expected WLAN controller")
    cells = read_property(dtb, "/soc", "#address-cells", "x")
    sizes = read_property(dtb, "/soc", "#size-cells", "x")
    if cells != [1] or sizes != [1]:
        raise ValueError("Unsupported /soc reg cell layout")

    def ranges(node):
        raw = read_property(dtb, node, "reg", "x")
        names = read_property(dtb, node, "reg-names", "s")
        if len(raw) != 2 * len(names) or any(raw[i+1] == 0 for i in range(0, len(raw), 2)):
            raise ValueError(f"Malformed register resources in {node}")
        return [{"name": name, "address": raw[i * 2], "size": raw[i * 2 + 1]}
                for i, name in enumerate(names)]

    chip = read_property(dtb, GPU, "qcom,chipid", "x")
    interrupts = read_property(dtb, GPU, "interrupts", "x")
    if len(chip) != 1 or len(interrupts) != 3:
        raise ValueError("Malformed GPU chip ID or interrupt specifier")
    if chip[0] != 0x06010901:
        raise ValueError(f"Unverified GPU chip ID 0x{chip[0]:x}")
    iommu_reg = read_property(dtb, GPU_IOMMU, "reg", "x")
    if len(iommu_reg) != 2 or iommu_reg[1] == 0:
        raise ValueError("Malformed GPU IOMMU resource")
    return {
        "dtb_sha256": hashlib.sha256(dtb.read_bytes()).hexdigest(),
        "gpu": {
            "compatible": gpu_compatible, "chipid": chip[0],
            "register_ranges": ranges(GPU), "interrupt_specifier": interrupts,
            "clock_names": read_property(dtb, GPU, "clock-names", "s"),
            "iommu_reg": iommu_reg,
            "zap_firmware": read_property(dtb, GPU_FIRMWARE, "qcom,firmware-name", "s"),
        },
        "wlan": {
            "compatible": wlan_compatible, "resources": ranges(WLAN),
            "iommu_specifier": read_property(dtb, WLAN, "iommus", "x"),
            "address_note": "smmu_iova_ipa describes an IOVA range, not physical MMIO.",
            "chipset": None,
        },
        "note": "Device-tree resources only; no device initialization or hardware validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dtb", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.dtb), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Hardware inspection failed: {exc}\n")


if __name__ == "__main__":
    main()
