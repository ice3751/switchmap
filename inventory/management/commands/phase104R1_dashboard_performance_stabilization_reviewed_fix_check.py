from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse


class Command(BaseCommand):
    help = "Phase104R1 dashboard performance stabilization verification. Read-only except local cache writes."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def _line(self, text):
        self.stdout.write(str(text))

    def _fail(self, failures, key, detail):
        failures.append({"key": key, "detail": str(detail)})
        self._line(f"FAIL {key}: {detail}")

    def _warn(self, warnings, key, detail):
        warnings.append({"key": key, "detail": str(detail)})
        self._line(f"WARNING {key}: {detail}")

    def _measure(self, func):
        start = time.perf_counter()
        with CaptureQueriesContext(connection) as captured:
            result = func()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return len(captured), elapsed_ms, result

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        failures = []
        warnings = []
        report = {
            "phase": "Phase104R1",
            "generated_at": datetime.now().isoformat(),
            "strict": strict,
            "mode": "read_only_no_db_schema_no_ssh_no_restore_no_backup_write",
            "checks": {},
            "warnings": warnings,
            "failures": failures,
        }

        self._line("PHASE104R1_DASHBOARD_PERFORMANCE_STABILIZATION_CHECK_START")
        self._line("MODE=read_only_no_db_schema_no_ssh_no_restore_no_backup_write")

        try:
            from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch
            from inventory import views
        except Exception as exc:
            self._fail(failures, "import_guard", repr(exc))
            raise CommandError("PHASE104R1_IMPORT_FAILED")

        counts_before = {
            "switches": Switch.objects.count(),
            "ports": Port.objects.count(),
            "alarms": AlarmNotification.objects.count(),
            "sfp_snapshots": SfpMonitorSnapshot.objects.count(),
        }
        report["checks"]["counts_before"] = counts_before
        self._line("COUNTS_BEFORE=" + json.dumps(counts_before, ensure_ascii=False, sort_keys=True))

        views_path = Path(settings.BASE_DIR) / "inventory" / "views.py"
        views_text = views_path.read_text(encoding="utf-8", errors="ignore")
        required_markers = [
            "Phase104R1: dashboard performance stabilization",
            "def _phase104_int_env",
            "DASHBOARD_INSIGHT_CACHE_KEY",
            "def _dashboard_insight_payload_uncached",
            "def _dashboard_insight_payload(force=False)",
            "dashboard_insight = _dashboard_insight_payload()",
        ]
        missing = [marker for marker in required_markers if marker not in views_text]
        if missing:
            self._fail(failures, "source_markers", ",".join(missing))
        else:
            self._line("SOURCE_MARKERS_OK=6")
        report["checks"]["source_markers_missing"] = missing

        ttl_values = {
            "dashboard_insight_cache_seconds": getattr(views, "DASHBOARD_INSIGHT_CACHE_SECONDS", None),
            "backup_dashboard_cache_seconds": getattr(views, "BACKUP_DASHBOARD_CACHE_SECONDS", None),
        }
        report["checks"]["ttl_values"] = ttl_values
        for key, value in ttl_values.items():
            if not isinstance(value, int) or value < 0:
                self._fail(failures, "ttl_guard", f"{key}={value!r}")
        self._line("TTL_VALUES=" + json.dumps(ttl_values, ensure_ascii=False, sort_keys=True))

        switch_list_start = views_text.find("def switch_list(request):")
        switch_detail_start = views_text.find("def switch_detail", switch_list_start)
        switch_list_text = views_text[switch_list_start:switch_detail_start] if switch_list_start >= 0 and switch_detail_start > switch_list_start else ""
        forbidden_duplicate_calls = ["_sfp_dashboard_payload()", "_alarm_dashboard_payload()", "_backup_dashboard_payload()"]
        duplicate_calls = [item for item in forbidden_duplicate_calls if item in switch_list_text]
        if duplicate_calls:
            self._fail(failures, "switch_list_duplicate_dashboard_work", ",".join(duplicate_calls))
        else:
            self._line("SWITCH_LIST_DUPLICATE_DASHBOARD_WORK_REMOVED_OK=True")
        report["checks"]["switch_list_duplicate_calls"] = duplicate_calls

        try:
            url = reverse("inventory:switch_list")
            match = resolve("/")
            self._line(f"URL_OK=inventory:switch_list:{url}:resolve={match.url_name}")
            report["checks"]["url_switch_list"] = {"reverse": url, "resolve": match.url_name}
        except Exception as exc:
            self._fail(failures, "url_switch_list", repr(exc))

        try:
            cache.delete(views.DASHBOARD_INSIGHT_CACHE_KEY)
            cache.delete(views.BACKUP_DASHBOARD_CACHE_KEY)

            cold_queries, cold_ms, cold_payload = self._measure(lambda: views._dashboard_insight_payload(force=True))
            build_queries, build_ms, build_payload = self._measure(lambda: views._dashboard_insight_payload())
            cached_queries, cached_ms, cached_payload = self._measure(lambda: views._dashboard_insight_payload())

            self._line(f"DASHBOARD_INSIGHT_FORCE_QUERIES={cold_queries}")
            self._line(f"DASHBOARD_INSIGHT_FORCE_MS={cold_ms}")
            self._line(f"DASHBOARD_INSIGHT_CACHE_BUILD_QUERIES={build_queries}")
            self._line(f"DASHBOARD_INSIGHT_CACHE_BUILD_MS={build_ms}")
            self._line(f"DASHBOARD_INSIGHT_CACHED_QUERIES={cached_queries}")
            self._line(f"DASHBOARD_INSIGHT_CACHED_MS={cached_ms}")

            required_payload_keys = ["generated_at", "counters", "actions", "alarms", "topology_issues", "sfp_dashboard", "backup_dashboard", "alarm_categories"]
            missing_payload_keys = [key for key in required_payload_keys if key not in cached_payload]
            if missing_payload_keys:
                self._fail(failures, "dashboard_payload_keys", ",".join(missing_payload_keys))

            if cached_payload.get("generated_at") != build_payload.get("generated_at"):
                self._fail(failures, "dashboard_cache_consistency", "cached generated_at changed before TTL")

            if strict and cached_queries > 0:
                self._fail(failures, "dashboard_cached_query_budget", f"queries={cached_queries} budget=0")

            if cached_ms > build_ms and cached_ms > 250:
                self._warn(warnings, "dashboard_cached_time", f"cached_ms={cached_ms} build_ms={build_ms}")

            report["checks"]["dashboard_insight"] = {
                "force_queries": cold_queries,
                "force_ms": cold_ms,
                "cache_build_queries": build_queries,
                "cache_build_ms": build_ms,
                "cached_queries": cached_queries,
                "cached_ms": cached_ms,
                "missing_payload_keys": missing_payload_keys,
                "counters": cached_payload.get("counters", {}),
            }

            cache.delete(views.BACKUP_DASHBOARD_CACHE_KEY)
            backup_build_queries, backup_build_ms, backup_build = self._measure(lambda: views._backup_dashboard_payload())
            backup_cached_queries, backup_cached_ms, backup_cached = self._measure(lambda: views._backup_dashboard_payload())
            self._line(f"BACKUP_DASHBOARD_CACHE_BUILD_QUERIES={backup_build_queries}")
            self._line(f"BACKUP_DASHBOARD_CACHE_BUILD_MS={backup_build_ms}")
            self._line(f"BACKUP_DASHBOARD_CACHED_QUERIES={backup_cached_queries}")
            self._line(f"BACKUP_DASHBOARD_CACHED_MS={backup_cached_ms}")
            if backup_build.get("count") != backup_cached.get("count"):
                self._fail(failures, "backup_cache_consistency", "backup count changed before TTL")
            report["checks"]["backup_dashboard"] = {
                "cache_build_queries": backup_build_queries,
                "cache_build_ms": backup_build_ms,
                "cached_queries": backup_cached_queries,
                "cached_ms": backup_cached_ms,
                "count": backup_cached.get("count", 0),
            }
        except Exception as exc:
            self._fail(failures, "dashboard_cache_runtime", repr(exc))

        try:
            cache.delete(views.DASHBOARD_INSIGHT_CACHE_KEY)
            factory = RequestFactory()
            request = factory.get("/")
            request.user = AnonymousUser()
            request.session = {}
            page_cold_queries, page_cold_ms, page_cold_response = self._measure(lambda: views.switch_list(request))
            page_cached_queries, page_cached_ms, page_cached_response = self._measure(lambda: views.switch_list(request))
            cold_status = getattr(page_cold_response, "status_code", None)
            cached_status = getattr(page_cached_response, "status_code", None)
            self._line(f"SWITCH_LIST_COLD_STATUS={cold_status}")
            self._line(f"SWITCH_LIST_COLD_QUERIES={page_cold_queries}")
            self._line(f"SWITCH_LIST_COLD_MS={page_cold_ms}")
            self._line(f"SWITCH_LIST_CACHED_STATUS={cached_status}")
            self._line(f"SWITCH_LIST_CACHED_QUERIES={page_cached_queries}")
            self._line(f"SWITCH_LIST_CACHED_MS={page_cached_ms}")
            if cold_status != 200 or cached_status != 200:
                self._fail(failures, "switch_list_render_status", f"cold={cold_status} cached={cached_status}")
            if strict and page_cached_ms > 6000:
                self._warn(warnings, "switch_list_cached_time_high", f"cached_ms={page_cached_ms}")
            report["checks"]["switch_list_render"] = {
                "cold_status": cold_status,
                "cold_queries": page_cold_queries,
                "cold_ms": page_cold_ms,
                "cached_status": cached_status,
                "cached_queries": page_cached_queries,
                "cached_ms": page_cached_ms,
            }
        except Exception as exc:
            self._fail(failures, "switch_list_render_runtime", repr(exc))

        counts_after = {
            "switches": Switch.objects.count(),
            "ports": Port.objects.count(),
            "alarms": AlarmNotification.objects.count(),
            "sfp_snapshots": SfpMonitorSnapshot.objects.count(),
        }
        report["checks"]["counts_after"] = counts_after
        self._line("COUNTS_AFTER=" + json.dumps(counts_after, ensure_ascii=False, sort_keys=True))
        if counts_before != counts_after:
            self._fail(failures, "db_count_mutation_guard", f"before={counts_before} after={counts_after}")

        self._line("DB_MUTATION=NO")
        self._line("MIGRATION_WRITE=NO")
        self._line("RESTORE_ENABLE_CHANGE=NO")
        self._line("SSH_EXECUTION=NO")
        self._line("OPERATIONAL_BACKUP_WRITE=NO")
        self._line("VISIBLE_TEST_DATA_CREATED=NO")

        output = options.get("output") or ""
        if output:
            out = Path(output)
        else:
            out = Path(settings.BASE_DIR) / "logs" / "phase104R1_dashboard_performance_stabilization_check_latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        report["final_ok"] = not failures
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._line(f"REPORT_JSON={out}")

        if failures:
            self._line(f"FINAL_FAIL_COUNT={len(failures)}")
            self._line(f"FINAL_WARNING_COUNT={len(warnings)}")
            raise CommandError("PHASE104R1_DASHBOARD_PERFORMANCE_STABILIZATION_CHECK_FAILED")

        self._line("FINAL_FAIL_COUNT=0")
        self._line(f"FINAL_WARNING_COUNT={len(warnings)}")
        self._line("PHASE104R1_DASHBOARD_PERFORMANCE_STABILIZATION_CHECK_OK")
