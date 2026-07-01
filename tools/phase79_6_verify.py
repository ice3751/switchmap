from __future__ import annotations
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

ok=[]; warn=[]; fail=[]

def add(cond, name, msg=''):
    (ok if cond else fail).append((name, msg))

try:
    subprocess.check_call([sys.executable, 'manage.py', 'check'], cwd=str(ROOT))
    ok.append(('django_check','OK'))
except Exception as e:
    fail.append(('django_check', str(e)))

def txt(rel):
    p=ROOT/rel
    if not p.exists():
        fail.append((f'file:{rel}','missing'))
        return ''
    return p.read_text(encoding='utf-8', errors='ignore')

base=txt('inventory/templates/inventory/base.html')
sl=txt('inventory/templates/inventory/switch_list.html')
sd=txt('inventory/templates/inventory/switch_detail.html')
js=txt('inventory/static/inventory/switchmap.js')
css=txt('inventory/static/inventory/css/switchmap-phase79.css')

add('phase79-6-last-connected-render-reset' in base, 'base:js_version')
add('phase79-lc-card' in sl and 'phase79-last-connected-title' not in sl, 'switch_list:last_connected_block_reset')
add('phase79-lc-card' in sd and 'phase79-last-connected-title' not in sd, 'switch_detail:last_connected_block_reset')
add('PHASE79_6_LAST_CONNECTED_RENDER_RESET' in js, 'js:phase79_6_marker')
add('phase79-lc-row' in js, 'js:phase79_lc_rows')
add('PHASE79_6_LAST_CONNECTED_RENDER_RESET' in css, 'css:phase79_6_marker')

# Static copy check: warn only, because DEBUG/dev may serve app static.
for rel in ['staticfiles/inventory/switchmap.js', 'inventory/staticfiles/inventory/switchmap.js']:
    p=ROOT/rel
    if p.exists():
        st=p.read_text(encoding='utf-8', errors='ignore')
        if 'PHASE79_6_LAST_CONNECTED_RENDER_RESET' in st:
            ok.append((f'static:{rel}','OK'))
        else:
            warn.append((f'static:{rel}','marker not found'))

print('PHASE79_6_LAST_CONNECTED_RENDER_RESET_REPORT')
print(f'OK_COUNT={len(ok)}')
print(f'WARNING_COUNT={len(warn)}')
print(f'FAIL_COUNT={len(fail)}')
print('\n[OK]')
for k,v in ok: print('OK', k, v)
print('\n[WARNING]')
if warn:
    for k,v in warn: print('WARNING', k, v)
else:
    print('- none')
print('\n[FAIL]')
if fail:
    for k,v in fail: print('FAIL', k, v)
    print('PHASE79_6_VERIFY_FAIL')
    raise SystemExit(1)
print('- none')
print('PHASE79_6_VERIFY_OK')
