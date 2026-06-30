from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_DIR = BASE_DIR / 'backups' / f'phase73_1_header_refresh_button_finalize_{STAMP}'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

print('PHASE73_1_HEADER_REFRESH_BUTTON_FINALIZE')
print(f'PROJECT={BASE_DIR}')
print(f'BACKUP={BACKUP_DIR}')

# Files that may contain the dashboard header button.
template_root = BASE_DIR / 'inventory' / 'templates'
css_file = BASE_DIR / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-dashboard-stable-main.css'

refresh_terms = [
    'Refresh View',
    'data-dashboard-manual-refresh',
    'sm-main-refresh-btn',
]

changed_templates = []
found_templates = []

# Conservative button/a removal. Keep surrounding header and last update text.
patterns = [
    re.compile(r'\n?\s*<button\b(?=[^>]*(?:data-dashboard-manual-refresh|sm-main-refresh-btn))[^>]*>.*?</button>\s*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\n?\s*<a\b(?=[^>]*(?:data-dashboard-manual-refresh|sm-main-refresh-btn))[^>]*>.*?</a>\s*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\n?\s*<button\b[^>]*>\s*.*?Refresh\s+View.*?</button>\s*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\n?\s*<a\b[^>]*>\s*.*?Refresh\s+View.*?</a>\s*', re.IGNORECASE | re.DOTALL),
]

if template_root.exists():
    for p in template_root.rglob('*.html'):
        text = p.read_text(encoding='utf-8', errors='replace')
        if any(term in text for term in refresh_terms):
            found_templates.append(p)
            rel = p.relative_to(BASE_DIR)
            dest = BACKUP_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            new = text
            total_removed = 0
            for pat in patterns:
                new, n = pat.subn('', new)
                total_removed += n
            if new != text:
                p.write_text(new, encoding='utf-8', newline='')
                changed_templates.append((p, total_removed))
                print(f'TEMPLATE_REFRESH_BUTTON_REMOVED={rel} count={total_removed}')
            else:
                print(f'TEMPLATE_REFRESH_BUTTON_FOUND_BUT_NOT_REMOVED={rel}')
else:
    print('TEMPLATE_ROOT_MISSING')

if not found_templates:
    print('TEMPLATE_REFRESH_BUTTON_FOUND=NO')

# CSS fallback: hide any leftover manual refresh button without touching last-update text.
if css_file.exists():
    rel = css_file.relative_to(BASE_DIR)
    dest = BACKUP_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(css_file, dest)
    css = css_file.read_text(encoding='utf-8', errors='replace')
    marker = '/* Phase 73.1 hide deprecated manual dashboard refresh button */'
    block = '''\n\n/* Phase 73.1 hide deprecated manual dashboard refresh button */\n.sm-main-refresh-btn,\n[data-dashboard-manual-refresh] {\n    display: none !important;\n}\n'''
    if marker not in css:
        css_file.write_text(css.rstrip() + block, encoding='utf-8', newline='')
        print(f'CSS_HIDE_REFRESH_BUTTON_ADDED={rel}')
    else:
        print(f'CSS_HIDE_REFRESH_BUTTON_EXISTS={rel}')
else:
    print('CSS_FILE_MISSING')

# Django checks and collectstatic sync for WhiteNoise/staticfiles.
try:
    import django
    django.setup()
    print('DJANGO_SETUP=OK')
except Exception as exc:
    print(f'DJANGO_SETUP=FAIL::{type(exc).__name__}: {exc}')

python_exe = BASE_DIR / 'venv' / 'Scripts' / 'python.exe'
if not python_exe.exists():
    python_exe = Path(sys.executable)

commands = [
    [str(python_exe), 'manage.py', 'check'],
    [str(python_exe), 'manage.py', 'collectstatic', '--noinput', '-v', '0'],
]
for cmd in commands:
    print('RUN=' + ' '.join(cmd))
    cp = subprocess.run(cmd, cwd=str(BASE_DIR), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = cp.stdout.strip()
    if out:
        print(out)
    print(f'RETURN_CODE={cp.returncode}')
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)

print('PHASE73_1_HEADER_REFRESH_BUTTON_FINALIZE_DONE')
