"""Verify the local iPhone X iOS 16.7.6 manifest and three DMGs read-only.

Usage: python inspect_ipsw_1676.py PATH_TO_EXTRACTED_IPSW
This does not mount images, write to a device, or change the IPSW directory.
"""
import hashlib
import json
from pathlib import Path
import plistlib
import sys


MANIFEST_SHA256 = "fecad6a1edd2e7c6b4bc3256dc373784f7c45506b9edbdb0ba7ebccb1b8bb44f"
COMPONENTS = ("OS", "Cryptex1,SystemOS", "Cryptex1,AppOS")


def main(root):
    root = Path(root)
    raw = (root / "BuildManifest.plist").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Unexpected manifest SHA-256")
    manifest = plistlib.loads(raw)
    if (manifest.get("ProductVersion"), manifest.get("ProductBuildVersion")) != ("16.7.6", "20H320"):
        raise ValueError("Unexpected iOS version/build")
    identities = [item for item in manifest["BuildIdentities"]
                  if item.get("Info", {}).get("DeviceClass") == "d22ap"
                  and item.get("Info", {}).get("RestoreBehavior") == "Update"]
    if len(identities) != 1:
        raise ValueError("Expected one iPhone X update identity")
    images = {}
    for name in COMPONENTS:
        entry = identities[0]["Manifest"][name]
        info = entry["Info"]
        filename = info["Path"]
        if not isinstance(filename, str) or "/" in filename or "\\" in filename or not filename.endswith(".dmg"):
            raise ValueError(f"Unexpected image path for {name}")
        if info.get("HashMethod") != "sha2-384" or len(entry.get("Digest", b"")) != 48:
            raise ValueError(f"Unexpected digest for {name}")
        path = root / filename
        digest = hashlib.sha384()
        with path.open("rb") as image:
            for block in iter(lambda: image.read(8 * 1024 * 1024), b""):
                digest.update(block)
        if digest.digest() != entry["Digest"]:
            raise ValueError(f"Digest mismatch for {name}: {filename}")
        images[name] = {"filename": filename, "size": path.stat().st_size,
                        "sha384": digest.hexdigest(), "manifest_match": True}
    print(json.dumps({"product_version": "16.7.6", "build": "20H320",
                      "device_class": "d22ap", "manifest_sha256": MANIFEST_SHA256,
                      "images": images, "device_write": False}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python inspect_ipsw_1676.py PATH_TO_EXTRACTED_IPSW")
    main(sys.argv[1])
