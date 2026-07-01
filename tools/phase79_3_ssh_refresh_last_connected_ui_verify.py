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

def read(rel):
    path = ROOT / rel
    if not path.exists():
        add_fail(f"file_missing:{rel}")
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")

try:
    import django
    django.setup()
    from django.core.management import call_command
    from django.urls import reverse
    call_command("check")
    add_ok("django_check")
    for name in ("switch_list", "port_payload_json", "switchmap_ajax_ssh_port_action"):
        try:
            if name == "port_payload_json":
                reverse("inventory:" + name, args=[1])
            else:
                reverse("inventory:" + name)
            add_ok("url:" + name)
        except Exception as exc:
            add_fail("url:" + name + ":" + str(exc))
except Exception as exc:
    add_fail("django_setup:" + str(exc))

js = read("inventory/static/inventory/switchmap.js")
for marker in (
    "Phase79.3 - stable Last Connected Device renderer",
    "function refreshSelectedPortAfterSsh(",
    "refreshSelectedPortAfterSsh(form, result.data);",
):
    if marker in js:
        add_ok("js_marker:" + marker[:34])
    else:
        add_fail("js_marker_missing:" + marker[:34])

css = read("inventory/static/inventory/css/switchmap-phase79.css")
if "Phase79.3 - stable compact Last Connected Device panel" in css and "phase79-lc-v3-head" in css:
    add_ok("css:phase79_3_last_connected")
else:
    add_fail("css:phase79_3_last_connected")

base = read("inventory/templates/inventory/base.html")
if "phase79-3-ssh-refresh-last-connected-v3" in base:
    add_ok("base:phase79_css_version")
else:
    add_fail("base:phase79_css_version")

for rel in ("inventory/templates/inventory/switch_list.html", "inventory/templates/inventory/switch_detail.html"):
    text = read(rel)
    if "data-phase79-last-connected" in text:
        add_ok("template:last_connected:" + rel.rsplit("/", 1)[-1])
    else:
        add_fail("template:last_connected_missing:" + rel)
    if 'key-grid compact-grid port-main-grid phase79-last-connected' in text:
        add_warn("template:old_last_connected_classes:" + rel.rsplit("/", 1)[-1])

print("PHASE79_3_SSH_REFRESH_LAST_CONNECTED_UI_REPORT")
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
    print("PHASE79_3_VERIFY_FAIL")
    raise SystemExit(1)
print("PHASE79_3_VERIFY_OK")
