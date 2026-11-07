"""Inspect the pinned iOS IPSW manifest without unpacking or writing a device."""
import hashlib
import json
from pathlib import Path
import plistlib
import sys

p = Path(sys.argv[1])
raw = p.read_bytes()
if hashlib.sha256(raw).hexdigest() != '2d1452103a2f5ad71cb78d94454977fc70632472201980a468c247fba14b10b7':
    raise ValueError('Manifest does not match the pinned Apple IPSW')
manifest = plistlib.loads(raw)
if (manifest.get('ProductVersion'), manifest.get('ProductBuildVersion')) != ('16.7.16', '20H392'):
    raise ValueError('Unexpected iOS version/build')
matches = [i for i in manifest['BuildIdentities']
           if i.get('Info', {}).get('DeviceClass') == 'd22ap'
           and i.get('Info', {}).get('RestoreBehavior') == 'Update']
if len(matches) != 1:
    raise ValueError('Expected exactly one d22ap update identity')
required = ('OS', 'Cryptex1,SystemOS', 'Cryptex1,AppOS')
images = {}
for key in required:
    entry = matches[0]['Manifest'][key]
    name = entry['Info']['Path']
    if not isinstance(name, str) or '/' in name or '\\' in name or not name.endswith('.dmg'):
        raise ValueError('Unexpected image path')
    images[key] = name
print(json.dumps({'product_version':manifest['ProductVersion'],
                  'build':manifest['ProductBuildVersion'], 'device_class':'d22ap',
                  'manifest_sha256':hashlib.sha256(raw).hexdigest(),
                  'images':images, 'device_write':False}, indent=2))
