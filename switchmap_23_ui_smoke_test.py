import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.test import Client


def main():
    django.setup()
    allowed = list(getattr(settings, "ALLOWED_HOSTS", []))
    if "testserver" not in allowed:
        settings.ALLOWED_HOSTS = allowed + ["testserver"]

    client = Client()
    checks = [
        ("/", ["app-sidebar", "dashboard-overview-grid", "sm-cisco-3850", "data-auto-refresh-select"]),
        ("/reports/", ["report-accordion-list", "report-accordion-item"]),
        ("/topology/", ["topology-panel", "data-table"]),
        ("/logs/", ["data-table", "Action Log"]),
    ]

    for path, needles in checks:
        response = client.get(path)
        if response.status_code != 200:
            raise SystemExit(f"SMOKE_FAIL: {path} status={response.status_code}")
        body = response.content.decode("utf-8", errors="ignore")
        for needle in needles:
            if needle not in body:
                raise SystemExit(f"SMOKE_FAIL: {path} missing={needle}")

    css_path = BASE_DIR / "inventory" / "static" / "inventory" / "switchmap.css"
    css = css_path.read_text(encoding="utf-8", errors="ignore")
    for needle in ["SWITCHMAP_23_UI_OVERHAUL_START", "app-frame", "app-sidebar", "overview-card"]:
        if needle not in css:
            raise SystemExit(f"SMOKE_FAIL: css missing={needle}")

    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
