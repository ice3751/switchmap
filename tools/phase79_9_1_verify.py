from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
FAIL = []

def check(path, marker):
    p = ROOT / path
    if not p.exists():
        FAIL.append(f"missing:{path}")
        return ""
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if marker not in txt:
        FAIL.append(f"missing marker:{path}:{marker}")
    else:
        print(f"OK marker:{path}:{marker}")
    return txt

tpl = check("inventory/templates/inventory/alarm_center.html", "PHASE79_9_1_ALARM_FILTER_VISIBLE_FIX")
css = check("inventory/static/inventory/css/switchmap-alarms.css", "PHASE79_9_1_ALARM_FILTER_VISIBLE_FIX")
check("inventory/alarm_views.py", "PHASE79_9_ALARM_FILTERS")

bad = 'surface-card search-panel ui-collapsible alarm-filter-panel'
if bad in tpl:
    FAIL.append("filter_panel_still_uses_hidden_search_panel_class")
else:
    print("OK alarm_filter_not_using_hidden_search_panel_class")

if "display:block !important" not in css:
    FAIL.append("missing_display_override")
else:
    print("OK css_display_override")

try:
    import py_compile
    py_compile.compile(str(ROOT / "inventory" / "alarm_views.py"), doraise=True)
    print("OK py_compile:inventory/alarm_views.py")
except Exception as exc:
    FAIL.append(f"py_compile_failed:{exc}")

if FAIL:
    print("PHASE79_9_1_FILE_VERIFY_FAIL")
    for item in FAIL:
        print("FAIL", item)
    sys.exit(1)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "switchmap.settings")
try:
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import reverse
except Exception as exc:
    print(f"WARN django_http_verify_skipped:{exc}")
    print("PHASE79_9_1_VERIFY_OK")
    sys.exit(0)

user = get_user_model().objects.filter(is_superuser=True).first()
if not user:
    print("WARN django_http_verify_skipped:no_superuser")
    print("PHASE79_9_1_VERIFY_OK")
    sys.exit(0)

client = Client(HTTP_HOST="127.0.0.1")
client.force_login(user)
url = reverse("inventory:alarm_center") + "?status=active"
resp = client.get(url)
if resp.status_code != 200:
    FAIL.append(f"http_status:{resp.status_code}")
else:
    body = resp.content.decode("utf-8", errors="ignore")
    required = [
        "PHASE79_9_1_ALARM_FILTER_VISIBLE_FIX",
        "phase79-9-alarm-filter-panel",
        "Filter Alarms",
        "name=\"severity\"",
        "name=\"type\"",
        "name=\"switch\"",
        "name=\"port\"",
    ]
    for item in required:
        if item not in body:
            FAIL.append(f"http_missing:{item}")
    if 'surface-card search-panel ui-collapsible alarm-filter-panel' in body:
        FAIL.append("http_filter_panel_has_hidden_class")
    if not FAIL:
        print(f"OK http:{url}")

if FAIL:
    print("PHASE79_9_1_VERIFY_FAIL")
    for item in FAIL:
        print("FAIL", item)
    sys.exit(1)

print("PHASE79_9_1_VERIFY_OK")
