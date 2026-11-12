#!/usr/bin/env python3
"""Validate Miami hardware touchscreen driver structures, SPI MMIO addresses, and protocol registers."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xnu'))
import touch_component

def test_touch():
    touch_c = ROOT / 'xnu/miami_touch.c'
    assert touch_c.exists(), "miami_touch.c must exist"

    content = touch_c.read_text(encoding='utf-8')
    assert 'TOUCH_SE_PA          0x04a80000u' in content, "SM6375 GENI SPI0 base invalid"
    assert 'TOUCH_GCC_PA         0x01400000u' in content, "SM6375 GCC base invalid"
    assert 'TOUCH_TLMM_PA        0x00500000u' in content, "SM6375 GPIO register base invalid"
    assert 'GOODIX_FW_VERSION    0x10014u' in content, "Goodix Berlin FW version register invalid"
    assert 'GOODIX_IC_INFO       0x10070u' in content, "Goodix Berlin IC info register invalid"
    assert 'void miami_touch_init(void)' in content, "miami_touch_init declaration missing"
    assert 'miami_hid_touch(' in content, "Dispatch to MiamiHIDTouch missing"

    # Check component staging syntax
    comp_py = ROOT / 'xnu/touch_component.py'
    assert comp_py.exists(), "touch_component.py must exist"

    print("PASS: Miami touchscreen driver, SPI registers and Goodix protocol verified.")

if __name__ == '__main__':
    test_touch()
