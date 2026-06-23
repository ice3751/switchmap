import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client


def main():
    django.setup()
    from inventory.models import PortActionLog

    for field_name in ["actor_username", "client_ip", "request_path", "action_label"]:
        PortActionLog._meta.get_field(field_name)

    client = Client(HTTP_HOST="127.0.0.1")
    logs_response = client.get("/logs/")
    if logs_response.status_code != 200:
        raise SystemExit(f"LOGS_PAGE_FAILED:{logs_response.status_code}")

    csv_response = client.get("/logs/export.csv")
    if csv_response.status_code != 200:
        raise SystemExit(f"LOGS_CSV_FAILED:{csv_response.status_code}")
    if "text/csv" not in csv_response.get("Content-Type", ""):
        raise SystemExit("LOGS_CSV_CONTENT_TYPE_FAILED")

    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
