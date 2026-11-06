#!/usr/bin/env python3
"""Keep actual compiler errors visible after a parallel warning-heavy build."""
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(errors='replace')
lines = re.sub(r'\x1b\[[0-9;]*m', '', text).splitlines()
hits = [i for i, line in enumerate(lines)
        if re.search(r':\d+:\d+: (?:fatal )?error:', line)]
print('Compiler error diagnostics:', len(hits))
for index in hits[-40:]:
    print('\n'.join(lines[max(0, index - 1):index + 5]))
