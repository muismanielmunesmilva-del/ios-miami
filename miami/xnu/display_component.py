"""Stage XNU native display pipeline (IOCoreSurfaceRoot + AppleCLCD / IOMobileFramebuffer) for MIAMI."""
import hashlib
from pathlib import Path

def stage(tree, edit_func=None):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Update iokit/conf/files.arm64
    files_arm64 = tree / 'iokit/conf/files.arm64'
    files_content = files_arm64.read_text()
    if 'MiamiSurface.cpp' not in files_content:
        files_content += (
            "iokit/Kernel/arm/MiamiSurface.cpp                                optional iokitcpp\n"
            "iokit/Kernel/arm/MiamiFramebuffer.cpp                            optional iokitcpp\n"
        )
        files_arm64.write_text(files_content)

    # 2. Update iokit/KernelConfigTables.cpp
    kct = tree / 'iokit/KernelConfigTables.cpp'
    kct_content = kct.read_text()
    if 'IOCoreSurfaceRoot' not in kct_content:
        display_tables = (
            "    \"   {\\n\"\n"
            "    \"     'IOClass'         = IOCoreSurfaceRoot;\\n\"\n"
            "    \"     'IOProviderClass' = IOResources;\\n\"\n"
            "    \"     'IOMatchCategory' = IOCoreSurfaceRoot;\\n\"\n"
            "    \"   },\\n\"\n"
            "    \"   {\\n\"\n"
            "    \"     'IOClass'         = AppleCLCD;\\n\"\n"
            "    \"     'IOProviderClass' = IOPlatformDevice;\\n\"\n"
            "    \"     'IONameMatch'     = 'miami,display';\\n\"\n"
            "    \"   },\\n\"\n"
            "#endif\n"
        )
        if '#endif\n     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;' in kct_content:
            kct_content = kct_content.replace(
                '#endif\n     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;',
                display_tables + '     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;'
            )
            kct.write_text(kct_content)
        elif '#endif\n' in kct_content and "IOPanicPlatform" in kct_content:
            # Fallback to replacing #endif before IOPanicPlatform
            idx = kct_content.index('IOPanicPlatform')
            endif_idx = kct_content.rindex('#endif\n', 0, idx)
            kct_content = kct_content[:endif_idx] + display_tables + kct_content[endif_idx + len('#endif\n'):]
            kct.write_text(kct_content)
        else:
            raise ValueError("Could not find insertion point before IOPanicPlatform in KernelConfigTables.cpp")

    # 3. Update iokit/Kernel/arm/SweetPlatformExpert.cpp
    spe = tree / 'iokit/Kernel/arm/SweetPlatformExpert.cpp'
    spe_content = spe.read_text()
    if 'arm-io' not in spe_content:
        hook = (
            "\tIORegistryEntry *armio = root->childFromPath(\"arm-io\", gIODTPlane);\n"
            "\tif (armio != NULL) {\n"
            "\t\tcreateNubs(this, IODTFindMatchingEntries(armio, kIODTExclusive, \"('gic')\"));\n"
            "\t\tarmio->release();\n"
            "\t}\n"
        )
        target_marker = "createNubs(this, IODTFindMatchingEntries(root, kIODTExclusive, excludeList()));\n"
        if target_marker in spe_content:
            spe_content = spe_content.replace(target_marker, target_marker + "\n" + hook)
            spe.write_text(spe_content)
        else:
            raise ValueError("Could not find processTopLevel insertion point in SweetPlatformExpert.cpp")

    # 4. Copy clean source files into iokit/Kernel/arm/
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
