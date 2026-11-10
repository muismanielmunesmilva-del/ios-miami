#!/usr/bin/env python3
"""Validate Miami hardware keys driver structures and SPMI arbiter MMIO addresses."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xnu'))
import keys_component

def test_keys():
    keys_c = ROOT / 'xnu/miami_keys.c'
    assert keys_c.exists(), "miami_keys.c must exist"
    
    content = keys_c.read_text(encoding='utf-8')
    assert 'KEYS_CORE_PA     0x01c40000u' in content, "SM6375 SPMI core address invalid"
    assert 'KEYS_OBS_PA      0x03e00000u' in content, "SM6375 SPMI obs address invalid"
    assert 'KEYS_CNFG_PA     0x01c0a000u' in content, "SM6375 SPMI cnfg address invalid"
    assert 'KEYS_PON_RT      0x0810u' in content
    assert 'KEYS_GPIO_RT     0xc110u' in content
    assert 'miami_hid_key(k, state[k]);' in content
    assert 'void miami_keys_init(void)' in content

    # Check component staging syntax
    comp_py = ROOT / 'xnu/keys_component.py'
    assert comp_py.exists(), "keys_component.py must exist"

    print("PASS: Miami keys driver and SPMI arbiter registers verified.")

if __name__ == '__main__':
    test_keys()
