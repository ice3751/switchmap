from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.core.management import call_command
from django.db import connection

ok = []
warn = []
fail = []

try:
    django.setup()
    call_command("check", verbosity=0)
    ok.append("django_check: OK")
except Exception as exc:
    fail.append(f"django_setup: {exc}")

if not fail:
    try:
        from inventory.models import Port, PortConnectionHistory
        from inventory.phase79_history import latest_port_connection, record_port_identity_snapshot
        ok.append("model:PortConnectionHistory: OK")
        ok.append("helper:phase79_history: OK")

        tables = set(connection.introspection.table_names())
        if "inventory_portconnectionhistory" in tables:
            ok.append("table:inventory_portconnectionhistory: OK")
        else:
            fail.append("table:inventory_portconnectionhistory missing; run migrate")

        port_count = Port.objects.count()
        history_count = PortConnectionHistory.objects.count() if "inventory_portconnectionhistory" in tables else 0
        identity_ports = Port.objects.exclude(neighbor_device="").count() + Port.objects.exclude(mac_addresses="").count() + Port.objects.exclude(mac_address="").count() + Port.objects.exclude(connected_device="").count()
        ok.append(f"data:ports:{port_count}")
        ok.append(f"data:connection_history_rows:{history_count}")
        if history_count == 0:
            warn.append("phase79:connection_history_empty: no last-device data captured yet")
        if identity_ports == 0:
            warn.append("phase79:current_identity_source_empty: no current neighbor/mac/device data in Port table")
    except Exception as exc:
        fail.append(f"phase79_1_checks: {exc}")

print("PHASE79_1_PORT_HISTORY_REPORT")
print(f"OK_COUNT={len(ok)}")
print(f"WARNING_COUNT={len(warn)}")
print(f"FAIL_COUNT={len(fail)}")
print("\n[OK]")
for item in ok:
    print("OK " + item)
print("\n[WARNING]")
for item in warn:
    print("WARNING " + item)
if not warn:
    print("- none")
print("\n[FAIL]")
for item in fail:
    print("FAIL " + item)
if not fail:
    print("- none")
print("PHASE79_1_VERIFY_" + ("OK" if not fail else "FAIL"))
sys.exit(0 if not fail else 1)
