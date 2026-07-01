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

try:
    import django
    from django.core.management import call_command
    django.setup()
    call_command('check')
    add_ok('django_check')

    from inventory.models import Port
    from inventory.views import _phase79_history_payload
    try:
        from inventory.phase79_history import latest_port_connection
    except Exception as exc:
        latest_port_connection = None
        add_fail(f'import:latest_port_connection:{exc}')

    class EmptyHistory:
        connected_device = ''
        neighbor_device = ''
        neighbor_port = ''
        neighbor_ip = None
        ip_address = None
        mac_address = ''
        mac_addresses = ''
        device_type = ''
        owner = ''
        access_vlan = '1'
        vlan = '1'
        status_after = 'down'
        source = 'poll'
        neighbor_source = ''
        observed_at = None
        last_verified_at = None
        event_type = 'snapshot'

    empty_payload = _phase79_history_payload(EmptyHistory())
    if empty_payload.get('available') is False and empty_payload.get('observed_at_text') == '-':
        add_ok('payload:empty_history_hidden')
    else:
        add_fail(f'payload:empty_history_visible:{empty_payload}')

    targets = [
        ('NEXUS', 'Ethernet1/29'),
        ('NEXUS', 'Ethernet1/38'),
    ]
    for sw_name, iface in targets:
        port = Port.objects.select_related('switch').filter(switch__name__iexact=sw_name, interface_name__iexact=iface).first()
        if not port:
            add_warn(f'target:{sw_name} {iface}:not_found')
            continue
        hist = latest_port_connection(port) if latest_port_connection else None
        payload = _phase79_history_payload(hist)
        add_ok(f'target:{sw_name} {iface}:status:{port.status}')
        add_ok(f'target:{sw_name} {iface}:payload_available:{1 if payload.get("available") else 0}')
        add_ok(f'target:{sw_name} {iface}:identity:{payload.get("identity", "-")}')
        if not any([port.connected_device, port.neighbor_device, port.neighbor_port, port.mac_address, port.mac_addresses, port.ip_address]):
            if payload.get('available'):
                add_fail(f'target:{sw_name} {iface}:empty_current_port_but_payload_visible')
            else:
                add_ok(f'target:{sw_name} {iface}:empty_current_port_hidden')

except Exception as exc:
    add_fail(f'django_setup:{exc}')

checks = [
    (ROOT / 'inventory/views.py', ['observed_at / VLAN / status are not identity evidence', '"available": False', 'def _phase79_history_payload(history):']),
    (ROOT / 'inventory/static/inventory/switchmap.js', ['function meaningfulHistoryValue(value)', 'function hasMeaningfulLastConnection(last)', 'const available = hasMeaningfulLastConnection(last);']),
    (ROOT / 'inventory/static/inventory/css/switchmap-phase79.css', ['Phase79.2.4 - truth guard', "content: 'سابقه اتصال واقعی برای این پورت ثبت نشده است.'"]),
    (ROOT / 'inventory/templates/inventory/base.html', ['switchmap-phase79.css', 'phase79-2-4-last-connected-truth-guard']),
]
for path, markers in checks:
    if not path.exists():
        add_fail(f'file_missing:{path.relative_to(ROOT)}')
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    missing = [m for m in markers if m not in text]
    if missing:
        add_fail(f'markers:{path.relative_to(ROOT)} missing={missing}')
    else:
        add_ok(f'markers:{path.relative_to(ROOT)}')

print('PHASE79_2_4_LAST_CONNECTED_TRUTH_GUARD_REPORT')
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
    print('PHASE79_2_4_VERIFY_FAIL')
    raise SystemExit(1)
print('PHASE79_2_4_VERIFY_OK')
