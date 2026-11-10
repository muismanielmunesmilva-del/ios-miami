"""Stage XNU native display pipeline (IOCoreSurfaceRoot + AppleCLCD / IOMobileFramebuffer) for MIAMI."""
import hashlib
from pathlib import Path

def stage(tree, edit_func):
    # 1. Update iokit/conf/files.arm64 to add MiamiSurface.cpp and MiamiFramebuffer.cpp
    files_arm64 = tree / 'iokit/conf/files.arm64'
    text = files_arm64.read_text()
    add_files = (
        'iokit/Kernel/arm/MiamiSurface.cpp                                optional iokitcpp\n'
        'iokit/Kernel/arm/MiamiFramebuffer.cpp                            optional iokitcpp\n'
    )
    if 'MiamiSurface.cpp' not in text:
        text += add_files
        files_arm64.write_text(text)

    # 2. Update iokit/KernelConfigTables.cpp to register IOCoreSurfaceRoot and AppleCLCD matching 'miami,display'
    tables = tree / 'iokit/KernelConfigTables.cpp'
    tbl_text = tables.read_text()
    marker = "'IOProviderClass' = IOPlatformExpertDevice;"
    entry = (
        "   {\n"
        "     'IOClass'         = IOCoreSurfaceRoot;\n"
        "     'IOProviderClass' = IOResources;\n"
        "     'IOMatchCategory' = IOCoreSurfaceRoot;\n"
        "   },\n"
        "   {\n"
        "     'IOClass'         = AppleCLCD;\n"
        "     'IOProviderClass' = IOPlatformDevice;\n"
        "     'IONameMatch'     = 'miami,display';\n"
        "   },\n"
    )
    if 'IOCoreSurfaceRoot' not in tbl_text:
        # insert right before the SweetPlatformExpert or first entry in ARM64_BOARD_CONFIG
        if "'IOClass'         = SweetPlatformExpert;" in tbl_text:
            tbl_text = tbl_text.replace(
                "'IOClass'         = SweetPlatformExpert;",
                entry + "     'IOClass'         = SweetPlatformExpert;"
            )
            tables.write_text(tbl_text)
        elif "'IOClass'         = MiamiPlatformExpert;" in tbl_text:
            tbl_text = tbl_text.replace(
                "'IOClass'         = MiamiPlatformExpert;",
                entry + "     'IOClass'         = MiamiPlatformExpert;"
            )
            tables.write_text(tbl_text)

    # 3. Update SweetPlatformExpert.cpp to create nubs for arm-io children (disp0)
    pe_file = tree / 'iokit/Kernel/arm/SweetPlatformExpert.cpp'
    if not pe_file.exists():
        pe_file = tree / 'iokit/Kernel/arm/MiamiPlatformExpert.cpp'
    pe_text = pe_file.read_text()
    arm_io_hook = (
        '\n\tIORegistryEntry *armio = root->childFromPath("arm-io", gIODTPlane);\n'
        '\tif (armio != NULL) {\n'
        '\t\tcreateNubs(this, IODTFindMatchingEntries(armio, kIODTExclusive, "(\'gic\')"));\n'
        '\t\tarmio->release();\n'
        '\t}\n'
    )
    target_pe_hook = 'createNubs(this, IODTFindMatchingEntries(root, kIODTExclusive, excludeList()));'
    if 'arm-io' not in pe_text and target_pe_hook in pe_text:
        pe_text = pe_text.replace(target_pe_hook, target_pe_hook + arm_io_hook)
        pe_file.write_text(pe_text)

    # 4. Copy source files into iokit/Kernel/arm/
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
    }
