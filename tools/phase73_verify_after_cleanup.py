from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

print('PHASE73_VERIFY_AFTER_CLEANUP')
print(f'PROJECT={BASE_DIR}')

switch_list = BASE_DIR / 'inventory' / 'templates' / 'inventory' / 'switch_list.html'
if switch_list.exists():
    text = switch_list.read_text(encoding='utf-8', errors='replace')
    print(f'REFRESH_VIEW_BUTTON_PRESENT={"YES" if "data-dashboard-manual-refresh" in text else "NO"}')
    print(f'LAST_UPDATE_PRESENT={"YES" if "data-field=\"generated_at\"" in text else "NO"}')
else:
    print('SWITCH_LIST_TEMPLATE=MISSING')

for rel in [
    'scripts/switchmap_service_runner.cmd',
    'scripts/54_dashboard_background_refresh_runner.cmd',
    'scripts/99_sfp_background_monitor_runner.cmd',
    'scripts/41_mikrotik_auto_snmp_poll_runner.cmd',
]:
    print(f'REQUIRED_FILE::{rel}={"OK" if (BASE_DIR / rel).exists() else "MISSING"}')

for rel in [
    'logs/dashboard-background-refresh-status.json',
    'logs/sfp-background-monitor-status.json',
]:
    p = BASE_DIR / rel
    if not p.exists():
        print(f'STATUS_FILE::{rel}=MISSING')
        continue
    print(f'STATUS_FILE::{rel}=OK')
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        print(f'STATUS::{rel}::status={data.get("status", "") }')
        print(f'STATUS::{rel}::summary={data.get("summary", "") }')
        print(f'STATUS::{rel}::completed_at={data.get("completed_at", "") }')
    except Exception as exc:
        print(f'STATUS::{rel}::READ_ERROR={type(exc).__name__}: {exc}')

try:
    import django
    django.setup()
    from inventory.models import Switch, AlarmNotification, SfpMonitorSnapshot
    test_qs = (Switch.objects.filter(name__icontains='Smoke') | Switch.objects.filter(name__startswith='Phase41-') | Switch.objects.filter(management_ip='10.41.2.1')).distinct()
    print(f'TEST_SWITCHES_REMAINING={test_qs.count()}')
    for sw in test_qs.order_by('name'):
        print(f'TEST_SWITCH_REMAINING={sw.id}|{sw.name}|{sw.management_ip}')
    print(f'ACTIVE_SWITCHES={Switch.objects.filter(is_active=True).count()}')
    print(f'ACTIVE_ALARMS={AlarmNotification.objects.filter(status="active").count()}')
    latest = SfpMonitorSnapshot.objects.order_by('-poll_time').first()
    if latest:
        print(f'SFP_LATEST_POLL={latest.poll_time}')
    else:
        print('SFP_LATEST_POLL=NONE')
except Exception as exc:
    print(f'DB_VERIFY_ERROR={type(exc).__name__}: {exc}')

print('PHASE73_VERIFY_AFTER_CLEANUP_DONE')
