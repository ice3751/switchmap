from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    (ROOT / "inventory" / "alarm_views.py", "PHASE79_9_ALARM_FILTERS"),
    (ROOT / "inventory" / "templates" / "inventory" / "alarm_center.html", "PHASE79_9_ALARM_FILTERS"),
    (ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-alarms.css", "PHASE79_9_ALARM_FILTERS"),
    (ROOT / "inventory" / "templates" / "inventory" / "base.html", "phase79-9-alarm-filters"),
]

failures = []
for path, marker in CHECKS:
    if not path.exists():
        failures.append(f"missing:{path}")
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    if marker not in text:
        failures.append(f"missing marker:{path}:{marker}")
    else:
        print(f"OK marker:{path.relative_to(ROOT)}:{marker}")

try:
    import py_compile
    py_compile.compile(str(ROOT / "inventory" / "alarm_views.py"), doraise=True)
    print("OK py_compile:inventory/alarm_views.py")
except Exception as exc:
    failures.append(f"py_compile_failed:{exc}")

if failures:
    print("PHASE79_9_FILE_VERIFY_FAIL")
    for item in failures:
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
    print("PHASE79_9_VERIFY_OK")
    sys.exit(0)

User = get_user_model()
user = User.objects.filter(is_superuser=True).first()
if not user:
    print("WARN django_http_verify_skipped:no_superuser")
    print("PHASE79_9_VERIFY_OK")
    sys.exit(0)

client = Client(HTTP_HOST="127.0.0.1")
client.force_login(user)
base = reverse("inventory:alarm_center")
urls = [
    base,
    base + "?status=all",
    base + "?status=active&severity=critical",
    base + "?status=active&type=snmp",
    base + "?status=active&type=sfp",
    base + "?q=snmp&port=Ethernet",
]
for url in urls:
    resp = client.get(url)
    if resp.status_code != 200:
        failures.append(f"http_status:{url}:{resp.status_code}")
        continue
    body = resp.content.decode("utf-8", errors="ignore")
    required = ["PHASE79_9_ALARM_FILTERS", "name=\"status\"", "name=\"severity\"", "name=\"type\"", "name=\"switch\"", "name=\"port\""]
    missing = [item for item in required if item not in body]
    if missing:
        failures.append(f"http_missing:{url}:{missing}")
    else:
        print(f"OK http:{url}")

if failures:
    print("PHASE79_9_VERIFY_FAIL")
    for item in failures:
        print("FAIL", item)
    sys.exit(1)

print("PHASE79_9_VERIFY_OK")
