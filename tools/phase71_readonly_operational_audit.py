from __future__ import annotations

import json
import os
from collections import Counter
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db.models import Max, Min, Count  # noqa: E402
from django.utils import timezone  # noqa: E402

from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch  # noqa: E402
from inventory.views import _build_topology_payload, _sfp_has_issue, _sfp_issue_labels_for_snapshot  # noqa: E402


def age_text(dt):
    if not dt:
        return "NEVER"
    delta = timezone.now() - dt
    total = int(delta.total_seconds())
    if total < 0:
        total = 0
    d, r = divmod(total, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m}m ago"
    if h:
        return f"{h}h {m}m ago"
    if m:
        return f"{m}m {s}s ago"
    return f"{s}s ago"


def print_line(key, value):
    print(f"{key}={value}")


def latest_per_interface():
    latest = {}
    for item in SfpMonitorSnapshot.objects.select_related("switch", "port").order_by("switch_id", "interface_name", "-poll_time"):
        key = (item.switch_id, item.interface_name)
        if key not in latest:
            latest[key] = item
    return list(latest.values())


def main():
    now = timezone.now()
    print_line("NOW", now.isoformat())
    print_line("DEBUG", settings.DEBUG)

    active_snmp = Switch.objects.filter(is_active=True, snmp_enabled=True)
    print_line("ACTIVE_SNMP_SWITCHES", active_snmp.count())
    print_line("ACTIVE_SWITCHES", Switch.objects.filter(is_active=True).count())

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

    stale_cutoff = now - timedelta(minutes=15)
    never_snmp = active_snmp.filter(snmp_last_poll__isnull=True).count()
    stale_snmp = active_snmp.filter(snmp_last_poll__lt=stale_cutoff).count()
    never_disc = active_snmp.filter(discovery_last_poll__isnull=True).count()
    stale_disc = active_snmp.filter(discovery_last_poll__lt=stale_cutoff).count()
    print_line("SNMP_NEVER_SWITCHES", never_snmp)
    print_line("SNMP_STALE_GT_15MIN_SWITCHES", stale_snmp)
    print_line("DISCOVERY_NEVER_SWITCHES", never_disc)
    print_line("DISCOVERY_STALE_GT_15MIN_SWITCHES", stale_disc)

    ports = Port.objects.filter(switch__is_active=True, switch__snmp_enabled=True)
    port_agg = ports.aggregate(
        total=Count("id"),
        latest_snmp=Max("snmp_last_poll"),
        latest_discovery=Max("discovery_last_poll"),
    )
    print_line("SNMP_PORTS", port_agg["total"])
    print_line("PORT_LATEST_SNMP", f"{port_agg['latest_snmp']} | {age_text(port_agg['latest_snmp'])}")
    print_line("PORT_LATEST_DISCOVERY", f"{port_agg['latest_discovery']} | {age_text(port_agg['latest_discovery'])}")
    print_line("PORTS_WITH_NEIGHBOR", ports.exclude(neighbor_device="").count())
    print_line("PORTS_WITH_MAC_TABLE", ports.filter(mac_count__gt=0).count())

    try:
        topology = _build_topology_payload()
        tmap = topology.get("topology_map", {}) or {}
        print_line("TOPOLOGY_NODES", len(tmap.get("nodes", [])))
        print_line("TOPOLOGY_LINKS", len(tmap.get("links", [])))
        print_line("TOPOLOGY_INTERNAL_LINKS", len(topology.get("internal_links", [])))
        print_line("TOPOLOGY_EXTERNAL_LINKS", len(topology.get("external_links", [])))
        print_line("TOPOLOGY_UPLINKS_WITHOUT_NEIGHBOR", len(topology.get("uplinks_without_neighbor", [])))
    except Exception as exc:
        print_line("TOPOLOGY_READ_ERROR", repr(exc))

    latest_sfp = latest_per_interface()
    sfp_latest_time = max([x.poll_time for x in latest_sfp], default=None)
    print_line("SFP_LATEST_INTERFACES", len(latest_sfp))
    print_line("SFP_LATEST_POLL", f"{sfp_latest_time} | {age_text(sfp_latest_time)}")
    health = Counter([x.health_state for x in latest_sfp])
    print_line("SFP_HEALTH_COUNTS", json.dumps(dict(health), ensure_ascii=False, sort_keys=True))
    issues = [x for x in latest_sfp if _sfp_has_issue(x)]
    print_line("SFP_ACTIVE_ISSUE_INTERFACES", len(issues))
    print_line("SFP_CRC_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.fcs_delta > 0 or x.align_delta > 0))
    print_line("SFP_INPUT_ERROR_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.input_error_delta > 0))
    print_line("SFP_OUTPUT_ERROR_DELTA_INTERFACES", sum(1 for x in latest_sfp if x.output_error_delta > 0))
    print_line("SFP_ERR_DISABLED_INTERFACES", sum(1 for x in latest_sfp if x.err_disabled))
    for item in issues[:10]:
        labels = ",".join(_sfp_issue_labels_for_snapshot(item))
        print(f"SFP_ISSUE={item.switch.name}|{item.interface_name}|{item.health_state}|{labels}|poll={item.poll_time}|age={age_text(item.poll_time)}")

    active_alarms = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
    print_line("ACTIVE_ALARMS", active_alarms.count())
    print_line("ACTIVE_ALARMS_BY_CATEGORY", json.dumps(dict(Counter(active_alarms.values_list("category", flat=True))), ensure_ascii=False, sort_keys=True))
    print_line("ACTIVE_ALARMS_BY_SEVERITY", json.dumps(dict(Counter(active_alarms.values_list("severity", flat=True))), ensure_ascii=False, sort_keys=True))
    print_line("ACTIVE_SFP_ALARMS", active_alarms.filter(category=AlarmNotification.Category.SFP).count())
    crc_alarms = active_alarms.filter(category=AlarmNotification.Category.SFP).filter(title__icontains="CRC")
    print_line("ACTIVE_SFP_CRC_ALARMS", crc_alarms.count())
    for alarm in active_alarms.select_related("switch", "port").order_by("-last_seen")[:10]:
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
        except Exception as exc:
            print_line("BACKGROUND_STATUS_FILE_ERROR", repr(exc))
    else:
        print_line("BACKGROUND_STATUS_FILE", "MISSING")

    print("PHASE71_READONLY_AUDIT_DONE")


if __name__ == "__main__":
    main()
