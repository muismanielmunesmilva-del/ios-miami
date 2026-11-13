#!/usr/bin/env python3
"""Exercise hardware inspection with synthetic, explicitly non-device DTBs."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

script = Path(__file__).resolve().parents[1] / "tools" / "inspect_hardware_fdt.py"
spec = importlib.util.spec_from_file_location("hardware_fdt", script)
hardware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardware)

DTS = r"""
/dts-v1/;
/ {
  soc {
    #address-cells = <1>;
    #size-cells = <1>;
    qcom,kgsl-hyp { qcom,firmware-name = "a615_zap"; };
    qcom,kgsl-3d0@5900000 {
      compatible = "qcom,kgsl-3d0", "qcom,adreno-gpu-a619-holi";
      reg = <0x5900000 0x40000>;
      reg-names = "kgsl_3d0_reg_memory";
      interrupts = <0 177 4>;
      clock-names = "core_clk";
      qcom,chipid = <0x06010901>;
    };
    qcom,kgsl-iommu@5940000 { reg = <0x5940000 0x10000>; };
    qcom,icnss@C800000 {
      compatible = "qcom,icnss";
      reg = <0xc800000 0x800000 0xb0000000 0x10000>;
      reg-names = "membase", "smmu_iova_ipa";
      iommus = <1 0x80 1>;
    };
  };
};
"""

with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "test.dts"
    dtb = Path(directory) / "test.dtb"
    def compile_tree(text):
        source.write_text(text)
        subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o",
                        str(dtb), str(source)], check=True)

    compile_tree(DTS)
    info = hardware.inspect(dtb)
    assert info["gpu"]["chipid"] == 0x06010901
    assert info["gpu"]["register_ranges"][0]["address"] == 0x05900000
    assert info["wlan"]["chipset"] is None
    assert info["wlan"]["resources"][1]["name"] == "smmu_iova_ipa"
    for invalid in (DTS.replace("qcom,adreno-gpu-a619-holi", "qcom,other-gpu"),
                    DTS.replace("0x06010901", "0x06010902"),
                    DTS.replace("0x5900000 0x40000", "0x5900000 0")):
        compile_tree(invalid)
        try:
            hardware.inspect(dtb)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid hardware tree was accepted")
print("MIAMI GPU and WLAN FDT inspection checks passed")
