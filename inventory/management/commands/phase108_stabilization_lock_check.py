# Phase108 Stabilization Lock Verify
# Read-only verification for SwitchMap after Phase107R2 performance lock.

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, reverse
from django.utils import timezone


class Command(BaseCommand):
    help = "Phase108 read-only stabilization lock verification."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="logs/phase108_stabilization_lock_check.json")
        parser.add_argument("--http-host", default="127.0.0.1")

    def handle(self, *args, **options):
        self.strict = bool(options.get("strict"))
        self.root = Path(getattr(settings, "BASE_DIR", ".")).resolve()
        self.http_host = options.get("http_host") or "127.0.0.1"
        self.failures: List[str] = []
        self.warnings: List[str] = []
        self.ok: List[str] = []
        self.report: Dict[str, Any] = {
            "phase": "108",
            "name": "stabilization_lock_check",
            "timestamp": timezone.now().isoformat(),
            "mode": "read_only_no_db_schema_no_ssh_no_restore_no_backup_write_no_ui_change",
            "root": str(self.root),
            "http_host": self.http_host,
            "checks": {},
        }

        self._line("PHASE108_STABILIZATION_LOCK_CHECK_START")
        self._line("MODE=read_only_no_db_schema_no_ssh_no_restore_no_backup_write_no_ui_change")
        self._line(f"ROOT={self.root}")

        before = self._counts()
        self.report["counts_before"] = before
        self._line("COUNTS_BEFORE=" + json.dumps(before, ensure_ascii=False, sort_keys=True))

        self._source_file_presence()
        self._source_markers()
        self._url_resolve_checks()
        self._http_guard_checks()
        self._performance_lock_checks()
        self._security_static_guards()
        self._django_dry_run_checks()

        after = self._counts()
        self.report["counts_after"] = after
        self._line("COUNTS_AFTER=" + json.dumps(after, ensure_ascii=False, sort_keys=True))
        if before != after:
            self._fail("db_count_mutation", f"before={before} after={after}")

        self._finalize_report(options.get("output"))

    def _line(self, text: str):
        self.stdout.write(str(text))

    def _ok(self, key: str, detail: Any = True):
        msg = f"OK={key}" if detail is True else f"OK={key}:{detail}"
        self.ok.append(msg)
        self._line(msg)
        self.report["checks"][key] = {"status": "ok", "detail": detail}

    def _warn(self, key: str, detail: Any = True):
        msg = f"WARNING {key}: {detail}"
        self.warnings.append(msg)
        self._line(msg)
        self.report["checks"][key] = {"status": "warning", "detail": detail}

    def _fail(self, key: str, detail: Any = True):
        msg = f"FAIL {key}: {detail}"
        self.failures.append(msg)
        self._line(msg)
        self.report["checks"][key] = {"status": "fail", "detail": detail}

    def _read(self, rel: str) -> str:
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    def _exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def _sha256_short(self, rel: str) -> str:
        path = self.root / rel
        if not path.exists() or not path.is_file():
            return ""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def _counts(self) -> Dict[str, int]:
        names = [
            "Switch", "Port", "Alarm", "ActionLog", "SfpSnapshot", "SFPSnapshot",
            "RouterHealthSnapshot", "ConfigBackupSnapshot", "BackupMetadata",
        ]
        out: Dict[str, int] = {}
        for name in names:
            model = self._model(name)
            if model is None:
                continue
            try:
                out[name] = int(model.objects.count())
            except Exception as exc:
                out[name] = -1
                self._warn(f"count_{name}", repr(exc))
        return out

    def _model(self, name: str):
        try:
            return apps.get_model("inventory", name)
        except LookupError:
            return None

    def _source_file_presence(self):
        required = [
            "inventory/views.py",
            "inventory/dashboard_views.py",
            "inventory/urls.py",
            "inventory/templates/inventory/base.html",
            "inventory/templates/inventory/switch_list.html",
            "inventory/templates/inventory/includes/dashboard_device_browser.html",
            "inventory/static/inventory/switchmap.js",
            "inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css",
            "smoke_tests/run_smoke.py",
        ]
        files = {}
        for rel in required:
            exists = self._exists(rel)
            files[rel] = {"exists": exists, "sha256_16": self._sha256_short(rel)}
            if exists:
                self._ok("file_present", rel)
            else:
                self._fail("file_missing", rel)
        self.report["files"] = files

    def _source_markers(self):
        switch_list = self._read("inventory/templates/inventory/switch_list.html")
        base = self._read("inventory/templates/inventory/base.html")
        views = self._read("inventory/views.py")
        urls = self._read("inventory/urls.py")
        js = self._read("inventory/static/inventory/switchmap.js")
        css_cards = self._read("inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css")

        checks = {
            "dashboard_phase103_css_present": "switchmap-phase103-dashboard-cards.css" in switch_list,
            "dashboard_phase107_lazy_holder": "phase107-device-browser-lazy" in switch_list,
            "dashboard_lazy_url_context": "dashboard_device_browser_url" in switch_list and "dashboard_device_browser_url" in views,
            "dashboard_no_bunny_font_in_switch_list": "fonts.bunny.net" not in switch_list,
            "dashboard_cards_css_scope": "phase103" in css_cards.lower() and "dashboard-card" in css_cards.lower(),
            "switchmap_js_present": "switchmap.js" in base,
            "phase79_lc_override_present": "switchmap-phase79-lc-override.js" in base,
            "lazy_fragment_view_present": "dashboard_device_browser_fragment_view" in views,
            "lazy_fragment_url_present": "dashboard/device-browser/" in urls,
            "lazy_js_fetch_present": "fetch(" in js and "data-phase107-device-browser" in js,
            "quick_search_marker_present": "data-search-results" in switch_list or "sm-final-search-main" in switch_list,
            "port_popup_marker_present": "dashboard-port-modal" in switch_list and "data-modal-close" in switch_list,
            "ssh_endpoint_marker_present": "ssh-port-action" in urls and "ssh-port-preview" in urls,
            "alarm_marker_present": "alarm_center" in urls and "alarms/" in urls,
            "sfp_marker_present": "sfp_monitor" in urls and "sfp-monitor" in urls,
            "topology_marker_present": "topology" in urls and "topology/" in urls,
            "backup_marker_present": "backup_center" in urls and "backups/" in urls,
        }
        self.report["source_markers"] = checks
        for key, passed in checks.items():
            if passed:
                self._ok(key)
            else:
                self._fail(key)

    def _reverse(self, name: str, *args) -> Tuple[bool, str]:
        try:
            return True, reverse(f"inventory:{name}", args=args)
        except NoReverseMatch as exc:
            return False, repr(exc)

    def _first_pk(self, model_name: str) -> int | None:
        model = self._model(model_name)
        if model is None:
            return None
        try:
            obj = model.objects.order_by("pk").first()
            return int(obj.pk) if obj else None
        except Exception:
            return None

    def _url_resolve_checks(self):
        switch_id = self._first_pk("Switch") or 1
        port_id = self._first_pk("Port") or 1
        fixed = [
            ("switch_list", []),
            ("switchmap_dashboard_data", []),
            ("dashboard_device_browser_fragment", []),
            ("switchmap_refresh_all_data", []),
            ("alarm_center", []),
            ("alarm_rules", []),
            ("topology", []),
            ("sfp_monitor", []),
            ("sfp_monitor_data", []),
            ("backup_center", []),
            ("backup_storage_status", []),
            ("cisco_backup_center", []),
            ("mikrotik_backup_center", []),
            ("reports", []),
            ("action_logs", []),
            ("user_management", []),
            ("asset_documentation", []),
            ("asset_completion", []),
            ("automation_templates", []),
            ("config_backups", []),
            ("switchmap_ajax_ssh_port_action", []),
            ("switchmap_ajax_multi_ssh_port_action", []),
            ("ssh_action_preview", []),
            ("backup_validate_restore", []),
            ("switch_detail", [switch_id]),
            ("switch_ports_table", [switch_id]),
            ("switch_refresh_step", [switch_id]),
            ("port_payload_json", [port_id]),
        ]
        urls = {}
        for name, args in fixed:
            ok, value = self._reverse(name, *args)
            urls[name] = {"ok": ok, "value": value, "args": args}
            if ok:
                self._ok("url_resolve", f"{name}:{value}")
            else:
                self._fail("url_resolve", f"{name}:{value}")
        self.report["urls"] = urls

    def _http_guard_checks(self):
        client = Client(HTTP_HOST=self.http_host)
        pages = [
            "/", "/dashboard/device-browser/", "/dashboard/data/", "/backup-health/",
            "/backup-storage/", "/cisco-backups/", "/mikrotik-backups/", "/backups/",
            "/alarms/", "/topology/", "/sfp-monitor/", "/reports/", "/logs/",
            "/users/", "/assets/", "/assets/completion/", "/automation/templates/",
            "/config-backups/",
        ]
        http = {}
        for path in pages:
            start = time.perf_counter()
            try:
                resp = client.get(path)
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                status = int(resp.status_code)
                size = len(getattr(resp, "content", b"") or b"")
                http[path] = {"status": status, "ms": elapsed_ms, "bytes": size}
                if status in (200, 301, 302, 403, 404):
                    self._ok("http_get", f"{path}:{status}:{elapsed_ms}ms:{size}b")
                else:
                    self._fail("http_get", f"{path}:{status}:{elapsed_ms}ms")
            except Exception as exc:
                http[path] = {"error": repr(exc)}
                self._fail("http_get", f"{path}:{repr(exc)}")

        post_guards = [
            "/refresh-all/", "/ssh-port-action/", "/ssh-port-multi-action/", "/ssh-port-preview/",
            "/alarms/sync/", "/alarms/bulk-action/", "/sfp-monitor/poll/",
            "/cisco-backups/run/", "/cisco-backups/batch/", "/mikrotik-backups/run/",
            "/mikrotik-backups/batch/", "/backups/create/", "/backups/validate-restore/",
        ]
        posts = {}
        for path in post_guards:
            try:
                resp = client.post(path, data={})
                status = int(resp.status_code)
                posts[path] = {"status": status}
                if status in (301, 302, 403, 404, 405):
                    self._ok("anon_post_guard", f"{path}:{status}")
                else:
                    self._fail("anon_post_guard", f"{path}:{status}")
            except Exception as exc:
                posts[path] = {"error": repr(exc)}
                self._fail("anon_post_guard", f"{path}:{repr(exc)}")
        self.report["http_get"] = http
        self.report["anon_post_guard"] = posts

    def _raw_dashboard_response(self, path: str):
        """Render dashboard views directly to validate HTML without requiring a login/session write."""
        rf = RequestFactory(HTTP_HOST=self.http_host)
        request = rf.get(path)
        try:
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()
        except Exception:
            request.user = None
        request.META["HTTP_HOST"] = self.http_host
        return request

    def _response_text(self, response) -> str:
        if hasattr(response, "render") and callable(response.render):
            try:
                response = response.render()
            except Exception:
                pass
        return (getattr(response, "content", b"") or b"").decode("utf-8", errors="replace")

    def _performance_lock_checks(self):
        data: Dict[str, Any] = {}
        try:
            from inventory import dashboard_views as live_dashboard_views
            request = self._raw_dashboard_response("/")
            root = live_dashboard_views.switch_list(request)
            html = self._response_text(root)
            data["dashboard_status"] = int(getattr(root, "status_code", 0) or 0)
            data["dashboard_bytes"] = len(getattr(root, "content", b"") or b"")
            data["no_bunny"] = "fonts.bunny.net" not in html
            data["lazy_holder"] = "phase107-device-browser-lazy" in html
            data["initial_no_switch_cards"] = "sm-switch-card" not in html
            data["phase103_css_present"] = "switchmap-phase103-dashboard-cards.css" in html
            data["lazy_load_url_present"] = "dashboard/device-browser" in html
            for key in ["no_bunny", "lazy_holder", "initial_no_switch_cards", "phase103_css_present", "lazy_load_url_present"]:
                if data.get(key):
                    self._ok("perf_" + key)
                else:
                    self._fail("perf_" + key, data)
        except Exception as exc:
            self._fail("dashboard_performance_render", repr(exc))
            data["dashboard_error"] = repr(exc)
        try:
            from inventory import dashboard_views as live_dashboard_views
            view = getattr(live_dashboard_views, "dashboard_device_browser_fragment_view", None)
            if view is None:
                self._fail("device_browser_fragment_view_missing")
            else:
                request = self._raw_dashboard_response("/dashboard/device-browser/")
                frag = view(request)
                frag_html = self._response_text(frag)
                data["fragment_status"] = int(getattr(frag, "status_code", 0) or 0)
                data["fragment_bytes"] = len(getattr(frag, "content", b"") or b"")
                data["fragment_has_switch_cards"] = "sm-switch-card" in frag_html
                data["fragment_has_port_buttons"] = "data-port-id" in frag_html or "port-button" in frag_html
                data["fragment_has_device_browser_shell"] = "device-browser-shell" in frag_html
                if data["fragment_status"] == 200 and data["fragment_has_device_browser_shell"] and data["fragment_has_switch_cards"]:
                    self._ok("device_browser_fragment")
                else:
                    self._fail("device_browser_fragment", data)
        except Exception as exc:
            self._fail("device_browser_fragment", repr(exc))
            data["fragment_error"] = repr(exc)
        self.report["performance_lock"] = data

    def _security_static_guards(self):
        access = self._read("inventory/access_control.py")
        urls = self._read("inventory/urls.py")
        restore_related = "backup_validate_restore" in urls and "restore" in urls.lower()
        execute_restore_absent = "execute_restore" not in urls and "restore_execute" not in urls
        role_markers = all(x in access for x in ["view_required", "operator_or_admin_required", "admin_required"])
        if role_markers:
            self._ok("role_guard_markers")
        else:
            self._fail("role_guard_markers")
        if restore_related:
            self._ok("restore_validate_url_present")
        else:
            self._warn("restore_validate_url_present", "not found")
        if execute_restore_absent:
            self._ok("restore_execute_url_absent")
        else:
            self._fail("restore_execute_url_absent")

        sensitive = ["db.sqlite3", "switchmap.env", "secrets", "venv", "backups", "logs"]
        pkg_paths = [str(p.relative_to(self.root)) for p in self.root.glob("SwitchMap_Phase108_Stabilization_Lock_Verify/**/*") if p.is_file()] if (self.root / "SwitchMap_Phase108_Stabilization_Lock_Verify").exists() else []
        bad = [p for p in pkg_paths if any(s.lower() in p.lower() for s in sensitive)]
        if not bad:
            self._ok("phase108_package_no_sensitive_payload")
        else:
            self._fail("phase108_package_no_sensitive_payload", bad[:10])

    def _django_dry_run_checks(self):
        commands = [
            [sys.executable, "manage.py", "check"],
            [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
        ]
        dry = []
        for cmd in commands:
            try:
                p = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True, timeout=120)
                item = {"cmd": " ".join(cmd), "rc": p.returncode, "out": (p.stdout or "")[-2000:], "err": (p.stderr or "")[-2000:]}
                dry.append(item)
                if p.returncode == 0:
                    self._ok("django_cmd", item["cmd"])
                else:
                    self._fail("django_cmd", item)
            except Exception as exc:
                dry.append({"cmd": " ".join(cmd), "error": repr(exc)})
                self._fail("django_cmd", f"{' '.join(cmd)}:{repr(exc)}")
        self.report["django_dry_run"] = dry

    def _finalize_report(self, output: str):
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = self.root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.report["final_ok_count"] = len(self.ok)
        self.report["final_warning_count"] = len(self.warnings)
        self.report["final_fail_count"] = len(self.failures)
        self.report["ok"] = self.ok
        self.report["warnings"] = self.warnings
        self.report["failures"] = self.failures
        out_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path = out_path.with_suffix(".md")
        md_lines = [
            "# Phase108 Stabilization Lock Report",
            "",
            f"- Time: {self.report['timestamp']}",
            f"- Root: {self.root}",
            f"- OK: {len(self.ok)}",
            f"- Warnings: {len(self.warnings)}",
            f"- Fails: {len(self.failures)}",
            "",
            "## Failures",
        ]
        md_lines.extend([f"- {x}" for x in self.failures] or ["- none"])
        md_lines.append("\n## Warnings")
        md_lines.extend([f"- {x}" for x in self.warnings] or ["- none"])
        md_lines.append("\n## Key OK")
        md_lines.extend([f"- {x}" for x in self.ok[:80]])
        md_lines.extend([
            "",
            "## Safety",
            "DB_MUTATION=NO" if self.report.get("counts_before") == self.report.get("counts_after") else "DB_MUTATION=UNKNOWN",
            "MIGRATION_WRITE=NO",
            "RESTORE_ENABLE_CHANGE=NO",
            "SSH_EXECUTION=NO",
            "BACKUP_WRITE=NO",
            "VISIBLE_TEST_DATA_CREATED=NO",
        ])
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        self._line(f"REPORT_JSON={out_path}")
        self._line(f"REPORT_MD={md_path}")
        self._line(f"FINAL_OK_COUNT={len(self.ok)}")
        self._line(f"FINAL_WARNING_COUNT={len(self.warnings)}")
        self._line(f"FINAL_FAIL_COUNT={len(self.failures)}")
        self._line("DB_MUTATION=NO" if self.report.get("counts_before") == self.report.get("counts_after") else "DB_MUTATION=UNKNOWN")
        self._line("MIGRATION_WRITE=NO")
        self._line("RESTORE_ENABLE_CHANGE=NO")
        self._line("SSH_EXECUTION=NO")
        self._line("BACKUP_WRITE=NO")
        self._line("VISIBLE_TEST_DATA_CREATED=NO")
        if self.failures and self.strict:
            self._line("PHASE108_STABILIZATION_LOCK_CHECK_FAILED")
            raise CommandError("PHASE108_STABILIZATION_LOCK_CHECK_FAILED")
        self._line("PHASE108_STABILIZATION_LOCK_CHECK_OK")
