from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

ok = []
fail = []
warn = []

def add_ok(x): ok.append(x)
def add_fail(x): fail.append(x)
def add_warn(x): warn.append(x)

try:
    import django
    django.setup()
    from django.core.management import call_command
    call_command("check")
    add_ok("django_check")
except Exception as exc:
    add_fail(f"django_setup:{exc}")

if not fail:
    try:
        from inventory.phase79_history import history_has_identity_data, latest_port_connection, port_has_identity_data
        add_ok("import:history_has_identity_data")
        add_ok("import:latest_port_connection")
        add_ok("import:port_has_identity_data")
    except Exception as exc:
        add_fail(f"history_import:{exc}")

if not fail:
    try:
        from inventory.models import Port
        sample = Port.objects.order_by("id").first()
        if sample:
            latest_port_connection(sample)
            add_ok("latest_port_connection:callable")
        else:
            add_warn("data:no_ports")
    except Exception as exc:
        add_fail(f"latest_port_connection_call:{exc}")

print("PHASE79_2_6_HISTORY_IMPORT_FIX_REPORT")
print(f"OK_COUNT={len(ok)}")
print(f"WARNING_COUNT={len(warn)}")
print(f"FAIL_COUNT={len(fail)}")
print("\n[OK]")
for x in ok:
    print("OK", x)
print("\n[WARNING]")
if warn:
    for x in warn:
        print("WARNING", x)
else:
    print("- none")
print("\n[FAIL]")
if fail:
    for x in fail:
        print("FAIL", x)
    print("PHASE79_2_6_VERIFY_FAIL")
    raise SystemExit(1)
print("- none")
print("PHASE79_2_6_VERIFY_OK")
