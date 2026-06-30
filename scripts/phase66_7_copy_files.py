import shutil
import sys
from pathlib import Path

if len(sys.argv) != 4:
    print('PHASE66_7_COPY_FAIL_BAD_ARGS')
    sys.exit(1)

root = Path(sys.argv[1])
src = Path(sys.argv[2])
backup = Path(sys.argv[3])
files = [
    'inventory/templates/inventory/base.html',
    'inventory/templates/inventory/switch_list.html',
    'inventory/static/inventory/css/switchmap-phase42.css',
    'inventory/static/inventory/switchmap.js',
    'smoke_tests/switchmap_66_7_hard_visual_reset_smoke_test.py',
    'smoke_tests/manifest.json',
    'docs/PHASE66_7_HARD_VISUAL_RESET.md',
]
try:
    backup.mkdir(parents=True, exist_ok=True)
    for rel in files:
        s = src / rel
        d = root / rel
        if not s.exists():
            print(f'PHASE66_7_COPY_FAIL_SOURCE_MISSING={rel}')
            sys.exit(1)
        if d.exists():
            b = backup / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(d, b)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        print(f'PHASE66_7_COPIED={rel}')
    print('PHASE66_7_COPY_OK')
except Exception as exc:
    print('PHASE66_7_COPY_FAIL=' + str(exc))
    sys.exit(1)
