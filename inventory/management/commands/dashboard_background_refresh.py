from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Switch
from inventory.snmp_tools import SnmpError, poll_switch_discovery, poll_switch_ports, sync_missing_snmp_ports
from inventory.views import _is_dashboard_test_device, _sync_alarm_notifications


# dashboard_background_refresh marker for phase 63 smoke compatibility
STATUS_FILE = Path(settings.BASE_DIR) / "logs" / "dashboard-background-refresh-status.json"


class Command(BaseCommand):
    help = "Phase 63: run read-only dashboard background refresh for all SNMP-enabled devices and alarm sync."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--no-discovery", action="store_true")
        parser.add_argument("--no-sync", action="store_true")

    def handle(self, *args, **options):
        quiet = bool(options.get("quiet"))
        no_discovery = bool(options.get("no_discovery"))
        no_sync = bool(options.get("no_sync"))
        started = timezone.now()
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

        switches = [
            switch for switch in Switch.objects.filter(is_active=True, snmp_enabled=True).order_by("topology_position", "name")
            if not _is_dashboard_test_device(switch)
        ]
        results = []
        ok_count = 0
        failed_count = 0

        for switch in switches:
            item = {"switch": switch.name, "ip": str(switch.management_ip), "ok": False, "steps": [], "error": ""}
            try:
                if not no_sync:
                    sync_result = sync_missing_snmp_ports(switch=switch, dry_run=False)
                    item["steps"].append({"name": "sync", "created": sync_result.get("created", 0), "matched": sync_result.get("matched", sync_result.get("existing", 0))})
                port_result = poll_switch_ports(switch=switch, dry_run=False, show_ignored=False)
                item["steps"].append({"name": "ports", "updated": port_result.get("updated", 0), "matched": port_result.get("matched", 0)})
                if not no_discovery:
                    discovery_result = poll_switch_discovery(switch=switch, dry_run=False)
                    item["steps"].append({"name": "discovery", "updated": discovery_result.get("updated", 0), "neighbors": discovery_result.get("neighbors", 0), "mac_ports": discovery_result.get("mac_ports", 0)})
                item["ok"] = True
                ok_count += 1
            except SnmpError as exc:
                item["error"] = str(exc)
                failed_count += 1
            except Exception as exc:
                item["error"] = str(exc)
                failed_count += 1
            results.append(item)

        alarm_status = {"active": 0}
        try:
            alarm_status = _sync_alarm_notifications()
        except Exception as exc:
            alarm_status = {"error": str(exc)}

        completed = timezone.now()
        status = {
            "phase_marker": "Phase 63 Dashboard Background Refresh",
            "status": "ok" if failed_count == 0 else "warning",
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "devices": len(switches),
            "ok": ok_count,
            "failed": failed_count,
            "alarm_status": alarm_status,
            "results": results[:50],
            "summary": f"devices={len(switches)} ok={ok_count} failed={failed_count} alarms={alarm_status.get('active', 0)}",
        }
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        if not quiet:
            self.stdout.write("PHASE63_DASHBOARD_BACKGROUND_REFRESH " + status["summary"])
        return status["summary"]
