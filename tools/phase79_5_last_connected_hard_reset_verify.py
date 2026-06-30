from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

ok=[]; warn=[]; fail=[]
def add_ok(x): ok.append('OK '+x)
def add_warn(x): warn.append('WARNING '+x)
def add_fail(x): fail.append('FAIL '+x)

try:
    import django
    django.setup()
    from django.core.management import call_command
    from django.urls import reverse
    call_command('check', verbosity=0)
    add_ok('django_check')
    reverse('inventory:switch_list'); add_ok('url:switch_list')
    reverse('inventory:port_payload_json', args=[1]); add_ok('url:port_payload_json')
except Exception as e:
    add_fail('django_setup:'+str(e))

files = {
    'base': ROOT/'inventory/templates/inventory/base.html',
    'js': ROOT/'inventory/static/inventory/switchmap.js',
    'css': ROOT/'inventory/static/inventory/css/switchmap-phase79.css',
    'switch_list': ROOT/'inventory/templates/inventory/switch_list.html',
    'switch_detail': ROOT/'inventory/templates/inventory/switch_detail.html',
}
for name,path in files.items():
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
        if name == 'base':
            if 'switchmap.js' in text and 'phase79-5-last-connected-hard-reset' in text: add_ok('base:js_css_cache_bust')
            else: add_fail('base:cache_bust_missing')
        elif name == 'js':
            for m in ('Phase79.5 - hard reset renderer','effectiveLastConnectionFromDataset(button.dataset)','Phase79.5 - current visible port evidence first'):
                if m in text: add_ok('js_marker:'+m)
                else: add_fail('js_marker_missing:'+m)
        elif name == 'css':
            if 'Phase79.5 - hard reset Last Connected Device UI' in text and '[data-phase79-last-connected]::before' in text:
                add_ok('css:hard_reset')
            else: add_fail('css:hard_reset_missing')
        else:
            if 'phase79-last-connected-panel' in text and 'last_connection_identity' not in text and 'key-item' not in text[text.find('data-phase79-last-connected')-300:text.find('data-phase79-last-connected')+800]:
                add_ok('template:'+name+':clean_container')
            else:
                add_fail('template:'+name+':legacy_last_connected_container_present')
    except Exception as e:
        add_fail('file:'+name+':'+str(e))

staticfiles = ROOT/'staticfiles/inventory/switchmap.js'
if staticfiles.exists():
    t = staticfiles.read_text(encoding='utf-8', errors='ignore')
    if 'Phase79.5 - hard reset renderer' in t: add_ok('staticfiles:switchmap_js_updated')
    else: add_warn('staticfiles:switchmap_js_marker_missing_run_collectstatic')
else:
    add_warn('staticfiles:switchmap_js_not_found')

print('PHASE79_5_LAST_CONNECTED_HARD_RESET_REPORT')
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
    print('PHASE79_5_VERIFY_FAIL')
    sys.exit(1)
print('PHASE79_5_VERIFY_OK')
