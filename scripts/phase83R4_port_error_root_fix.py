import os
import shutil
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

django.setup()

from inventory.models import AlarmNotification, Port
try:
    from inventory.models import AlarmPolicyState
except Exception:
    AlarmPolicyState = None
from inventory.alarm_policy import alarm_is_false_positive, is_actionable_port_error
try:
    from inventory.alarm_engine import sync_alarm_notifications_v2
except Exception:
    sync_alarm_notifications_v2 = None

PHASE = "PHASE83R4_PORT_ERROR_ROOT_FIX"
BENIGN_OPER = {"down", "notpresent", "not present", "dormant", "lowerlayerdown", "lower layer down", "unknown", "testing", ""}


def norm(value):
    return str(value or "").strip().lower().replace(" ", "")


def db_backup():
    db_name = settings.DATABASES.get("default", {}).get("NAME")
    if not db_name:
        return "NO_DB_PATH"
    db_path = Path(db_name)
    if not db_path.exists():
        return "DB_NOT_FOUND"
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(settings.BASE_DIR) / "backups" / f"phase83R4_port_error_root_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / "db.sqlite3"
    shutil.copy2(db_path, target)
    return str(target)


def resolve_alarm(alarm, reason):
    now = timezone.now()
    marker = f"PHASE83R4 resolved: {reason}"
    details = (alarm.details or "").strip()
    if marker not in details:
        details = (details + "\n" + marker).strip()
    alarm.status = AlarmNotification.Status.RESOLVED
    alarm.resolved_at = now
    alarm.details = details
    alarm.save(update_fields=["status", "resolved_at", "details"])
    if AlarmPolicyState and getattr(alarm, "fingerprint", ""):
        state, _ = AlarmPolicyState.objects.get_or_create(
            fingerprint=alarm.fingerprint,
            defaults={"rule_key": "legacy_port_error"},
        )
        state.state = AlarmPolicyState.State.RESOLVED
        state.last_resolved_at = now
        state.suppressed_reason = reason[:255]
        state.save(update_fields=["state", "last_resolved_at", "suppressed_reason", "updated_at"])


def normalize_ports():
    changed = 0
    kept = 0
    for port in Port.objects.filter(status=Port.Status.ERROR).select_related("switch"):
        if is_actionable_port_error(port):
            kept += 1
            continue
        oper = norm(getattr(port, "snmp_oper_status", ""))
        # IF-MIB non-up/non-fault states are not Port Error. They are simply not operational/up.
        port.status = Port.Status.DOWN
        port.save(update_fields=["status"])
        changed += 1
    return changed, kept


def resolve_false_port_errors():
    resolved = 0
    kept = 0
    qs = AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE)
    for alarm in qs:
        title = str(alarm.title or "").strip().lower()
        fp = str(alarm.fingerprint or "").strip().lower()
        if title != "port error" and not fp.startswith("port-error:"):
            continue
        is_fp, reason = alarm_is_false_positive(alarm)
        if is_fp:
            resolve_alarm(alarm, reason or "port_error_without_fault_evidence")
            resolved += 1
            print("RESOLVED_PORT_ERROR=", alarm.id, getattr(alarm.switch, "name", "-"), getattr(alarm.port, "interface_name", "-"), reason)
        else:
            kept += 1
            print("KEPT_PORT_ERROR=", alarm.id, getattr(alarm.switch, "name", "-"), getattr(alarm.port, "interface_name", "-"))
    return resolved, kept


def url_check():
    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    paths = ["/", "/alarms/", "/alarms/rules/", "/topology/"]
    bad = []
    for path in paths:
        response = c.get(path)
        print("URL", path, response.status_code)
        if response.status_code >= 500:
            bad.append((path, response.status_code))
    if bad:
        raise SystemExit(f"{PHASE}_FAIL_URL {bad}")
    return len(paths)


def main():
    print(f"{PHASE}_START")
    print("DB_BACKUP=", db_backup())
    port_changed, port_kept = normalize_ports()
    print("NORMALIZED_PORT_ERROR_TO_DOWN=", port_changed)
    print("KEPT_ACTIONABLE_PORT_ERROR_PORTS=", port_kept)

    if sync_alarm_notifications_v2:
        print("ENGINE_SYNC=", sync_alarm_notifications_v2())
    else:
        print("ENGINE_SYNC=SKIPPED")

    resolved, kept = resolve_false_port_errors()
    cache.delete("switchmap:phase77:alarm_counts:v1")
    cache.clear()
    url_count = url_check()

    active = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    critical = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count()
    warning = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count()
    active_port_errors = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, title="Port Error").count()
    print("URL_CHECK_OK=", url_count)
    print("RESOLVED_FALSE_PORT_ERROR_COUNT=", resolved)
    print("KEPT_ACTIVE_PORT_ERROR_COUNT=", kept)
    print("ACTIVE_AFTER=", active)
    print("CRITICAL_AFTER=", critical)
    print("WARNING_AFTER=", warning)
    print("ACTIVE_PORT_ERROR_AFTER=", active_port_errors)
    print(f"{PHASE}_OK")


if __name__ == "__main__":
    main()
