#!/usr/bin/env python3
"""Validate Miami HID and Touchscreen subsystem classes and structures."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xnu'))
import hid_component

def test_hid():
    hid_dir = ROOT / 'xnu/hid'
    assert hid_dir.exists(), "hid directory must exist"
    
    # 1. Verify key files exist
    required_files = [
        'AppleHIDUsageTables.h',
        'IOHIDEvent.h',
        'IOHIDEvent.cpp',
        'IOHIDEventService.h',
        'IOHIDEventServiceQueue.h',
        'IOHIDEventServiceQueue.cpp',
        'IOHIDEventServiceUserClient.h',
        'IOHIDEventServiceUserClient.cpp',
        'MiamiHID.cpp'
    ]
    for rf in required_files:
        p = hid_dir / rf
        assert p.exists(), f"Missing required HID file: {rf}"
        content = p.read_text(encoding='utf-8', errors='ignore')
        assert len(content) > 100, f"File too small: {rf}"

    # 2. Verify MiamiHID.cpp contains Miami classes
    miami_hid = (hid_dir / 'MiamiHID.cpp').read_text(encoding='utf-8', errors='ignore')
    assert 'class MiamiHIDButtons' in miami_hid
    assert 'class MiamiHIDTouch' in miami_hid
    assert 'miami_hid_key' in miami_hid
    assert 'miami_hid_touch' in miami_hid
    assert 'SweetHID' not in miami_hid

    print("PASS: Miami HID and Touchscreen files and classes verified.")

if __name__ == '__main__':
    test_hid()
