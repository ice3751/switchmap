from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse


class Command(BaseCommand):
    help = "Phase93 performance-safe refine verification. Read-only except local cache writes."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def _line(self, text):
        self.stdout.write(str(text))

    def _fail(self, failures, key, detail):
        failures.append({"key": key, "detail": detail})
        self._line(f"FAIL {key}: {detail}")

    def _table_constraints(self, table_name):
        with connection.cursor() as cursor:
            try:
                return connection.introspection.get_constraints(cursor, table_name)
            except Exception:
                return {}

    def _query_count(self, func):
        with CaptureQueriesContext(connection) as captured:
            result = func()
        return len(captured), result

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        failures = []
        warnings = []
        report = {
            "phase": "Phase93",
            "generated_at": datetime.now().isoformat(),
            "strict": strict,
            "checks": {},
            "warnings": warnings,
            "failures": failures,
        }

        self._line("PHASE93_PERFORMANCE_SAFE_REFINE_CHECK_START")
        self._line("MODE=read_only_no_ssh_no_restore_no_backup_write")

        # Marker/source guard.
        context_path = Path(settings.BASE_DIR) / "inventory" / "context_processors.py"
        text = context_path.read_text(encoding="utf-8", errors="ignore")
        required_markers = [
            "Phase93: performance-safe context cache refine",
            "switchmap:phase93:alarm_counts:v2",
            "annotate(total=Count(\"id\"))",
        ]
        missing_markers = [marker for marker in required_markers if marker not in text]
        if missing_markers:
            self._fail(failures, "source_markers", ",".join(missing_markers))
        else:
            self._line("SOURCE_MARKERS_OK=3")
        report["checks"]["source_markers"] = {"missing": missing_markers}

        # URL guard: verify core pages still resolve.
        required_urls = [
            ("inventory:switch_list", [], "/"),
            ("inventory:backup_health_dashboard", [], "/backup-health/"),
            ("inventory:backup_storage_status", [], "/backup-storage/"),
            ("inventory:cisco_backup_center", [], "/cisco-backups/"),
            ("inventory:mikrotik_backup_center", [], "/mikrotik-backups/"),
            ("inventory:alarm_center", [], "/alarms/"),
            ("inventory:topology", [], "/topology/"),
            ("inventory:sfp_monitor", [], "/sfp-monitor/"),
            ("inventory:switchmap_ajax_ssh_port_action", [], "/ssh-port-action/"),
            ("inventory:switchmap_ajax_multi_ssh_port_action", [], "/ssh-port-multi-action/"),
            ("inventory:backup_validate_restore", [], "/backups/validate-restore/"),
        ]
        url_ok = 0
        for name, args, expected in required_urls:
            try:
                actual = reverse(name, args=args)
                match = resolve(expected)
                if actual != expected:
                    self._fail(failures, f"url_reverse:{name}", f"expected={expected} actual={actual}")
                else:
                    url_ok += 1
                    self._line(f"URL_OK={name}:{actual}:resolve={match.url_name}")
            except Exception as exc:
                self._fail(failures, f"url:{name}", repr(exc))
        report["checks"]["url_guard_ok"] = url_ok

        # Context processor query guard.
        try:
            from inventory import context_processors

            cache.delete("switchmap:phase93:alarm_counts:v2")
            cache.delete("switchmap:phase77:alarm_counts:v1")
            alarm_cold_queries, alarm_result = self._query_count(context_processors._alarm_counts)
            alarm_cached_queries, alarm_cached = self._query_count(context_processors._alarm_counts)
            self._line(f"ALARM_COUNTS_COLD_QUERIES={alarm_cold_queries}")
            self._line(f"ALARM_COUNTS_CACHED_QUERIES={alarm_cached_queries}")
            self._line(f"ALARM_COUNTS_ACTIVE={alarm_result.get('active', 0)}")
            self._line(f"ALARM_COUNTS_CRITICAL={alarm_result.get('critical', 0)}")
            self._line(f"ALARM_COUNTS_WARNING={alarm_result.get('warning', 0)}")
            if alarm_result.get("active") != alarm_cached.get("active"):
                self._fail(failures, "alarm_cache_consistency", "cached active count changed")
            if strict and alarm_cold_queries > 3:
                self._fail(failures, "alarm_cold_query_budget", f"queries={alarm_cold_queries} budget=3")
            if strict and alarm_cached_queries > 0:
                self._fail(failures, "alarm_cached_query_budget", f"queries={alarm_cached_queries} budget=0")
            report["checks"]["alarm_counts"] = {
                "cold_queries": alarm_cold_queries,
                "cached_queries": alarm_cached_queries,
                "active": alarm_result.get("active", 0),
                "critical": alarm_result.get("critical", 0),
                "warning": alarm_result.get("warning", 0),
            }

            cache.delete("switchmap:phase77:switch_menu_groups:v1")
            menu_cold_queries, menu_result = self._query_count(context_processors._switch_menu_groups)
            menu_cached_queries, menu_cached = self._query_count(context_processors._switch_menu_groups)
            menu_items = sum(len(group.get("items", [])) for group in menu_result)
            self._line(f"SWITCH_MENU_COLD_QUERIES={menu_cold_queries}")
            self._line(f"SWITCH_MENU_CACHED_QUERIES={menu_cached_queries}")
            self._line(f"SWITCH_MENU_GROUPS={len(menu_result)}")
            self._line(f"SWITCH_MENU_ITEMS={menu_items}")
            if len(menu_result) != len(menu_cached):
                self._fail(failures, "switch_menu_cache_consistency", "cached group count changed")
            if strict and menu_cold_queries > 2:
                self._fail(failures, "switch_menu_cold_query_budget", f"queries={menu_cold_queries} budget=2")
            if strict and menu_cached_queries > 0:
                self._fail(failures, "switch_menu_cached_query_budget", f"queries={menu_cached_queries} budget=0")
            report["checks"]["switch_menu"] = {
                "cold_queries": menu_cold_queries,
                "cached_queries": menu_cached_queries,
                "groups": len(menu_result),
                "items": menu_items,
            }
        except Exception as exc:
            self._fail(failures, "context_processor_query_guard", repr(exc))

        # Index guard: verify performance indexes already present; Phase93 does not mutate DB schema.
        expected_indexes = {
            "inventory_port": [
                "p77_port_desc_idx",
                "p77_port_cable_idx",
                "p77_port_iface_idx",
                "p77_port_status_idx",
                "p77_port_mode_idx",
                "p77_port_doc_idx",
            ],
            "inventory_switch": [
                "p77_sw_active_pos_idx",
                "p77_sw_family_active_idx",
                "p77_sw_role_active_idx",
            ],
            "inventory_alarmnotification": [
                "alarm_status_sev_seen_idx",
                "alarm_switch_status_idx",
                "alarm_cat_status_idx",
            ],
            "inventory_sfpmonitorsnapshot": [
                "sfp_sw_if_poll_idx",
                "sfp_health_poll_idx",
            ],
        }
        index_report = {}
        for table, names in expected_indexes.items():
            constraints = self._table_constraints(table)
            existing = set(constraints.keys())
            missing = [name for name in names if name not in existing]
            index_report[table] = {"expected": names, "missing": missing}
            if missing:
                self._fail(failures, f"missing_indexes:{table}", ",".join(missing))
            else:
                self._line(f"INDEX_GUARD_OK={table}:{len(names)}")
        report["checks"]["indexes"] = index_report

        # Restore guard: validate-only endpoints must exist; no execute restore URL should be introduced by Phase93.
        try:
            validate_url = reverse("inventory:backup_validate_restore")
            self._line(f"RESTORE_VALIDATE_URL_OK={validate_url}")
            try:
                reverse("inventory:backup_restore_execute")
                self._fail(failures, "restore_guard", "backup_restore_execute URL exists")
            except Exception:
                self._line("RESTORE_EXECUTE_URL_ABSENT_OK=True")
            report["checks"]["restore_guard"] = "validate_only"
        except Exception as exc:
            self._fail(failures, "restore_guard", repr(exc))

        # Optional report write.
        output = options.get("output") or ""
        if output:
            out = Path(output)
        else:
            out = Path(settings.BASE_DIR) / "logs" / "phase93_performance_safe_refine_check_latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        report["final_ok"] = not failures
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._line(f"REPORT_JSON={out}")

        if warnings:
            for warning in warnings:
                self._line(f"WARNING={warning}")

        if failures:
            self._line(f"FINAL_FAIL_COUNT={len(failures)}")
            raise CommandError("PHASE93_PERFORMANCE_SAFE_REFINE_CHECK_FAILED")

        self._line("FINAL_FAIL_COUNT=0")
        self._line("PHASE93_PERFORMANCE_SAFE_REFINE_CHECK_OK")
