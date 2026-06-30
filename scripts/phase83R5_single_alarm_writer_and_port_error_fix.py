import os
import re
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

PHASE = "PHASE83R5_SINGLE_ALARM_WRITER_AND_PORT_ERROR_FIX"
BASE_DIR = Path(settings.BASE_DIR)

AUTO_VISUAL = "auto visual placeholder"
EXPLICIT_FAULT_TOKENS = (
    "err-disabled", "errdisabled", "error-disabled", "error disabled",
    "gbic-invalid", "sfp invalid", "xcvr invalid", "transceiver invalid",
    "fault", "faulty", "hardware failure", "failed", "failure",
    "link-flap", "link flap", "port-security", "bpduguard", "bpdu guard",
)

SAFE_POLICY_APPEND = r'''

# PHASE83R5_SINGLE_ALARM_WRITER_AND_PORT_ERROR_FIX
# Root rule: generic Port.Status.ERROR is not an operational alarm.
# Only explicit physical/interface fault evidence can create/keep Port Error.
_PHASE83R5_AUTO_VISUAL = "auto visual placeholder"
_PHASE83R5_FAULT_TOKENS = (
    "err-disabled", "errdisabled", "error-disabled", "error disabled",
    "gbic-invalid", "sfp invalid", "xcvr invalid", "transceiver invalid",
    "fault", "faulty", "hardware failure", "failed", "failure",
    "link-flap", "link flap", "port-security", "bpduguard", "bpdu guard",
)
_PHASE83R5_BENIGN_OPER = {
    "", "down", "notconnect", "not connected", "notpresent", "not present",
    "lowerlayerdown", "lower layer down", "dormant", "unknown", "testing",
    "absent", "missing", "sfpabsent", "xcvrabsent",
}


def _phase83r5_text(*values):
    return " ".join(str(v or "") for v in values).strip().lower()


def _phase83r5_port_text(port):
    if not port:
        return ""
    return _phase83r5_text(
        getattr(port, "interface_name", ""),
        getattr(port, "status", ""),
        getattr(port, "snmp_admin_status", ""),
        getattr(port, "snmp_oper_status", ""),
        getattr(port, "description", ""),
        getattr(port, "snmp_alias", ""),
        getattr(port, "connected_device", ""),
        getattr(port, "neighbor_device", ""),
        getattr(port, "neighbor_port", ""),
        getattr(port, "notes", ""),
    )


def _phase83r5_alarm_text(alarm):
    return _phase83r5_text(
        getattr(alarm, "title", ""),
        getattr(alarm, "message", ""),
        getattr(alarm, "details", ""),
        getattr(alarm, "source", ""),
        _phase83r5_port_text(getattr(alarm, "port", None)),
    )


def _phase83r5_has_latest_err_disabled(port):
    if not port:
        return False
    try:
        from .models import SfpMonitorSnapshot
        snap = SfpMonitorSnapshot.objects.filter(
            switch_id=getattr(port, "switch_id", None),
            interface_name=getattr(port, "interface_name", ""),
        ).order_by("-poll_time", "-id").first()
        return bool(snap and getattr(snap, "err_disabled", False))
    except Exception:
        return False


def is_actionable_port_error(port, alarm=None):
    text = _phase83r5_alarm_text(alarm) if alarm is not None else _phase83r5_port_text(port)
    if _PHASE83R5_AUTO_VISUAL in text:
        return False
    if any(token in text for token in _PHASE83R5_FAULT_TOKENS):
        return True
    if _phase83r5_has_latest_err_disabled(port):
        return True
    return False


try:
    _phase83r5_previous_alarm_is_false_positive = alarm_is_false_positive
except NameError:
    _phase83r5_previous_alarm_is_false_positive = None


def alarm_is_false_positive(alarm):
    title = _phase83r5_text(getattr(alarm, "title", ""))
    fp = _phase83r5_text(getattr(alarm, "fingerprint", ""))
    text = _phase83r5_alarm_text(alarm)
    if title == "port error" or fp.startswith("port-error:"):
        if not is_actionable_port_error(getattr(alarm, "port", None), alarm):
            return True, "phase83r5_port_error_without_explicit_fault_evidence"
    if _PHASE83R5_AUTO_VISUAL in text:
        return True, "phase83r5_auto_visual_placeholder_not_alarm"
    if _phase83r5_previous_alarm_is_false_positive:
        return _phase83r5_previous_alarm_is_false_positive(alarm)
    return False, ""
'''


def backup_file(path: Path, backup_dir: Path):
    if path.exists():
        target = backup_dir / path.relative_to(BASE_DIR)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        return str(target)
    return "MISSING"


def db_backup(backup_dir: Path):
    db_name = settings.DATABASES.get("default", {}).get("NAME")
    if not db_name:
        return "NO_DB_PATH"
    db_path = Path(db_name)
    if not db_path.exists():
        return "DB_NOT_FOUND"
    target = backup_dir / "db.sqlite3"
    shutil.copy2(db_path, target)
    return str(target)


def patch_views(backup_dir: Path):
    path = BASE_DIR / "inventory" / "views.py"
    text = path.read_text(encoding="utf-8")
    backup_file(path, backup_dir)
    marker = "# PHASE83R5_SINGLE_ALARM_WRITER"
    new_func = '''def _sync_alarm_notifications():\n    # PHASE83R5_SINGLE_ALARM_WRITER\n    # UI/Alarm Center/Sync button must not create alarms directly.\n    from .alarm_engine import sync_alarm_notifications_v2\n    return sync_alarm_notifications_v2()\n\n'''
    if marker in text:
        return "already_patched"
    m = re.search(r"^def _sync_alarm_notifications\(\):\n(?=.+?^def\s+\w+\()", text, flags=re.M | re.S)
    if not m:
        raise RuntimeError("views.py _sync_alarm_notifications block not found")
    replacement = new_func
    patched = text[:m.start()] + replacement + text[m.end():]
    path.write_text(patched, encoding="utf-8")
    return "patched"


def patch_policy(backup_dir: Path):
    path = BASE_DIR / "inventory" / "alarm_policy.py"
    if not path.exists():
        path.write_text("from __future__ import annotations\n", encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    backup_file(path, backup_dir)
    if "PHASE83R5_SINGLE_ALARM_WRITER_AND_PORT_ERROR_FIX" in text:
        return "already_patched"
    path.write_text(text.rstrip() + SAFE_POLICY_APPEND + "\n", encoding="utf-8")
    return "patched"


def alarm_text(alarm):
    port = getattr(alarm, "port", None)
    return " ".join(str(v or "") for v in [
        getattr(alarm, "title", ""), getattr(alarm, "message", ""), getattr(alarm, "details", ""),
        getattr(alarm, "source", ""), getattr(port, "interface_name", "") if port else "",
        getattr(port, "status", "") if port else "", getattr(port, "snmp_oper_status", "") if port else "",
        getattr(port, "description", "") if port else "", getattr(port, "snmp_alias", "") if port else "",
    ]).lower()


def has_explicit_fault(alarm):
    text = alarm_text(alarm)
    if AUTO_VISUAL in text:
        return False
    if any(token in text for token in EXPLICIT_FAULT_TOKENS):
        return True
    port = getattr(alarm, "port", None)
    if port:
        try:
            from inventory.models import SfpMonitorSnapshot
            snap = SfpMonitorSnapshot.objects.filter(switch_id=port.switch_id, interface_name=port.interface_name).order_by("-poll_time", "-id").first()
            if snap and bool(getattr(snap, "err_disabled", False)):
                return True
        except Exception:
            pass
    return False


def resolve_alarm(alarm, reason):
    now = timezone.now()
    details = (alarm.details or "").strip()
    marker = f"PHASE83R5 resolved: {reason}"
    if marker not in details:
        details = (details + "\n" + marker).strip()
    alarm.status = AlarmNotification.Status.RESOLVED
    alarm.resolved_at = now
    alarm.details = details
    alarm.save(update_fields=["status", "resolved_at", "details"])
    try:
        from inventory.models import AlarmPolicyState
        state, _ = AlarmPolicyState.objects.get_or_create(fingerprint=alarm.fingerprint, defaults={"rule_key": "legacy"})
        state.state = AlarmPolicyState.State.RESOLVED
        state.last_resolved_at = now
        state.suppressed_reason = reason[:255]
        state.save(update_fields=["state", "last_resolved_at", "suppressed_reason", "updated_at"])
    except Exception:
        pass


def normalize_visual_ports():
    changed = 0
    qs = Port.objects.filter(status=Port.Status.ERROR)
    for port in qs:
        text = " ".join(str(v or "") for v in [port.description, port.snmp_alias, port.interface_name, port.snmp_oper_status]).lower()
        if AUTO_VISUAL in text or not any(token in text for token in EXPLICIT_FAULT_TOKENS):
            port.status = Port.Status.DOWN
            port.save(update_fields=["status"])
            changed += 1
    return changed


def cleanup_alarms():
    resolved = 0
    kept = 0
    qs = AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE)
    for alarm in qs:
        title = str(alarm.title or "").strip().lower()
        fp = str(alarm.fingerprint or "").strip().lower()
        if title == "port error" or fp.startswith("port-error:"):
            if has_explicit_fault(alarm):
                kept += 1
            else:
                resolve_alarm(alarm, "port_error_without_explicit_fault_evidence")
                print("RESOLVED_PORT_ERROR", alarm.id, getattr(alarm.switch, "name", "-"), getattr(alarm.port, "interface_name", "-"))
                resolved += 1
    return resolved, kept


def run_engine_once():
    try:
        from inventory.alarm_engine import sync_alarm_notifications_v2
        return sync_alarm_notifications_v2()
    except Exception as exc:
        return {"engine_error": str(exc)}


def url_check():
    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    paths = ["/", "/alarms/", "/alarms/rules/", "/topology/"]
    bad = []
    for p in paths:
        r = c.get(p)
        print("URL", p, r.status_code)
        if r.status_code >= 500:
            bad.append(f"{p}:{r.status_code}")
    if bad:
        raise SystemExit(f"{PHASE}_FAIL_URL " + ",".join(bad))
    return len(paths)


def main():
    print(f"{PHASE}_START")
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    backup_dir = BASE_DIR / "backups" / f"phase83R5_single_alarm_writer_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    print("BACKUP_DIR=", backup_dir)
    print("DB_BACKUP=", db_backup(backup_dir))
    print("PATCH_VIEWS=", patch_views(backup_dir))
    print("PATCH_POLICY=", patch_policy(backup_dir))

    normalized = normalize_visual_ports()
    print("NORMALIZED_PORT_ERROR_TO_DOWN=", normalized)
    print("ENGINE_SYNC=", run_engine_once())
    resolved, kept = cleanup_alarms()

    cache.delete("switchmap:phase77:alarm_counts:v1")
    cache.delete("switchmap:phase77:switch_menu_groups:v1")
    cache.clear()

    active_port_errors = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, title="Port Error").count()
    active_total = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    url_ok = url_check()

    print("URL_CHECK_OK=", url_ok)
    print("RESOLVED_PORT_ERROR_COUNT=", resolved)
    print("KEPT_EXPLICIT_PORT_ERROR_COUNT=", kept)
    print("ACTIVE_PORT_ERROR_AFTER=", active_port_errors)
    print("ACTIVE_TOTAL_AFTER=", active_total)
    if active_port_errors:
        for alarm in AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE, title="Port Error")[:20]:
            print("REMAINING_PORT_ERROR", alarm.id, getattr(alarm.switch, "name", "-"), getattr(alarm.port, "interface_name", "-"), alarm.message)
        raise SystemExit(f"{PHASE}_FAIL_ACTIVE_PORT_ERROR_REMAINS")
    print(f"{PHASE}_OK")


if __name__ == "__main__":
    main()
