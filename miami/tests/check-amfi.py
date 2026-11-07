"""Execute the actual staged no-entitlements admission function on the host.

The full kernel build verifies its real Apple ABI; this harness isolates the
policy and checks that unsupported entitlements fail closed.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

source = (Path(sys.argv[1]) / 'bsd/kern/miami_amfi.c').read_text()
start = source.index('static kern_return_t\nmiami_amfi_adjust_without_monitor(')
end = source.index('\n}\n', start) + 3
function = source[start:end]
harness = '''
#include <assert.h>
#include <stddef.h>
#define __unused __attribute__((unused))
typedef int kern_return_t;
enum { KERN_SUCCESS = 0, KERN_DENIED = 53 };
struct cs_blob { void *csb_entitlements, *csb_entitlements_blob,
    *csb_der_entitlements_blob; };
''' + function + '''
int main(void) {
    struct cs_blob b = {0};
    assert(miami_amfi_adjust_without_monitor(NULL, &b) == KERN_SUCCESS);
    assert(miami_amfi_adjust_without_monitor(&b, &b) == KERN_DENIED);
    assert(miami_amfi_adjust_without_monitor(NULL, NULL) == KERN_DENIED);
    b.csb_entitlements = &b;
    assert(miami_amfi_adjust_without_monitor(NULL, &b) == KERN_DENIED);
    b.csb_entitlements = NULL; b.csb_entitlements_blob = &b;
    assert(miami_amfi_adjust_without_monitor(NULL, &b) == KERN_DENIED);
    b.csb_entitlements_blob = NULL; b.csb_der_entitlements_blob = &b;
    assert(miami_amfi_adjust_without_monitor(NULL, &b) == KERN_DENIED);
}
'''
assert 'amfi_interface_register(&miami_amfi);' in source
assert 'STARTUP(EARLY_BOOT, STARTUP_RANK_MIDDLE, miami_amfi_register)' in source
with tempfile.TemporaryDirectory(prefix='miami-amfi-check-') as folder:
    path = Path(folder)
    (path / 'check.c').write_text(harness)
    subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', str(path / 'check.c'),
                    '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True)
print('PASS: actual no-entitlements admission accepts empty context; rejects XML/DER, objects and missing blob')
