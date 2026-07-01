from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

ok = []
warn = []
fail = []


def add_ok(item): ok.append(item)
def add_warn(item): warn.append(item)
def add_fail(item): fail.append(item)

try:
    import django
    django.setup()
    add_ok("django_setup")
except Exception as exc:
    add_fail(f"django_setup:{exc}")

if not fail:
    try:
        from django.urls import reverse
        from inventory.models import Port, PortConnectionHistory
        from inventory.views import _port_payload
        reverse("inventory:port_payload_json", args=[1])
        add_ok("url:port_payload_json")
        add_ok("model:PortConnectionHistory")
        port = Port.objects.select_related("switch").first()
        if port:
            payload = _port_payload(port)
            if "last_connection" in payload:
                add_ok("payload:last_connection")
            else:
                add_fail("payload:last_connection_missing")
            add_ok(f"data:port_connection_history:{PortConnectionHistory.objects.count()}")
        else:
            add_warn("data:no_ports")
    except Exception as exc:
        add_fail(f"django_checks:{exc}")

checks = {
    "inventory/templates/inventory/base.html": ["switchmap-phase79.css", "phase79-2-port-history-popup"],
    "inventory/templates/inventory/switch_list.html": ["phase79-last-connected", "data-field=\"last_connection_identity\""],
    "inventory/templates/inventory/switch_detail.html": ["phase79-last-connected", "data-detail=\"last_connection_identity\""],
    "inventory/static/inventory/switchmap.js": ["refreshLastConnectionFromPayload", "last_connection_identity", "storeLastConnectionOnButton"],
    "inventory/static/inventory/css/switchmap-phase79.css": ["phase79-last-connected"],
    "inventory/views.py": ["last_connection", "latest_port_connection", "_phase79_history_payload"],
}
for rel, markers in checks.items():
    path = ROOT / rel
    if not path.exists():
        add_fail(f"file_missing:{rel}")
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [m for m in markers if m not in text]
    if missing:
        add_fail(f"marker_missing:{rel}:{','.join(missing)}")
    else:
        add_ok(f"markers:{rel}")

print("PHASE79_2_PORT_LAST_CONNECTED_UI_REPORT")
print(f"OK_COUNT={len(ok)}")
print(f"WARNING_COUNT={len(warn)}")
print(f"FAIL_COUNT={len(fail)}")
print("\n[OK]")
for item in ok:
    print(f"OK {item}")
print("\n[WARNING]")
if warn:
    for item in warn:
        print(f"WARNING {item}")
else:
    print("- none")
print("\n[FAIL]")
if fail:
    for item in fail:
        print(f"FAIL {item}")
    raise SystemExit(1)
else:
    print("- none")
print("PHASE79_2_VERIFY_OK")
