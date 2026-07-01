import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(BASE))

fail = 0

def ok(msg):
    print("OK", msg)

def bad(msg):
    global fail
    fail += 1
    print("FAIL", msg)

def contains(path, text):
    return text in (BASE / path).read_text(encoding="utf-8", errors="ignore")

try:
    import django
    django.setup()
except Exception as exc:
    bad(f"django_setup:{exc}")
else:
    from django.test import RequestFactory
    from inventory.models import Port, Switch
    from inventory.views import port_payload_json

    for path, marker in [
        ("inventory/static/inventory/switchmap.js", "PHASE79_6_3_LAST_CONNECTED_CURRENT_OR_HISTORY_FIX"),
        ("inventory/static/inventory/css/switchmap-phase79.css", "PHASE79_6_3_LAST_CONNECTED_CURRENT_OR_HISTORY_FIX"),
        ("inventory/templates/inventory/base.html", "phase79-6-3-current-history-fix"),
    ]:
        if contains(path, marker):
            ok(f"marker:{path}")
        else:
            bad(f"missing_marker:{path}")

    js = (BASE / "inventory/static/inventory/switchmap.js").read_text(encoding="utf-8", errors="ignore")
    if re.search(r"(?<![A-Za-z0-9_$])esc\s*\(", js):
        bad("undefined_esc_call_still_exists")
    else:
        ok("no_undefined_esc_call")

    for tpl in ["inventory/templates/inventory/switch_list.html", "inventory/templates/inventory/switch_detail.html"]:
        txt = (BASE / tpl).read_text(encoding="utf-8", errors="ignore")
        opens = len(re.findall(r"<div\b", txt))
        closes = len(re.findall(r"</div>", txt))
        blocks = txt.count("data-phase79-last-connected")
        if opens == closes and blocks == 1:
            ok(f"template_div_balance:{tpl}:div={opens}:lc_blocks={blocks}")
        else:
            bad(f"template_div_balance:{tpl}:open={opens}:close={closes}:lc_blocks={blocks}")

    try:
        sw = Switch.objects.get(management_ip="172.20.1.12")
        ok(f"switch:{sw.id}:{sw.name}:{sw.management_ip}")
    except Exception as exc:
        sw = None
        bad(f"switch_lookup:{exc}")

    if sw:
        rf = RequestFactory()
        expected = {
            "Ethernet1/1": False,
            "Ethernet1/32": True,
            "Ethernet1/40": True,
        }
        for iface, should_available in expected.items():
            try:
                port = Port.objects.get(switch=sw, interface_name=iface)
                response = port_payload_json(rf.get(f"/port/{port.id}/payload/"), port.id)
                data = json.loads(response.content.decode("utf-8"))
                lc = data["port"].get("last_connection", {})
                available = bool(lc.get("available"))
                ident = lc.get("identity") or ""
                event = lc.get("event_type") or ""
                neighbor = data["port"].get("neighbor_device") or ""
                print(f"PORT {iface} id={port.id} status={data['port'].get('status')} neighbor={neighbor} lc_available={available} lc_event={event} lc_identity={ident}")
                if available == should_available:
                    ok(f"payload_last_connection:{iface}")
                else:
                    bad(f"payload_last_connection:{iface}:expected={should_available}:got={available}")
                if iface in ("Ethernet1/32", "Ethernet1/40") and event != "Current":
                    bad(f"payload_event_not_current:{iface}:{event}")
            except Exception as exc:
                bad(f"payload:{iface}:{exc}")

if fail:
    print(f"PHASE79_6_3_VERIFY_FAIL={fail}")
    raise SystemExit(1)
print("PHASE79_6_3_VERIFY_OK")
