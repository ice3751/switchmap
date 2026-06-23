import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client

from inventory.models import CiscoSyslogEntry, Switch


sample_logs = """
*Jun 22 07:11:14.123: %LINK-3-UPDOWN: Interface Gi1/0/1, changed state to up
*Jun 22 07:11:16.456: %LINEPROTO-5-UPDOWN: Line protocol on Interface Gi1/0/1, changed state to up
*Jun 22 07:12:01.000: %SYS-5-CONFIG_I: Configured from console by admin on vty0
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
    )
    created_switch = True

before = CiscoSyslogEntry.objects.count()
client = Client(HTTP_HOST="127.0.0.1")
response = client.post(
    "/logs/cisco/import/",
    {"switch": str(switch.id), "raw_text": sample_logs},
    HTTP_HOST="127.0.0.1",
)
if response.status_code not in (302, 200):
    raise SystemExit(f"IMPORT_FAILED status={response.status_code}")

after = CiscoSyslogEntry.objects.count()
if after - before != 3:
    raise SystemExit(f"IMPORT_COUNT_FAILED before={before} after={after}")

parsed = CiscoSyslogEntry.objects.filter(switch=switch, raw_line__contains="%LINK-3-UPDOWN").order_by("-id").first()
if not parsed or parsed.severity != 3 or parsed.facility != "LINK" or parsed.mnemonic != "UPDOWN" or parsed.category != "interface":
    raise SystemExit("PARSE_FAILED")

page = client.get("/logs/?tab=cisco", HTTP_HOST="127.0.0.1")
if page.status_code != 200:
    raise SystemExit(f"LOG_PAGE_FAILED status={page.status_code}")

CiscoSyslogEntry.objects.filter(raw_line__in=sample_logs.splitlines()).delete()
if created_switch:
    switch.delete()

print("SMOKE_TEST_OK")
