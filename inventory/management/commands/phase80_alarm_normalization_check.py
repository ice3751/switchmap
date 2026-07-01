from pathlib import Path
import py_compile

from django.core.management.base import BaseCommand
from django.urls import reverse

from inventory.alarm_rules import RULES, alarm_rule_report, phase80_state_summary


class Command(BaseCommand):
    help = "Phase 80 read-only alarm normalization verification. No polling, no DB mutation."

    def handle(self, *args, **options):
        ok = 0
        warn = 0
        fail = 0

        def line(level, name, detail=""):
            self.stdout.write(f"{level} {name}{(': ' + detail) if detail else ''}")

        def good(name, detail=""):
            nonlocal ok
            ok += 1
            line("OK", name, detail)

        def bad(name, detail=""):
            nonlocal fail
            fail += 1
            line("FAIL", name, detail)

        self.stdout.write("PHASE80_ALARM_NORMALIZATION_VERIFY_START")

        required = {
            "snmp_timeout",
            "topology_discovery_error",
            "interface_error",
            "important_interface_down",
            "sfp_err_disabled",
            "sfp_counter_delta",
            "sfp_optical_threshold",
            "cisco_crc_delta",
        }
        missing = sorted(required - set(RULES))
        if missing:
            bad("missing_rules", ",".join(missing))
        else:
            good("required_rules", str(len(required)))

        for item in alarm_rule_report():
            fields = [
                "source",
                "device_type",
                "severity",
                "threshold",
                "consecutive_failures",
                "recovery_condition",
                "dedup_key",
                "suppress_if_parent_down",
                "cooldown_seconds",
            ]
            empty = [field for field in fields if item.get(field) in (None, "")]
            if empty:
                bad(f"rule_fields:{item['key']}", ",".join(empty))
            else:
                good(f"rule_fields:{item['key']}")

        for path_name in ["alarm_center", "alarm_rules", "alarm_sync"]:
            try:
                url = reverse(f"inventory:{path_name}")
                good(f"url:{path_name}", url)
            except Exception as exc:
                bad(f"url:{path_name}", str(exc))

        root = Path(__file__).resolve().parents[3]
        for rel in [
            "inventory/alarm_rules.py",
            "inventory/views.py",
            "inventory/alarm_views.py",
            "inventory/management/commands/sfp_background_monitor.py",
        ]:
            path = root / rel
            if not path.exists():
                bad(f"missing_file:{rel}")
                continue
            try:
                py_compile.compile(str(path), doraise=True)
                good(f"py_compile:{rel}")
            except Exception as exc:
                bad(f"py_compile:{rel}", str(exc))

        state = phase80_state_summary()
        good("state_path", state.get("state_path", ""))
        good("tracked_keys", str(state.get("tracked_keys", 0)))

        self.stdout.write(f"FINAL_OK_COUNT={ok}")
        self.stdout.write(f"FINAL_WARNING_COUNT={warn}")
        self.stdout.write(f"FINAL_FAIL_COUNT={fail}")
        if fail:
            self.stdout.write("PHASE80_ALARM_NORMALIZATION_VERIFY_FAIL")
            raise SystemExit(1)
        self.stdout.write("PHASE80_ALARM_NORMALIZATION_VERIFY_OK")
