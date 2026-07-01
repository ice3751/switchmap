import os
import re
import shutil
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.test import Client
from django.utils import timezone

django.setup()

from inventory.models import AlarmNotification, Switch, Port

try:
    from inventory.models import AlarmPolicyState
except Exception:
    AlarmPolicyState = None

try:
    from inventory.alarm_engine import sync_alarm_notifications_v2
except Exception:
    sync_alarm_notifications_v2 = None

try:
    from inventory.alarm_policy import alarm_is_false_positive, is_actionable_interface_down
except Exception:
    alarm_is_false_positive = None
    is_actionable_interface_down = None

PHASE = "PHASE83R3_ALARM_ENGINE_V2_STABILIZE"
FALSE_TAG = "Phase83R3 stabilized"

OPTICAL_TITLES = {"rx power abnormal", "tx power abnormal"}
SFP_COUNTER_TITLES = {"crc increased", "input error", "output error", "out discards"}
STRICT_TAGS = (
    "alarm:critical",
    "alarm=critical",
    "alarm:uplink",
    "monitor:critical",
    "monitor=uplink",
    "monitor-critical",
    "switchmap-monitor",
    "switchmap:monitor",
    "critical-monitor",
    "مانیتور:critical",
)
PHYSICAL_DELTA_KEYS = ("align", "fcs", "input", "output", "rcv", "xmit")
PLACEHOLDERS = {"", "-", "--", "---", "—", "neighbor", ":neighbor", "-:neighbor", "none", "unknown", "n/a", "na"}


def _db_backup():
    db_name = settings.DATABASES.get("default", {}).get("NAME")
    if not db_name:
        return "NO_DB_PATH"
    db_path = Path(db_name)
    if not db_path.exists():
        return "DB_NOT_FOUND"
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(settings.BASE_DIR) / "backups" / f"phase83R3_alarm_engine_v2_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / "db.sqlite3"
    shutil.copy2(db_path, target)
    return str(target)


def _text(*values):
    return " ".join(str(v or "") for v in values).strip().lower()


def _meaningful(value):
    t = str(value or "").strip().lower()
    return bool(t and t not in PLACEHOLDERS and re.search(r"[a-z0-9آ-ی]", t, re.I))


def _has_strict_tag(port):
    if not port:
        return False
    t = _text(
        getattr(port, "notes", ""),
        getattr(port, "description", ""),
        getattr(port, "connected_device", ""),
        getattr(port, "cable_label", ""),
        getattr(port, "asset_tag", ""),
    )
    return any(tag in t for tag in STRICT_TAGS)


def _parse_deltas(text):
    result = {}
    for key, value in re.findall(r"([A-Za-z]+)Δ\s*=\s*(-?\d+)", str(text or "")):
        try:
            result[key.lower()] = int(value)
        except Exception:
            result[key.lower()] = 0
    return result


def _latest_sfp_snapshot(alarm):
    try:
        from inventory.models import SfpMonitorSnapshot
    except Exception:
        return None
    port = getattr(alarm, "port", None)
    switch_id = getattr(alarm, "switch_id", None)
    iface = getattr(port, "interface_name", "") if port else ""
    if not switch_id or not iface:
        return None
    return SfpMonitorSnapshot.objects.filter(switch_id=switch_id, interface_name=iface).order_by("-poll_time", "-id").first()


def _link_up(value):
    return str(value or "").strip().lower() in {"up", "connected", "connect", "operational", "1"}


def _fp_reason(alarm):
    title = str(getattr(alarm, "title", "") or "").strip().lower()
    message = str(getattr(alarm, "message", "") or "").strip().lower()
    details = str(getattr(alarm, "details", "") or "")
    category = str(getattr(alarm, "category", "") or "").strip().lower()
    fp = str(getattr(alarm, "fingerprint", "") or "").strip().lower()
    port = getattr(alarm, "port", None)

    if alarm_is_false_positive:
        try:
            is_fp, reason = alarm_is_false_positive(alarm)
            if is_fp:
                return reason or "policy_false_positive"
        except Exception as exc:
            pass

    if fp.startswith("uplink-down:") or (category == "topology" and ("uplink" in title or "neighbor down" in title or " is down" in title or " is down" in message)):
        if not _has_strict_tag(port):
            return "topology_down_without_explicit_monitor_tag"
        if is_actionable_interface_down:
            try:
                if not is_actionable_interface_down(port):
                    return "topology_down_not_actionable_by_policy"
            except Exception:
                return "topology_down_policy_error"

    if title in OPTICAL_TITLES:
        snap = _latest_sfp_snapshot(alarm)
        if not snap or not _link_up(getattr(snap, "link_status", "")):
            return "sfp_optical_without_link_up"

    if "temperature abnormal" == title:
        snap = _latest_sfp_snapshot(alarm)
        try:
            temp = float(getattr(snap, "temperature_c", "") if snap else "")
            if -40.0 <= temp <= 85.0:
                return "sfp_temperature_within_sanity_range"
        except Exception:
            pass

    if fp.startswith("cisco-crc:") or "crc/input/output" in title or title in SFP_COUNTER_TITLES:
        deltas = _parse_deltas(details or message)
        physical = sum(max(0, int(deltas.get(k, 0))) for k in PHYSICAL_DELTA_KEYS)
        out_discard = max(0, int(deltas.get("outdiscard", 0)))
        if physical < 10:
            return "counter_without_physical_error_delta"
        if out_discard and physical == 0:
            return "discard_only_not_alarm"
        if port and not _link_up(getattr(port, "status", "") or getattr(port, "snmp_oper_status", "")):
            return "counter_alarm_port_not_up"

    return ""


def _resolve_alarm(alarm, reason):
    now = timezone.now()
    details = (alarm.details or "").strip()
    marker = f"{FALSE_TAG}: {reason}"
    if marker not in details:
        details = (details + "\n" + marker).strip()
    alarm.status = AlarmNotification.Status.RESOLVED
    alarm.resolved_at = now
    alarm.details = details
    alarm.save(update_fields=["status", "resolved_at", "details"])
    if AlarmPolicyState:
        state, _ = AlarmPolicyState.objects.get_or_create(
            fingerprint=alarm.fingerprint,
            defaults={"rule_key": "legacy"},
        )
        state.state = AlarmPolicyState.State.RESOLVED
        state.last_resolved_at = now
        state.suppressed_reason = reason[:255]
        state.save(update_fields=["state", "last_resolved_at", "suppressed_reason", "updated_at"])


def _url_check():
    from inventory import alarm_views
    assert hasattr(alarm_views, "alarm_rules_view"), "missing alarm_rules_view"
    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    paths = ["/", "/alarms/", "/alarms/rules/", "/topology/"]
    bad = []
    for p in paths:
        r = c.get(p)
        if r.status_code >= 500:
            bad.append(f"{p}:{r.status_code}")
    if bad:
        raise RuntimeError("URL_FAIL " + ",".join(bad))
    return len(paths)


def main():
    print(f"{PHASE}_START")
    print("DB_BACKUP=", _db_backup())

    if sync_alarm_notifications_v2:
        summary = sync_alarm_notifications_v2()
        print("ENGINE_SYNC=OK", summary)
    else:
        print("ENGINE_SYNC=SKIPPED")

    active = list(AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE))
    resolved = 0
    kept = 0
    for alarm in active:
        reason = _fp_reason(alarm)
        if reason:
            _resolve_alarm(alarm, reason)
            resolved += 1
            print("RESOLVED_FALSE_POSITIVE=", alarm.id, alarm.title, reason)
        else:
            kept += 1

    url_count = _url_check()

    remaining = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    remaining_critical = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count()
    remaining_warning = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count()

    bad_topology = []
    for alarm in AlarmNotification.objects.select_related("port").filter(status=AlarmNotification.Status.ACTIVE, category=AlarmNotification.Category.TOPOLOGY):
        reason = _fp_reason(alarm)
        if reason:
            bad_topology.append((alarm.id, alarm.title, reason))

    print("URL_CHECK_OK=", url_count)
    print("RESOLVED_FALSE_POSITIVE_COUNT=", resolved)
    print("KEPT_ACTIVE_COUNT=", kept)
    print("ACTIVE_AFTER=", remaining)
    print("CRITICAL_AFTER=", remaining_critical)
    print("WARNING_AFTER=", remaining_warning)
    print("BAD_TOPOLOGY_FALSE_POSITIVES_AFTER=", len(bad_topology))
    if bad_topology:
        for item in bad_topology:
            print("BAD_TOPOLOGY=", item)
        raise SystemExit(f"{PHASE}_FAIL")
    print(f"{PHASE}_OK")


if __name__ == "__main__":
    main()
