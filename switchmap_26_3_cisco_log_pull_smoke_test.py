import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client

from inventory import views
from inventory.models import CiscoSyslogEntry, Switch


PULL_SAMPLE = """
Switch#show logging
Syslog logging: enabled
Log Buffer (4096 bytes):
*Jun 23 08:01:14.123: %LINK-3-UPDOWN: Interface Gi1/1/1, changed state to down Smoke26_3
*Jun 23 08:01:16.456: %LINEPROTO-5-UPDOWN: Line protocol on Interface Gi1/1/1, changed state to down Smoke26_3
""".strip()

switch = Switch.objects.order_by("id").first()
created_switch = False
if switch is None:
    switch = Switch.objects.create(
        name="SmokeTest-SW",
        management_ip="10.255.255.254",
        model="Cisco Catalyst 3850",
        location="Smoke Test",
        port_count=48,
        ssh_enabled=True,
        ssh_username="admin",
    )
    created_switch = True
else:
    switch.ssh_enabled = True
    if not switch.ssh_username:
        switch.ssh_username = "admin"
    switch.save(update_fields=["ssh_enabled", "ssh_username"])

CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3").delete()


def fake_run_switch_show_commands(*args, **kwargs):
    return {
        "ok": True,
        "commands": ["show logging"],
        "output": PULL_SAMPLE,
        "outputs": {"show logging": PULL_SAMPLE},
    }

views.run_switch_show_commands = fake_run_switch_show_commands

client = Client(HTTP_HOST="127.0.0.1")
page = client.get("/logs/?tab=cisco", HTTP_HOST="127.0.0.1")
if page.status_code != 200:
    raise SystemExit(f"LOG_PAGE_FAILED status={page.status_code}")
if b"Pull Cisco Logs" not in page.content:
    raise SystemExit("PULL_FORM_MISSING")

before = CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3").count()
response = client.post(
    "/logs/cisco/pull/",
    {
        "pull_switch": str(switch.id),
        "ssh_username": "admin",
        "ssh_password": "dummy",
        "enable_password": "",
    },
    HTTP_HOST="127.0.0.1",
)
if response.status_code not in (302, 200):
    raise SystemExit(f"PULL_FAILED status={response.status_code}")

after = CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3").count()
if after - before != 2:
    raise SystemExit(f"PULL_IMPORT_COUNT_FAILED before={before} after={after}")

second_response = client.post(
    "/logs/cisco/pull/",
    {
        "pull_switch": str(switch.id),
        "ssh_username": "admin",
        "ssh_password": "dummy",
        "enable_password": "",
    },
    HTTP_HOST="127.0.0.1",
)
if second_response.status_code not in (302, 200):
    raise SystemExit(f"SECOND_PULL_FAILED status={second_response.status_code}")

final = CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3").count()
if final != after:
    raise SystemExit(f"DEDUP_FAILED after={after} final={final}")

entry = CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3", facility="LINK", mnemonic="UPDOWN").first()
if not entry or entry.category != "interface" or entry.severity != 3:
    raise SystemExit("PULLED_LOG_PARSE_FAILED")

CiscoSyslogEntry.objects.filter(raw_line__contains="Smoke26_3").delete()
if created_switch:
    switch.delete()

print("SMOKE_TEST_OK")
