from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

ok = []
warn = []
fail = []

def add_ok(x): ok.append('OK ' + x)
def add_warn(x): warn.append('WARNING ' + x)
def add_fail(x): fail.append('FAIL ' + x)

def reverse_url(name: str):
    from django.urls import reverse
    if name == 'port_payload_json':
        return reverse(f'inventory:{name}', kwargs={'port_id': 1})
    return reverse(f'inventory:{name}')

try:
    import django
    from django.core.management import call_command
    django.setup()
    call_command('check')
    add_ok('django_check')
    for name in ['switch_list', 'port_payload_json']:
        try:
            reverse_url(name)
            add_ok(f'url:{name}')
        except Exception as exc:
            add_fail(f'url:{name}:{exc}')
except Exception as exc:
    add_fail(f'django_setup:{exc}')

css = ROOT / 'inventory/static/inventory/css/switchmap-phase79.css'
base = ROOT / 'inventory/templates/inventory/base.html'
if css.exists():
    text = css.read_text(encoding='utf-8', errors='ignore')
    markers = [
        'Phase79.2.1',
        '.phase79-last-connected .key-item:first-child',
        'white-space: nowrap',
        'text-overflow: ellipsis',
    ]
    missing = [m for m in markers if m not in text]
    if missing:
        add_fail('css:missing_markers:' + ','.join(missing))
    else:
        add_ok('css:phase79_last_connected_layout')
else:
    add_fail('css:switchmap-phase79.css missing')

if base.exists():
    text = base.read_text(encoding='utf-8', errors='ignore')
    if 'switchmap-phase79.css' in text and 'phase79-2-1-last-connected-layout-fix' in text:
        add_ok('base:phase79_css_version')
    else:
        add_fail('base:phase79_css_version_missing')
else:
    add_fail('base.html missing')

print('PHASE79_2_2_VERIFY_NAMESPACE_FIX_REPORT')
print(f'OK_COUNT={len(ok)}')
print(f'WARNING_COUNT={len(warn)}')
print(f'FAIL_COUNT={len(fail)}')
print('\n[OK]')
print('\n'.join(ok) if ok else '- none')
print('\n[WARNING]')
print('\n'.join(warn) if warn else '- none')
print('\n[FAIL]')
print('\n'.join(fail) if fail else '- none')
if fail:
    print('PHASE79_2_2_VERIFY_FAIL')
    raise SystemExit(1)
print('PHASE79_2_2_VERIFY_OK')
