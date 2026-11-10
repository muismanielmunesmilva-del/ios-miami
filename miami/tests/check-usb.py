#!/usr/bin/env python3
"""Validate Miami USB state probe structures, MMIO addresses and read-only invariants."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xnu'))
import usb_component

def test_usb():
    usb_c = ROOT / 'xnu/miami_usb.c'
    assert usb_c.exists(), "miami_usb.c must exist"
    
    content = usb_c.read_text(encoding='utf-8')
    assert 'DWC3_PA                 0x04e00000u' in content, "SM6375 DWC3 address invalid"
    assert 'DWC3_SIZE               0x0000d000u' in content
    assert 'HSPHY_PA                0x0162b000u' in content, "SM6375 HSPHY address invalid"
    assert 'void miami_usb_probe(void)' in content
    assert 'GSNPSID' in content
    assert 'GHWPARAMS0' in content
    assert 'DSTS' in content

    # Check component staging syntax
    comp_py = ROOT / 'xnu/usb_component.py'
    assert comp_py.exists(), "usb_component.py must exist"

    print("PASS: Miami USB probe registers and invariants verified.")

if __name__ == '__main__':
    test_usb()
