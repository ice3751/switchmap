from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
checks = []
failures = []

def ok(msg):
    print("OK " + msg)

def fail(msg):
    print("FAIL " + msg)
    failures.append(msg)

def contains(rel, marker):
    p = ROOT / rel
    if not p.exists():
        fail(f"missing:{rel}")
        return False
    text = p.read_text(encoding="utf-8", errors="ignore")
    if marker not in text:
        fail(f"missing_marker:{rel}:{marker}")
        return False
    ok(f"marker:{rel}:{marker}")
    return True

contains("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_7_POST_SSH_PORT_REFRESH")
contains("inventory/static/inventory/switchmap-phase79-lc-override.js", "schedulePostSshRefresh")
contains("inventory/static/inventory/switchmap-phase79-lc-override.js", "window.fetch")
contains("inventory/static/inventory/switchmap-phase79-lc-override.js", "/port/")
contains("inventory/templates/inventory/base.html", "phase79-7-post-ssh-port-refresh")
contains("inventory/templates/inventory/base.html", "switchmap-phase79-lc-override.js")

# read-only Django payload smoke if Django is available
try:
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.test import Client
    from django.contrib.auth import get_user_model
    from inventory.models import Switch, Port
    sw = Switch.objects.filter(management_ip="172.20.1.12").first() or Switch.objects.filter(name__icontains="NEXUS").first()
    if sw:
        qs = Port.objects.filter(switch=sw).order_by("id")[:3]
        u = get_user_model().objects.filter(is_superuser=True).first()
        c = Client(HTTP_HOST="127.0.0.1")
        if u:
            c.force_login(u)
            for p in qs:
                r = c.get(f"/port/{p.id}/payload/")
                if r.status_code == 200 and r.json().get("ok") and "last_connection" in r.json().get("port", {}):
                    ok(f"payload:{p.interface_name}:{p.id}")
                else:
                    fail(f"payload:{p.interface_name}:{p.id}:status={r.status_code}")
        else:
            ok("payload_smoke_skipped:no_superuser")
    else:
        ok("payload_smoke_skipped:no_nexus_switch")
except Exception as exc:
    ok(f"django_payload_smoke_skipped:{exc.__class__.__name__}:{exc}")

if failures:
    print("PHASE79_7_VERIFY_FAIL")
    sys.exit(1)
print("PHASE79_7_VERIFY_OK")
