from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import get_commands  # noqa: E402
from django.db.models import Count, Max, Min  # noqa: E402
from django.utils import timezone  # noqa: E402

from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch  # noqa: E402

try:
    from inventory.views import _build_topology_payload, _sfp_has_issue, _sfp_issue_labels_for_snapshot  # noqa: E402
except Exception as exc:  # pragma: no cover
    _build_topology_payload = None
    _sfp_has_issue = None
    _sfp_issue_labels_for_snapshot = None
    IMPORT_VIEW_HELPERS_ERROR = repr(exc)
else:
    IMPORT_VIEW_HELPERS_ERROR = ""


def print_line(key, value):
    print(f"{key}={value}")


def age_seconds(dt):
    if not dt:
        return None
    try:
        seconds = int((timezone.now() - dt).total_seconds())
    except Exception:
        return None
    return max(0, seconds)


def age_text(dt):
    seconds = age_seconds(dt)
    if seconds is None:
        return "NEVER"
    d, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m}m ago"
    if h:
        return f"{h}h {m}m ago"
    if m:
        return f"{m}m {s}s ago"
    return f"{s}s ago"


def latest_per_sfp_interface():
    latest = {}
    qs = (
        SfpMonitorSnapshot.objects
        .select_related("switch", "port")
        .order_by("switch_id", "interface_name", "-poll_time", "-id")
    )
    for item in qs:
        key = (item.switch_id, item.interface_name)
        if key not in latest:
            latest[key] = item
    return list(latest.values())


def safe_issue_labels(item):
    if _sfp_issue_labels_for_snapshot is None:
        return []
    try:
        return list(_sfp_issue_labels_for_snapshot(item))
    except Exception:
        return []


def safe_has_issue(item):
    if _sfp_has_issue is None:
        return bool(safe_issue_labels(item))
    try:
        return bool(_sfp_has_issue(item))
    except Exception:
        return bool(safe_issue_labels(item))


def status_from_counts(never, stale, total):
    if total == 0:
        return "NO_TARGETS"
    if never == 0 and stale == 0:
        return "OK"
    return "WARNING"


def main():
    now = timezone.now()
    commands = get_commands()

    print_line("NOW", now.isoformat())
    print_line("DEBUG", settings.DEBUG)
    print_line("BASE_DIR", settings.BASE_DIR)
    print_line("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", ""))
    print_line("MANAGEMENT_COMMAND_dashboard_background_refresh", "YES" if "dashboard_background_refresh" in commands else "NO")
    print_line("MANAGEMENT_COMMAND_poll_discovery", "YES" if "poll_discovery" in commands else "NO")
    print_line("MANAGEMENT_COMMAND_poll_all_switches", "YES" if "poll_all_switches" in commands else "NO")
    print_line("VIEW_HELPERS_IMPORT_ERROR", IMPORT_VIEW_HELPERS_ERROR)

    active_switches = Switch.objects.filter(is_active=True)
    active_snmp = active_switches.filter(snmp_enabled=True)
    print_line("ACTIVE_SWITCHES", active_switches.count())
    print_line("ACTIVE_SNMP_SWITCHES", active_snmp.count())

    stale15 = now - timedelta(minutes=15)
    stale30 = now - timedelta(minutes=30)

    sw_agg = active_snmp.aggregate(
        latest_snmp=Max("snmp_last_poll"),
        oldest_snmp=Min("snmp_last_poll"),
        latest_discovery=Max("discovery_last_poll"),
        oldest_discovery=Min("discovery_last_poll"),
    )
    print_line("SWITCH_LATEST_SNMP", f"{sw_agg['latest_snmp']} | {age_text(sw_agg['latest_snmp'])}")
    print_line("SWITCH_OLDEST_SNMP", f"{sw_agg['oldest_snmp']} | {age_text(sw_agg['oldest_snmp'])}")
    print_line("SWITCH_LATEST_DISCOVERY", f"{sw_agg['latest_discovery']} | {age_text(sw_agg['latest_discovery'])}")
    print_line("SWITCH_OLDEST_DISCOVERY", f"{sw_agg['oldest_discovery']} | {age_text(sw_agg['oldest_discovery'])}")

    never_snmp = active_snmp.filter(snmp_last_poll__isnull=True).count()
    stale_snmp15 = active_snmp.filter(snmp_last_poll__lt=stale15).count()
    stale_snmp30 = active_snmp.filter(snmp_last_poll__lt=stale30).count()
    never_disc = active_snmp.filter(discovery_last_poll__isnull=True).count()
    stale_disc15 = active_snmp.filter(discovery_last_poll__lt=stale15).count()
    stale_disc30 = active_snmp.filter(discovery_last_poll__lt=stale30).count()
    print_line("SNMP_NEVER_SWITCHES", never_snmp)
    print_line("SNMP_STALE_GT_15MIN_SWITCHES", stale_snmp15)
    print_line("SNMP_STALE_GT_30MIN_SWITCHES", stale_snmp30)
    print_line("DISCOVERY_NEVER_SWITCHES", never_disc)
    print_line("DISCOVERY_STALE_GT_15MIN_SWITCHES", stale_disc15)
    print_line("DISCOVERY_STALE_GT_30MIN_SWITCHES", stale_disc30)
    print_line("VERDICT_SNMP_SWITCH_POLL", status_from_counts(never_snmp, stale_snmp15, active_snmp.count()))
    print_line("VERDICT_DISCOVERY_SWITCH_POLL", status_from_counts(never_disc, stale_disc15, active_snmp.count()))

    for sw in active_snmp.order_by("topology_position", "name"):
        snmp_age = age_text(sw.snmp_last_poll)
        disc_age = age_text(sw.discovery_last_poll)
        snmp_err = (sw.snmp_last_error or "").replace("\r", " ").replace("\n", " ")
        disc_err = (sw.discovery_last_error or "").replace("\r", " ").replace("\n", " ")
        if sw.snmp_last_poll is None or sw.discovery_last_poll is None or snmp_err or disc_err or age_seconds(sw.snmp_last_poll) and age_seconds(sw.snmp_last_poll) > 900:
            print(f"SWITCH_ATTENTION={sw.name}|{sw.management_ip}|snmp={snmp_age}|discovery={disc_age}|snmp_error={snmp_err}|discovery_error={disc_err}")

    ports = Port.objects.filter(switch__is_active=True, switch__snmp_enabled=True)
    port_agg = ports.aggregate(
        total=Count("id"),
        latest_snmp=Max("snmp_last_poll"),
        oldest_snmp=Min("snmp_last_poll"),
        latest_discovery=Max("discovery_last_poll"),
        oldest_discovery=Min("discovery_last_poll"),
    )
    print_line("SNMP_PORTS", port_agg["total"])
    print_line("PORT_LATEST_SNMP", f"{port_agg['latest_snmp']} | {age_text(port_agg['latest_snmp'])}")
    print_line("PORT_OLDEST_SNMP", f"{port_agg['oldest_snmp']} | {age_text(port_agg['oldest_snmp'])}")
    print_line("PORT_LATEST_DISCOVERY", f"{port_agg['latest_discovery']} | {age_text(port_agg['latest_discovery'])}")
    print_line("PORT_OLDEST_DISCOVERY", f"{port_agg['oldest_discovery']} | {age_text(port_agg['oldest_discovery'])}")
    print_line("PORTS_WITH_NEIGHBOR", ports.exclude(neighbor_device="").count())
    print_line("PORTS_WITH_MAC_TABLE", ports.filter(mac_count__gt=0).count())

    topology_ok = "UNKNOWN"
    if _build_topology_payload is None:
        print_line("TOPOLOGY_READ_ERROR", "view helper unavailable")
    else:
        try:
            topology = _build_topology_payload()
            tmap = topology.get("topology_map", {}) or {}
            nodes = len(tmap.get("nodes", []))
            links = len(tmap.get("links", []))
            internal = len(topology.get("internal_links", []))
            external = len(topology.get("external_links", []))
            missing = len(topology.get("uplinks_without_neighbor", []))
            print_line("TOPOLOGY_NODES", nodes)
            print_line("TOPOLOGY_LINKS", links)
            print_line("TOPOLOGY_INTERNAL_LINKS", internal)
            print_line("TOPOLOGY_EXTERNAL_LINKS", external)
            print_line("TOPOLOGY_UPLINKS_WITHOUT_NEIGHBOR", missing)
            topology_ok = "OK" if nodes and links else "WARNING"
        except Exception as exc:
            print_line("TOPOLOGY_READ_ERROR", repr(exc))
            topology_ok = "ERROR"
    print_line("VERDICT_TOPOLOGY_DATA", topology_ok)

    latest_sfp = latest_per_sfp_interface()
    sfp_latest_time = max([x.poll_time for x in latest_sfp], default=None)
    sfp_stale15 = sum(1 for x in latest_sfp if x.poll_time and x.poll_time < stale15)
    sfp_stale30 = sum(1 for x in latest_sfp if x.poll_time and x.poll_time < stale30)
    print_line("SFP_LATEST_INTERFACES", len(latest_sfp))
    print_line("SFP_LATEST_POLL", f"{sfp_latest_time} | {age_text(sfp_latest_time)}")
    print_line("SFP_STALE_GT_15MIN_INTERFACES", sfp_stale15)
    print_line("SFP_STALE_GT_30MIN_INTERFACES", sfp_stale30)
    health = Counter([x.health_state for x in latest_sfp])
    print_line("SFP_HEALTH_COUNTS", json.dumps(dict(health), ensure_ascii=False, sort_keys=True))
    issues = [x for x in latest_sfp if safe_has_issue(x)]
    print_line("SFP_ACTIVE_ISSUE_INTERFACES", len(issues))
    print_line("SFP_CRC_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.fcs_delta > 0 or x.align_delta > 0))
    print_line("SFP_INPUT_ERROR_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.input_error_delta > 0))
    print_line("SFP_OUTPUT_ERROR_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.output_error_delta > 0))
    print_line("SFP_ERR_DISABLED_INTERFACES", sum(1 for x in latest_sfp if x.err_disabled))
    if len(latest_sfp) == 0:
        sfp_verdict = "NO_DATA"
    elif sfp_latest_time is None or sfp_latest_time < stale15:
        sfp_verdict = "STALE_OR_MANUAL_ONLY"
    else:
        sfp_verdict = "RECENT_DATA"
    print_line("VERDICT_SFP_DATA_FRESHNESS", sfp_verdict)
    for item in issues[:10]:
        labels = ",".join(safe_issue_labels(item))
        print(f"SFP_ISSUE={item.switch.name}|{item.interface_name}|{item.health_state}|{labels}|poll={item.poll_time}|age={age_text(item.poll_time)}")

    active_alarms = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
    print_line("ACTIVE_ALARMS", active_alarms.count())
    print_line("ACTIVE_ALARMS_BY_CATEGORY", json.dumps(dict(Counter(active_alarms.values_list("category", flat=True))), ensure_ascii=False, sort_keys=True))
    print_line("ACTIVE_ALARMS_BY_SEVERITY", json.dumps(dict(Counter(active_alarms.values_list("severity", flat=True))), ensure_ascii=False, sort_keys=True))
    print_line("ACTIVE_SFP_ALARMS", active_alarms.filter(category=AlarmNotification.Category.SFP).count())
    crc_alarms = active_alarms.filter(category=AlarmNotification.Category.SFP).filter(title__icontains="CRC")
    print_line("ACTIVE_SFP_CRC_ALARMS", crc_alarms.count())
    for alarm in active_alarms.select_related("switch", "port").order_by("-last_seen", "-id")[:10]:
        sw = alarm.switch.name if alarm.switch else "-"
        port = alarm.port.interface_name if alarm.port else "-"
        print(f"ALARM={alarm.severity}|{alarm.category}|{sw}|{port}|{alarm.title}|last={alarm.last_seen}|age={age_text(alarm.last_seen)}")

    status_file = Path(settings.BASE_DIR) / "logs" / "dashboard-background-refresh-status.json"
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            print_line("BACKGROUND_STATUS", data.get("status", ""))
            print_line("BACKGROUND_SUMMARY", data.get("summary", ""))
            print_line("BACKGROUND_COMPLETED_AT", data.get("completed_at", ""))
            print_line("BACKGROUND_DEVICES", data.get("devices", ""))
            print_line("BACKGROUND_OK", data.get("ok", ""))
            print_line("BACKGROUND_FAILED", data.get("failed", ""))
        except Exception as exc:
            print_line("BACKGROUND_STATUS_FILE_ERROR", repr(exc))
    else:
        print_line("BACKGROUND_STATUS_FILE", "MISSING")

    print("PHASE71_1_READONLY_AUDIT_DONE")


if __name__ == "__main__":
    main()
