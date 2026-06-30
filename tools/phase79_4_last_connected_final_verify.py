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

def add_ok(x): ok.append("OK " + x)
def add_warn(x): warn.append("WARNING " + x)
def add_fail(x): fail.append("FAIL " + x)

try:
    import django
    django.setup()
    from django.core.management import call_command
    from django.urls import reverse
    call_command("check", verbosity=0)
    add_ok("django_check")
    for name in ("inventory:switch_list", "inventory:port_payload_json"):
        try:
            if name.endswith("port_payload_json"):
                reverse(name, args=[1])
            else:
                reverse(name)
            add_ok("url:" + name)
        except Exception as e:
            add_fail("url:" + name + ":" + str(e))
    from inventory.models import Port
    qs = Port.objects.select_related("switch").all()
    sample_up_identity = qs.exclude(status__iexact="down").exclude(neighbor_device__isnull=True).exclude(neighbor_device__exact="").first()
    if sample_up_identity:
        add_ok(f"sample_identity_port:{sample_up_identity.switch.name}/{sample_up_identity.interface_name}:{sample_up_identity.neighbor_device}/{sample_up_identity.neighbor_port or '-'}")
    else:
        add_warn("sample_identity_port:not_found")
    empty_down = qs.filter(status__iexact="down", mac_count=0).filter(neighbor_device__in=["", None]).first()
    if empty_down:
        add_ok(f"sample_empty_down_port:{empty_down.switch.name}/{empty_down.interface_name}")
    else:
        add_warn("sample_empty_down_port:not_found")
except Exception as e:
    add_fail("django_setup:" + str(e))

files = {
    "js": ROOT / "inventory/static/inventory/switchmap.js",
    "css": ROOT / "inventory/static/inventory/css/switchmap-phase79.css",
    "base": ROOT / "inventory/templates/inventory/base.html",
    "switch_list": ROOT / "inventory/templates/inventory/switch_list.html",
    "switch_detail": ROOT / "inventory/templates/inventory/switch_detail.html",
}
for label, path in files.items():
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if label == "js":
            for marker in ("Phase79.4 - final deterministic", "effectiveLastConnectionFromDataset", "setLastConnection(modal, 'data-field', effectiveLastConnectionFromDataset(d));"):
                if marker in text: add_ok(f"js_marker:{marker}")
                else: add_fail(f"js_marker_missing:{marker}")
        elif label == "css":
            if "Phase79.4 - final Last Connected Device layout" in text: add_ok("css:phase79_4_final")
            else: add_fail("css:phase79_4_final_missing")
        elif label == "base":
            if "switchmap-phase79.css" in text and "phase79-4-last-connected-final" in text: add_ok("base:phase79_css_version")
            else: add_fail("base:phase79_css_version_missing")
        else:
            if "phase79-lc-final" in text and "data-phase79-last-connected" in text: add_ok(f"template:{label}:phase79_lc_final")
            else: add_warn(f"template:{label}:phase79_lc_final_not_static_normalized")
    except Exception as e:
        add_fail(f"file:{label}:{e}")

print("PHASE79_4_LAST_CONNECTED_FINAL_REPORT")
print(f"OK_COUNT={len(ok)}")
print(f"WARNING_COUNT={len(warn)}")
print(f"FAIL_COUNT={len(fail)}")
print("\n[OK]")
print("\n".join(ok) if ok else "- none")
print("\n[WARNING]")
print("\n".join(warn) if warn else "- none")
print("\n[FAIL]")
print("\n".join(fail) if fail else "- none")
if fail:
    print("PHASE79_4_VERIFY_FAIL")
    sys.exit(1)
print("PHASE79_4_VERIFY_OK")
