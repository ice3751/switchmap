from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from inventory.models import AlarmNotification, SfpMonitorSnapshot
from inventory.views import _sync_alarm_notifications

LINK_UP_STATES = {"connected", "up"}
POWER_TITLES = {"Rx Power abnormal", "Tx Power abnormal"}


def latest_sfp_snapshot(switch_id, interface_name):
    if not switch_id or not interface_name:
        return None
    return (
        SfpMonitorSnapshot.objects.filter(switch_id=switch_id, interface_name=interface_name)
        .order_by("-poll_time", "-id")
        .first()
    )


def alarm_interface(alarm):
    if alarm.port_id and getattr(alarm.port, "interface_name", ""):
        return alarm.port.interface_name
    message = str(alarm.message or "")
    if ":" in message:
        head = message.split(":", 1)[0]
        parts = head.split()
        if parts:
            return parts[-1]
    return ""


print("PHASE80_1_SFP_MODULE_ONLY_VERIFY_START")
result = _sync_alarm_notifications()
print("OK alarm_sync_result:", result)

active_power_alarms = list(
    AlarmNotification.objects.select_related("switch", "port")
    .filter(status__in=[AlarmNotification.Status.ACTIVE, AlarmNotification.Status.ACKNOWLEDGED], title__in=POWER_TITLES)
    .order_by("switch__name", "port__interface_name", "title")
)

false_items = []
for alarm in active_power_alarms:
    iface = alarm_interface(alarm)
    snapshot = latest_sfp_snapshot(alarm.switch_id, iface)
    status = str(getattr(snapshot, "link_status", "") or "").strip().lower() if snapshot else ""
    if status and status not in LINK_UP_STATES:
        false_items.append((alarm, status))

print("OK active_power_alarms:", len(active_power_alarms))
print("OK module_only_power_alarms:", len(false_items))
for alarm, status in false_items[:10]:
    print(
        "FAIL module_only_power_alarm:",
        f"id={alarm.id}",
        f"switch={alarm.switch.name if alarm.switch_id else '-'}",
        f"port={alarm_interface(alarm)}",
        f"title={alarm.title}",
        f"status={status}",
    )

if false_items:
    print("FINAL_FAIL_COUNT=1")
    print("PHASE80_1_SFP_MODULE_ONLY_VERIFY_FAIL")
    raise SystemExit(1)

print("FINAL_FAIL_COUNT=0")
print("PHASE80_1_SFP_MODULE_ONLY_VERIFY_OK")
