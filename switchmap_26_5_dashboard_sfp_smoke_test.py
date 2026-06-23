import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client


def assert_ok(response, label):
    if response.status_code != 200:
        sys.exit(f"{label}_FAILED_STATUS_{response.status_code}\n{response.content[:500]!r}")


def main():
    django.setup()
    client = Client(HTTP_HOST="127.0.0.1")

    dashboard = client.get("/")
    assert_ok(dashboard, "DASHBOARD")
    content = dashboard.content.decode("utf-8", errors="ignore")
    if "data-sfp-dashboard" not in content or "Scan All SFP" not in content:
        sys.exit("DASHBOARD_SFP_WIDGET_MISSING")

    sfp_page = client.get("/sfp-monitor/")
    assert_ok(sfp_page, "SFP_MONITOR")
    sfp_content = sfp_page.content.decode("utf-8", errors="ignore")
    if "همه سوییچ‌های فعال" not in sfp_content:
        sys.exit("SFP_ALL_SWITCH_OPTION_MISSING")

    sfp_data = client.get("/sfp-monitor/data/?dashboard=1", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert_ok(sfp_data, "SFP_DASHBOARD_DATA")
    payload = sfp_data.json()
    if not payload.get("ok") or "dashboard" not in payload:
        sys.exit("SFP_DASHBOARD_DATA_INVALID")

    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
