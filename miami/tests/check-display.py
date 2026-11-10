"""Validate Miami display subsystem (IOCoreSurfaceRoot + AppleCLCD / IOMobileFramebuffer)."""
from pathlib import Path
import sys

PORT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PORT / 'miami/xnu'))
import mkadt


def check():
    # 1. Validate ADT contains disp0 under arm-io
    tree = mkadt.build()
    arm_io = next(c for c in tree.children if any(k == 'name' and b'arm-io' in v for k, _, v in c.props))
    disp0 = next(c for c in arm_io.children if any(k == 'name' and b'disp0' in v for k, _, v in c.props))

    disp_props = dict((k, v) for k, _, v in disp0.props)
    assert b'display-subsystem' in disp_props['device_type']
    assert b'miami,display' in disp_props['compatible']
    print('PASS: ADT disp0 node and compatible string verified.')

    # 2. Validate C++ source components
    xnu_dir = PORT / 'miami/xnu'
    surf_h = (xnu_dir / 'MiamiSurface.h').read_text()
    surf_cpp = (xnu_dir / 'MiamiSurface.cpp').read_text()
    fb_cpp = (xnu_dir / 'MiamiFramebuffer.cpp').read_text()

    assert 'class MiamiSurface' in surf_h
    assert 'class IOCoreSurfaceRoot' in surf_cpp
    assert 'class AppleCLCD : public IOMobileFramebuffer' in fb_cpp
    assert 'fSurface = miami_surface_create_physical' in fb_cpp

    print('PASS: MiamiSurface and MiamiFramebuffer classes verified.')


if __name__ == '__main__':
    check()
