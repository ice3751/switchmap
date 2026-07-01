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
    from django.urls import reverse
    django.setup()
    call_command('check')
    add_ok('django_check')

    for name, args in [('inventory:switch_list', []), ('inventory:port_payload_json', [1])]:
        try:
            reverse(name, args=args)
            add_ok('url:' + name)
        except Exception as exc:
            add_fail(f'url:{name}:{exc}')

    from inventory.models import Port, PortConnectionHistory
    from inventory.phase79_history import latest_port_connection, history_has_identity_data, meaningful_identity_q
    from inventory.views import _phase79_history_payload

    total_history = PortConnectionHistory.objects.count()
    meaningful_history = PortConnectionHistory.objects.filter(meaningful_identity_q()).count()
    visible_down = 0
    down_ports = Port.objects.select_related('switch').filter(status__iexact='down')[:2000]
    for port in down_ports:
        if latest_port_connection(port):
            visible_down += 1
    add_ok(f'data:history_rows:{total_history}')
    add_ok(f'data:meaningful_history_rows:{meaningful_history}')
    add_ok(f'data:down_ports_with_visible_last_connected:{visible_down}')

    empty_like = PortConnectionHistory.objects.exclude(meaningful_identity_q()).order_by('-observed_at', '-id').first()
    if empty_like:
        payload = _phase79_history_payload(empty_like)
        if payload.get('available') is False:
            add_ok('data:empty_history_hidden')
        else:
            add_fail('data:empty_history_not_hidden')
    else:
        add_ok('data:no_empty_history_rows')

    target = Port.objects.select_related('switch').filter(switch__name__iexact='NEXUS', interface_name__iexact='Ethernet1/38').first()
    if target:
        hist = latest_port_connection(target)
        payload = _phase79_history_payload(hist) if hist else _phase79_history_payload(None)
        add_ok(f'target:NEXUS Ethernet1/38 current_status:{target.status}')
        add_ok(f'target:NEXUS Ethernet1/38 current_neighbor:{target.neighbor_device or "-"}')
        add_ok(f'target:NEXUS Ethernet1/38 current_mac:{target.mac_address or (target.mac_addresses.splitlines()[0].strip() if target.mac_addresses else "-")}')
        add_ok(f'target:NEXUS Ethernet1/38 visible_available:{1 if payload.get("available") else 0}')
        add_ok(f'target:NEXUS Ethernet1/38 visible_identity:{payload.get("identity", "-")}')
        if not payload.get('available'):
            add_warn('target:NEXUS Ethernet1/38 has no meaningful last-connected identity yet')
    else:
        add_warn('target:NEXUS Ethernet1/38 not found')

except Exception as exc:
    add_fail(f'django_setup:{exc}')

checks = [
    (ROOT / 'inventory/static/inventory/css/switchmap-phase79.css', ['Phase79.2.3', '.phase79-lc-row', 'background: #ffffff']),
    (ROOT / 'inventory/templates/inventory/switch_list.html', ['phase79-lc-list', 'data-field="last_connection_identity"']),
    (ROOT / 'inventory/templates/inventory/switch_detail.html', ['phase79-lc-list', 'data-detail="last_connection_identity"']),
    (ROOT / 'inventory/phase79_history.py', ['meaningful_identity_q', 'history_has_identity_data', '.filter(meaningful_identity_q())']),
    (ROOT / 'inventory/views.py', ['history_has_identity_data', 'سابقه‌ای ثبت نشده']),
    (ROOT / 'inventory/templates/inventory/base.html', ['switchmap-phase79.css', 'phase79-2-3-last-connected-safe-ui']),
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

print('PHASE79_2_3_SAFE_UI_VERIFY_REPORT')
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
    print('PHASE79_2_3_VERIFY_FAIL')
    raise SystemExit(1)
print('PHASE79_2_3_VERIFY_OK')
