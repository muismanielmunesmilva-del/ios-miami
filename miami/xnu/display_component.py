"""Stage XNU native display pipeline (IOCoreSurfaceRoot + AppleCLCD / IOMobileFramebuffer) for MIAMI."""
import hashlib
from pathlib import Path
import subprocess

def stage(tree, edit_func=None):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Apply configuration patch (files.arm64, KernelConfigTables.cpp, SweetPlatformExpert.cpp)
    conf_patch = (Path(__file__).resolve().parent / '0046-miami-display-conf.patch').read_bytes()
    for flags in (['--check'], []):
        subprocess.run(['git', '-C', str(tree), 'apply', *flags,
                        '--whitespace=nowarn', '-'], input=conf_patch, check=True)
    (patch_dir / '0046-miami-display-conf.patch').write_bytes(conf_patch)

    # 2. Copy clean source files into iokit/Kernel/arm/
    src_dir = Path(__file__).resolve().parent
    for fname in ('MiamiSurface.h', 'MiamiSurface.cpp', 'MiamiFramebuffer.cpp'):
        content = (src_dir / fname).read_bytes()
        dest = tree / f'iokit/Kernel/arm/{fname}'
        dest.write_bytes(content)

    return {
        'component': 'IOSurface (IOCoreSurfaceRoot) + IOMobileFramebuffer (AppleCLCD)',
        'surface_h': hashlib.sha256((src_dir / 'MiamiSurface.h').read_bytes()).hexdigest(),
        'surface_cpp': hashlib.sha256((src_dir / 'MiamiSurface.cpp').read_bytes()).hexdigest(),
        'framebuffer_cpp': hashlib.sha256((src_dir / 'MiamiFramebuffer.cpp').read_bytes()).hexdigest(),
        'conf_patch': hashlib.sha256(conf_patch).hexdigest()
    }
