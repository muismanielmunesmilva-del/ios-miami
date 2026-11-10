"""Stage XNU native HID and Touchscreen subsystem (IOHIDEvent + IOHIDEventServiceUserClient) for MIAMI."""
import hashlib
from pathlib import Path
import shutil

def stage(tree, edit_func=None):
    patch_dir = tree.parent / 'miami-required-patches'
    patch_dir.mkdir(exist_ok=True)

    # 1. Update iokit/conf/files.arm64
    files_arm64 = tree / 'iokit/conf/files.arm64'
    files_content = files_arm64.read_text()
    if 'MiamiHID.cpp' not in files_content:
        files_content += (
            "iokit/Kernel/arm/hid/MiamiHID.cpp                                optional iokitcpp\n"
            "iokit/Kernel/arm/hid/IOHIDEvent.cpp                              optional iokitcpp\n"
            "iokit/Kernel/arm/hid/IOHIDEventServiceQueue.cpp                  optional iokitcpp\n"
            "iokit/Kernel/arm/hid/IOHIDEventServiceUserClient.cpp             optional iokitcpp\n"
        )
        files_arm64.write_text(files_content)

    # 2. Update iokit/KernelConfigTables.cpp
    kct = tree / 'iokit/KernelConfigTables.cpp'
    kct_content = kct.read_text()
    if 'MiamiHIDTouch' not in kct_content:
        hid_tables = (
            "    \"   {\\n\"\n"
            "    \"     'IOClass'         = MiamiHIDButtons;\\n\"\n"
            "    \"     'IOProviderClass' = IOResources;\\n\"\n"
            "    \"     'IOMatchCategory' = MiamiHIDButtons;\\n\"\n"
            "    \"   },\\n\"\n"
            "    \"   {\\n\"\n"
            "    \"     'IOClass'         = MiamiHIDTouch;\\n\"\n"
            "    \"     'IOProviderClass' = IOResources;\\n\"\n"
            "    \"     'IOMatchCategory' = MiamiHIDTouch;\\n\"\n"
            "    \"   },\\n\"\n"
            "#endif\n"
        )
        if '#endif\n     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;' in kct_content:
            kct_content = kct_content.replace(
                '#endif\n     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;',
                hid_tables + '     "   {"\n     "     \'IOClass\'         = IOPanicPlatform;'
            )
            kct.write_text(kct_content)
        elif '#endif\n' in kct_content and "IOPanicPlatform" in kct_content:
            idx = kct_content.index('IOPanicPlatform')
            endif_idx = kct_content.rindex('#endif\n', 0, idx)
            kct_content = kct_content[:endif_idx] + hid_tables + kct_content[endif_idx + len('#endif\n'):]
            kct.write_text(kct_content)
        else:
            raise ValueError("Could not find insertion point before IOPanicPlatform in KernelConfigTables.cpp")

    # 3. Copy clean HID headers and sources into iokit/Kernel/arm/hid/
    src_dir = Path(__file__).resolve().parent / 'hid'
    dest_dir = tree / 'iokit/Kernel/arm/hid'
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = {}
    for p in src_dir.glob('*'):
        if p.is_file():
            content = p.read_bytes()
            (dest_dir / p.name).write_bytes(content)
            copied[p.name] = hashlib.sha256(content).hexdigest()

    return {
        'component': 'IOHIDEvent + IOHIDEventServiceUserClient (MiamiHIDButtons, MiamiHIDTouch)',
        'files_count': len(copied),
        'miami_hid_cpp': copied.get('MiamiHID.cpp')
    }
