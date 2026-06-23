import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client

from inventory.models import CiscoSyslogEntry, Switch
from inventory.views import CISCO_SAMPLE_LOG_TEXT


client = Client(HTTP_HOST="127.0.0.1")
page = client.get("/logs/?tab=cisco", HTTP_HOST="127.0.0.1")
if page.status_code != 200:
    raise SystemExit(f"LOG_PAGE_FAILED status={page.status_code}")
if CISCO_SAMPLE_LOG_TEXT.splitlines()[0].encode() not in page.content:
    raise SystemExit("DEFAULT_SAMPLE_TEXT_MISSING")

before_empty = CiscoSyslogEntry.objects.count()
empty_response = client.post(
    "/logs/cisco/import/",
    {"switch": "", "source_ip": "", "raw_text": ""},
    HTTP_HOST="127.0.0.1",
)
if empty_response.status_code not in (302, 200):
    raise SystemExit(f"EMPTY_IMPORT_FAILED status={empty_response.status_code}")
if CiscoSyslogEntry.objects.count() != before_empty:
    raise SystemExit("EMPTY_IMPORT_CREATED_LOG")

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

sample_lines = CISCO_SAMPLE_LOG_TEXT.splitlines()
before = CiscoSyslogEntry.objects.count()
response = client.post(
    "/logs/cisco/import/",
    {"switch": str(switch.id), "raw_text": CISCO_SAMPLE_LOG_TEXT},
    HTTP_HOST="127.0.0.1",
)
if response.status_code not in (302, 200):
    raise SystemExit(f"SAMPLE_IMPORT_FAILED status={response.status_code}")

after = CiscoSyslogEntry.objects.count()
if after - before != len(sample_lines):
    raise SystemExit(f"SAMPLE_IMPORT_COUNT_FAILED before={before} after={after} expected={len(sample_lines)}")

if not CiscoSyslogEntry.objects.filter(switch=switch, category="interface", raw_line__contains="%LINK-3-UPDOWN").exists():
    raise SystemExit("INTERFACE_CATEGORY_FAILED")
if not CiscoSyslogEntry.objects.filter(switch=switch, category="config", raw_line__contains="%SYS-5-CONFIG_I").exists():
    raise SystemExit("CONFIG_CATEGORY_FAILED")
if not CiscoSyslogEntry.objects.filter(switch=switch, category="security", raw_line__contains="%SEC_LOGIN-5-LOGIN_SUCCESS").exists():
    raise SystemExit("SECURITY_CATEGORY_FAILED")
if not CiscoSyslogEntry.objects.filter(switch=switch, category="poe", raw_line__contains="%ILPOWER-7-DETECT").exists():
    raise SystemExit("POE_CATEGORY_FAILED")
if not CiscoSyslogEntry.objects.filter(switch=switch, category="stp", raw_line__contains="%SPANTREE-2-BLOCK_BPDUGUARD").exists():
    raise SystemExit("STP_CATEGORY_FAILED")

CiscoSyslogEntry.objects.filter(raw_line__in=sample_lines).delete()
if created_switch:
    switch.delete()

print("SMOKE_TEST_OK")
