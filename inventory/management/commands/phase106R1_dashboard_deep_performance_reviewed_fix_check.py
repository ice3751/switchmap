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
    help = "Phase106 dashboard deep performance verification. Read-only except local cache writes."

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
            "phase": "Phase106",
            "generated_at": datetime.now().isoformat(),
            "strict": strict,
            "mode": "read_only_no_db_schema_no_ssh_no_restore_no_backup_write",
            "checks": {},
            "warnings": warnings,
            "failures": failures,
        }

        self._line("PHASE106R1_DASHBOARD_DEEP_PERFORMANCE_REVIEWED_FIX_CHECK_START")
        self._line("MODE=read_only_no_db_schema_no_ssh_no_restore_no_backup_write")

        try:
            from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch
            from inventory import views
        except Exception as exc:
            self._fail(failures, "import_guard", repr(exc))
            raise CommandError("PHASE106_IMPORT_FAILED")

        counts_before = {
            "switches": Switch.objects.count(),
            "ports": Port.objects.count(),
            "alarms": AlarmNotification.objects.count(),
            "sfp_snapshots": SfpMonitorSnapshot.objects.count(),
        }
        report["checks"]["counts_before"] = counts_before
        self._line("COUNTS_BEFORE=" + json.dumps(counts_before, ensure_ascii=False, sort_keys=True))

        base = Path(settings.BASE_DIR)
        views_text = (base / "inventory" / "views.py").read_text(encoding="utf-8", errors="ignore")
        switch_template_text = (base / "inventory" / "templates" / "inventory" / "switch_list.html").read_text(encoding="utf-8", errors="ignore")
        include_path = base / "inventory" / "templates" / "inventory" / "includes" / "dashboard_device_browser.html"
        include_text = include_path.read_text(encoding="utf-8", errors="ignore") if include_path.exists() else ""

        required_markers = [
            "Phase106: dashboard deep performance stabilization",
            "DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS",
            "DASHBOARD_FAST_TOPOLOGY_CACHE_KEY",
            "def _dashboard_device_browser_html",
            "def _dashboard_device_switches",
            "dashboard_device_browser_html = _dashboard_device_browser_html",
        ]
        missing = [marker for marker in required_markers if marker not in views_text]
        if missing:
            self._fail(failures, "source_markers", ",".join(missing))
        else:
            self._line("SOURCE_MARKERS_OK=6")
        report["checks"]["source_markers_missing"] = missing

        if '{{ dashboard_device_browser_html|safe }}' not in switch_template_text:
            self._fail(failures, "template_fragment_slot", "dashboard_device_browser_html slot missing")
        else:
            self._line("TEMPLATE_FRAGMENT_SLOT_OK=True")
        if not include_text or "data-switch-card" not in include_text or "device-browser-shell" not in include_text:
            self._fail(failures, "device_browser_include", "include missing or incomplete")
        else:
            self._line("DEVICE_BROWSER_INCLUDE_OK=True")
        if "data-sfp-dashboard-form" in switch_template_text or "async function pollNow" in switch_template_text:
            self._fail(failures, "dead_sfp_inline_js", "dead SFP dashboard JS still present in switch_list.html")
        else:
            self._line("DEAD_SFP_INLINE_JS_REMOVED_OK=True")
        if "_build_topology_payload()" in views_text[views_text.find("def _dashboard_topology_issues"):views_text.find("def _dashboard_insight_payload_uncached")]:
            self._fail(failures, "dashboard_topology_heavy_call", "_dashboard_topology_issues still calls full topology builder")
        else:
            self._line("DASHBOARD_TOPOLOGY_FAST_PATH_OK=True")

        ttl_values = {
            "dashboard_insight_cache_seconds": getattr(views, "DASHBOARD_INSIGHT_CACHE_SECONDS", None),
            "backup_dashboard_cache_seconds": getattr(views, "BACKUP_DASHBOARD_CACHE_SECONDS", None),
            "device_browser_cache_seconds": getattr(views, "DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS", None),
            "fast_topology_cache_seconds": getattr(views, "DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS", None),
        }
        report["checks"]["ttl_values"] = ttl_values
        self._line("TTL_VALUES=" + json.dumps(ttl_values, ensure_ascii=False, sort_keys=True))
        for key, value in ttl_values.items():
            if not isinstance(value, int) or value < 0:
                self._fail(failures, "ttl_guard", f"{key}={value!r}")

        try:
            url = reverse("inventory:switch_list")
            match = resolve("/")
            self._line(f"URL_OK=inventory:switch_list:{url}:resolve={match.url_name}")
            report["checks"]["url_switch_list"] = {"reverse": url, "resolve": match.url_name}
        except Exception as exc:
            self._fail(failures, "url_switch_list", repr(exc))

        try:
            cache.delete(getattr(views, "DASHBOARD_INSIGHT_CACHE_KEY", ""))
            cache.delete(getattr(views, "BACKUP_DASHBOARD_CACHE_KEY", ""))
            cache.delete(getattr(views, "DASHBOARD_FAST_TOPOLOGY_CACHE_KEY", ""))

            force_queries, force_ms, force_payload = self._measure(lambda: views._dashboard_insight_payload(force=True))
            build_queries, build_ms, build_payload = self._measure(lambda: views._dashboard_insight_payload())
            cached_queries, cached_ms, cached_payload = self._measure(lambda: views._dashboard_insight_payload())
            self._line(f"DASHBOARD_INSIGHT_FORCE_QUERIES={force_queries}")
            self._line(f"DASHBOARD_INSIGHT_FORCE_MS={force_ms}")
            self._line(f"DASHBOARD_INSIGHT_CACHE_BUILD_QUERIES={build_queries}")
            self._line(f"DASHBOARD_INSIGHT_CACHE_BUILD_MS={build_ms}")
            self._line(f"DASHBOARD_INSIGHT_CACHED_QUERIES={cached_queries}")
            self._line(f"DASHBOARD_INSIGHT_CACHED_MS={cached_ms}")
            if strict and cached_queries > 0:
                self._fail(failures, "dashboard_insight_cached_query_budget", f"queries={cached_queries} budget=0")
            if build_payload.get("generated_at") != cached_payload.get("generated_at"):
                self._fail(failures, "dashboard_insight_cache_consistency", "generated_at changed before TTL")
            report["checks"]["dashboard_insight"] = {
                "force_queries": force_queries,
                "force_ms": force_ms,
                "cache_build_queries": build_queries,
                "cache_build_ms": build_ms,
                "cached_queries": cached_queries,
                "cached_ms": cached_ms,
                "counters": cached_payload.get("counters", {}),
            }
        except Exception as exc:
            self._fail(failures, "dashboard_insight_runtime", repr(exc))

        try:
            factory = RequestFactory()
            request = factory.get("/")
            request.user = AnonymousUser()
            request.session = {}
            device_cache_key = views._dashboard_device_browser_cache_key(request, "")
            cache.delete(device_cache_key)

            fragment_build_queries, fragment_build_ms, fragment_build_html = self._measure(lambda: views._dashboard_device_browser_html(request, ""))
            fragment_cached_queries, fragment_cached_ms, fragment_cached_html = self._measure(lambda: views._dashboard_device_browser_html(request, ""))
            self._line(f"DEVICE_BROWSER_BUILD_QUERIES={fragment_build_queries}")
            self._line(f"DEVICE_BROWSER_BUILD_MS={fragment_build_ms}")
            self._line(f"DEVICE_BROWSER_CACHED_QUERIES={fragment_cached_queries}")
            self._line(f"DEVICE_BROWSER_CACHED_MS={fragment_cached_ms}")
            if "data-switch-card" not in fragment_cached_html:
                self._fail(failures, "device_browser_cached_html", "data-switch-card missing from cached fragment")
            if strict and fragment_cached_queries > 0:
                self._fail(failures, "device_browser_cached_query_budget", f"queries={fragment_cached_queries} budget=0")
            report["checks"]["device_browser_fragment"] = {
                "build_queries": fragment_build_queries,
                "build_ms": fragment_build_ms,
                "cached_queries": fragment_cached_queries,
                "cached_ms": fragment_cached_ms,
                "html_len": len(fragment_cached_html),
            }
        except Exception as exc:
            self._fail(failures, "device_browser_fragment_runtime", repr(exc))

        try:
            factory = RequestFactory()
            request = factory.get("/")
            request.user = AnonymousUser()
            request.session = {}
            cache.delete(getattr(views, "DASHBOARD_INSIGHT_CACHE_KEY", ""))
            cache.delete(getattr(views, "BACKUP_DASHBOARD_CACHE_KEY", ""))
            cache.delete(getattr(views, "DASHBOARD_FAST_TOPOLOGY_CACHE_KEY", ""))
            cache.delete(views._dashboard_device_browser_cache_key(request, ""))

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
            if strict and page_cached_ms > 1500:
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
        out = Path(output) if output else Path(settings.BASE_DIR) / "logs" / "phase106R1_dashboard_deep_performance_reviewed_fix_check_latest.json"
        if not out.is_absolute():
            out = Path(settings.BASE_DIR) / out
        out.parent.mkdir(parents=True, exist_ok=True)
        report["final_ok"] = not failures
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._line(f"REPORT_JSON={out}")

        if failures:
            self._line(f"FINAL_FAIL_COUNT={len(failures)}")
            self._line(f"FINAL_WARNING_COUNT={len(warnings)}")
            raise CommandError("PHASE106R1_DASHBOARD_DEEP_PERFORMANCE_REVIEWED_FIX_CHECK_FAILED")

        self._line("FINAL_FAIL_COUNT=0")
        self._line(f"FINAL_WARNING_COUNT={len(warnings)}")
        self._line("PHASE106R1_DASHBOARD_DEEP_PERFORMANCE_REVIEWED_FIX_CHECK_OK")
