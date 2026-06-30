from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.utils import timezone  # noqa: E402


def age_text(value):
    if not value:
        return "NEVER"
    seconds = max(0, int((timezone.now() - value).total_seconds()))
    if seconds < 90:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h {minutes % 60}m ago"
    days = hours // 24
    return f"{days}d {hours % 24}h {minutes % 60}m ago"


def read_status(path):
    p = PROJECT / path
    if not p.exists():
        print(f"STATUS_FILE::{path}=MISSING")
        return
    print(f"STATUS_FILE::{path}=OK")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"STATUS_FILE::{path}=INVALID {exc}")
        return
    print(f"STATUS::{path}::status={data.get('status', '')}")
    print(f"STATUS::{path}::summary={data.get('summary', '')}")
    print(f"STATUS::{path}::completed_at={data.get('completed_at', '')}")


def print_credential_status(profile: str):
    from inventory.secure_credentials import SecureCredentialError, credential_status, load_ssh_monitor_credentials
    status = credential_status(profile)
    prefix = profile.upper()
    print(f"{prefix}_CREDENTIAL_EXISTS={'YES' if status.get('exists') else 'NO'}")
    print(f"{prefix}_CREDENTIAL_FILE={status.get('file', '')}")
    print(f"{prefix}_CREDENTIAL_LEGACY={'YES' if status.get('legacy') else 'NO'}")
    if status.get("exists"):
        try:
            payload = load_ssh_monitor_credentials(profile=profile)
            print(f"{prefix}_CREDENTIAL_DECRYPT=OK")
            print(f"{prefix}_CREDENTIAL_USER={payload.get('username', '')}")
            print(f"{prefix}_CREDENTIAL_CREATED_AT={payload.get('created_at', '')}")
        except SecureCredentialError as exc:
            print(f"{prefix}_CREDENTIAL_DECRYPT=FAIL {exc}")


def main():
    django.setup()
    from inventory.models import AlarmNotification, SfpMonitorSnapshot, Switch
    from inventory.views import _is_dashboard_test_device

    print("PHASE72_OPERATIONAL_STATUS")
    print(f"PROJECT={PROJECT}")
    print(f"NOW={timezone.now().isoformat()}")
    print_credential_status("cisco")
    print_credential_status("mikrotik")

    active = list(Switch.objects.filter(is_active=True).order_by("name"))
    operational = [s for s in active if not _is_dashboard_test_device(s)]
    print(f"ACTIVE_SWITCHES={len(active)}")
    print(f"OPERATIONAL_SWITCHES_NON_TEST={len(operational)}")
    print(f"ACTIVE_SNMP_SWITCHES_NON_TEST={sum(1 for s in operational if s.snmp_enabled)}")
    print(f"ACTIVE_SSH_SWITCHES_NON_TEST={sum(1 for s in operational if s.ssh_enabled)}")

    snmp_times = [s.snmp_last_poll for s in operational if s.snmp_enabled and s.snmp_last_poll]
    discovery_times = [s.discovery_last_poll for s in operational if s.snmp_enabled and s.discovery_last_poll]
    print(f"LATEST_SNMP={max(snmp_times).isoformat() if snmp_times else 'NEVER'} | {age_text(max(snmp_times)) if snmp_times else 'NEVER'}")
    print(f"OLDEST_SNMP={min(snmp_times).isoformat() if snmp_times else 'NEVER'} | {age_text(min(snmp_times)) if snmp_times else 'NEVER'}")
    print(f"LATEST_DISCOVERY={max(discovery_times).isoformat() if discovery_times else 'NEVER'} | {age_text(max(discovery_times)) if discovery_times else 'NEVER'}")
    print(f"OLDEST_DISCOVERY={min(discovery_times).isoformat() if discovery_times else 'NEVER'} | {age_text(min(discovery_times)) if discovery_times else 'NEVER'}")

    sfp_latest = SfpMonitorSnapshot.objects.order_by("-poll_time").first()
    sfp_count = SfpMonitorSnapshot.objects.values("switch_id", "interface_name").distinct().count()
    print(f"SFP_LATEST_INTERFACES={sfp_count}")
    print(f"SFP_LATEST_POLL={sfp_latest.poll_time.isoformat() if sfp_latest else 'NEVER'} | {age_text(sfp_latest.poll_time) if sfp_latest else 'NEVER'}")

    print(f"ACTIVE_ALARMS={AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()}")
    print(f"ACTIVE_SFP_ALARMS={AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, category=AlarmNotification.Category.SFP).count()}")
    print(f"ACTIVE_INTERFACE_ALARMS={AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, category=AlarmNotification.Category.INTERFACE).count()}")
    print(f"ACTIVE_CISCO_CRC_ALARMS={AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, fingerprint__startswith='cisco-crc:').count()}")

    read_status("logs/dashboard-background-refresh-status.json")
    read_status("logs/sfp-background-monitor-status.json")
    print("PHASE72_OPERATIONAL_STATUS_DONE")


if __name__ == "__main__":
    main()
