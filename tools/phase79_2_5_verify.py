
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
ok=[]; warn=[]; fail=[]
def add_ok(s): ok.append(s)
def add_warn(s): warn.append(s)
def add_fail(s): fail.append(s)
try:
    import django
    django.setup()
    from django.core.management import call_command
    from django.urls import reverse
    from inventory.models import Port
    from inventory.views import _phase79_effective_last_connection_payload
    from inventory.phase79_history import port_has_identity_data
    call_command('check')
    add_ok('django_check')
    for name in ['inventory:switch_list', 'inventory:port_payload_json']:
        try:
            reverse(name, args=[1]) if name.endswith('port_payload_json') else reverse(name)
            add_ok(f'url:{name}')
        except Exception as exc:
            add_fail(f'url:{name}:{exc}')
    sample = Port.objects.filter(status='up').exclude(neighbor_device='').first() or Port.objects.filter(status='up').exclude(mac_addresses='').first() or Port.objects.filter(status='up').exclude(mac_address='').first()
    if sample:
        payload = _phase79_effective_last_connection_payload(sample)
        if payload.get('available') and payload.get('identity') not in ('', '-', 'سابقه‌ای ثبت نشده'):
            add_ok(f'connected_port_payload:{sample.switch.name}:{sample.interface_name}:{payload.get("identity")}')
        else:
            add_fail(f'connected_port_payload_empty:{sample.switch.name}:{sample.interface_name}')
    else:
        add_warn('connected_port_payload:no_up_identity_sample')
    no_identity = Port.objects.filter(connected_device='', neighbor_device='', neighbor_port='', mac_address='', mac_addresses='', ip_address__isnull=True, neighbor_ip__isnull=True).first()
    if no_identity:
        if port_has_identity_data(no_identity):
            add_fail(f'empty_port_identity_detected:{no_identity.switch.name}:{no_identity.interface_name}')
        else:
            payload = _phase79_effective_last_connection_payload(no_identity)
            if payload.get('available'):
                add_fail(f'empty_port_payload_available:{no_identity.switch.name}:{no_identity.interface_name}')
            else:
                add_ok(f'empty_port_payload_hidden:{no_identity.switch.name}:{no_identity.interface_name}')
    else:
        add_warn('empty_port_identity:no_sample')
    files = [
        ('views', ROOT/'inventory/views.py', 'def _phase79_effective_last_connection_payload'),
        ('history', ROOT/'inventory/phase79_history.py', 'Phase79.2.5'),
        ('js', ROOT/'inventory/static/inventory/switchmap.js', 'phase79-lc-clean-row'),
        ('css', ROOT/'inventory/static/inventory/css/switchmap-phase79.css', 'Phase79.2.5 - strict'),
        ('base', ROOT/'inventory/templates/inventory/base.html', 'phase79-2-5-last-connected-current-port-fix'),
    ]
    for label, path, marker in files:
        text = path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''
        add_ok(f'marker:{label}') if marker in text else add_fail(f'marker:{label}:missing')
except Exception as exc:
    add_fail(f'django_setup:{exc}')
print('PHASE79_2_5_LAST_CONNECTED_CURRENT_FIX_REPORT')
print(f'OK_COUNT={len(ok)}')
print(f'WARNING_COUNT={len(warn)}')
print(f'FAIL_COUNT={len(fail)}')
print('\n[OK]')
for item in ok: print('OK ' + item)
print('\n[WARNING]')
if warn:
    for item in warn: print('WARNING ' + item)
else:
    print('- none')
print('\n[FAIL]')
if fail:
    for item in fail: print('FAIL ' + item)
else:
    print('- none')
if fail:
    print('PHASE79_2_5_VERIFY_FAIL')
    sys.exit(1)
print('PHASE79_2_5_VERIFY_OK')
