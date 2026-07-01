from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

from inventory.access_control import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEW_ONLY, allowed_ssh_actions, role_level
from inventory.forms import SSHPortActionForm
from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch


class Command(BaseCommand):
    help = "SwitchMap Phase 77 stabilization lock: read-only checks for critical functions and new phase URLs."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="", help="Optional report path")

    def handle(self, *args, **options):
        checks = []
        warnings = []
        failures = []

        def ok(name, detail="OK"):
            checks.append(("OK", name, detail))

        def warn(name, detail):
            warnings.append(("WARNING", name, detail))

        def fail(name, detail):
            failures.append(("FAIL", name, detail))

        required_url_names = [
            "switch_list",
            "switchmap_dashboard_data",
            "alarm_center",
            "sfp_monitor",
            "topology",
            "backup_center",
            "action_logs",
            "asset_documentation",
            "asset_completion",
            "automation_templates",
            "config_backups",
            "phase77_noc_dashboard",
            "phase77_status_json",
        ]
        for name in required_url_names:
            try:
                reverse(f"inventory:{name}")
                ok(f"url:{name}")
            except NoReverseMatch as exc:
                fail(f"url:{name}", str(exc))

        template_checks = {
            "inventory/templates/inventory/base.html": [
                "data-phase75-2-alarm-dropdown",
                "inventory:phase77_noc_dashboard",
                "inventory:automation_templates",
                "inventory:config_backups",
            ],
            "inventory/templates/inventory/switch_list.html": [
                "data-dashboard-live",
                "data-switch-search",
                "Quick Search",
            ],
            "inventory/static/inventory/switchmap.js": [
                "data-switch-search",
                "data-search-results",
            ],
            "inventory/static/inventory/css/switchmap-dashboard-stable-main.css": [
                "sm-main-dashboard",
            ],
            "inventory/static/inventory/css/switchmap-phase77.css": [
                "phase77-shell",
            ],
        }
        for rel_path, markers in template_checks.items():
            path = settings.BASE_DIR / rel_path
            if not path.exists():
                fail(f"file:{rel_path}", "missing")
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            missing = [marker for marker in markers if marker not in content]
            if missing:
                fail(f"markers:{rel_path}", ", ".join(missing))
            else:
                ok(f"markers:{rel_path}")

        switch_count = Switch.objects.filter(is_active=True).count()
        port_count = Port.objects.count()
        alarm_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
        sfp_count = SfpMonitorSnapshot.objects.count()
        if switch_count <= 0:
            fail("data:switches", "no active switch")
        else:
            ok("data:switches", str(switch_count))
        if port_count <= 0:
            fail("data:ports", "no port")
        else:
            ok("data:ports", str(port_count))
        ok("data:active_alarms", str(alarm_count))
        ok("data:sfp_snapshots", str(sfp_count))

        if role_level(ROLE_ADMIN) <= role_level(ROLE_OPERATOR):
            fail("role_order", "Admin must be higher than Operator")
        elif role_level(ROLE_OPERATOR) <= role_level(ROLE_VIEW_ONLY):
            fail("role_order", "Operator must be higher than View Only")
        else:
            ok("role_order", f"{ROLE_VIEW_ONLY} < {ROLE_OPERATOR} < {ROLE_ADMIN}")

        operator_actions = {value for value, _label in allowed_ssh_actions(type("Obj", (), {"is_authenticated": True, "is_superuser": False, "groups": type("Groups", (), {"values_list": lambda *a, **k: [ROLE_OPERATOR]})()})(), SSHPortActionForm.ACTION_CHOICES)}
        risky_admin_actions = {"force_trunk", "set_trunk_allowed", "add_trunk_vlan", "remove_trunk_vlan"}
        if operator_actions & risky_admin_actions:
            fail("role:ssh_operator_scope", f"operator has admin-only actions: {sorted(operator_actions & risky_admin_actions)}")
        else:
            ok("role:ssh_operator_scope")

        if alarm_count:
            warn("monitoring:active_alarms", f"{alarm_count} active alarms are operational state, not code failure")

        lines = []
        lines.append("PHASE77_STABILIZATION_LOCK=OK" if not failures else "PHASE77_STABILIZATION_LOCK=FAIL")
        lines.append(f"OK_COUNT={len(checks)}")
        lines.append(f"WARNING_COUNT={len(warnings)}")
        lines.append(f"FAIL_COUNT={len(failures)}")
        lines.append("")
        for group_name, group in (("OK", checks), ("WARNING", warnings), ("FAIL", failures)):
            lines.append(f"[{group_name}]")
            if group:
                for status, name, detail in group:
                    lines.append(f"{status} {name}: {detail}")
            else:
                lines.append("- none")
            lines.append("")

        report = "\n".join(lines)
        output = options.get("output")
        if not output:
            report_dir = settings.BASE_DIR / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            output = report_dir / "phase77_stabilization_lock_report.txt"
        else:
            output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        self.stdout.write(report)
        if failures:
            raise SystemExit(1)
