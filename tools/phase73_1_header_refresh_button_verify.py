from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

print('PHASE73_1_HEADER_REFRESH_BUTTON_VERIFY')
print(f'PROJECT={BASE_DIR}')

paths = [
    BASE_DIR / 'inventory' / 'templates' / 'inventory' / 'switch_list.html',
    BASE_DIR / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-dashboard-stable-main.css',
    BASE_DIR / 'staticfiles' / 'inventory' / 'css' / 'switchmap-dashboard-stable-main.css',
]
for p in paths:
    if not p.exists():
        print(f'CHECK::{p.relative_to(BASE_DIR)}=MISSING')
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    rel = p.relative_to(BASE_DIR)
    print(f'CHECK::{rel}::HAS_REFRESH_VIEW={"YES" if "Refresh View" in text else "NO"}')
    print(f'CHECK::{rel}::HAS_MANUAL_REFRESH_ATTR={"YES" if "data-dashboard-manual-refresh" in text else "NO"}')
    print(f'CHECK::{rel}::HAS_HIDE_RULE={"YES" if "Phase 73.1 hide deprecated manual dashboard refresh button" in text else "NO"}')

for rel in ['logs/dashboard-background-refresh-status.json', 'logs/sfp-background-monitor-status.json']:
    p = BASE_DIR / rel
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding='utf-8', errors='replace'))
            print(f'STATUS::{rel}::{data.get("status")}::{data.get("summary")}')
        except Exception as exc:
            print(f'STATUS::{rel}::READ_ERROR::{type(exc).__name__}: {exc}')
    else:
        print(f'STATUS::{rel}::MISSING')

print('PHASE73_1_HEADER_REFRESH_BUTTON_VERIFY_DONE')
