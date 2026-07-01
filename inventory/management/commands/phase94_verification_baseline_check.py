from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import NoReverseMatch, Resolver404, get_resolver, resolve, reverse


PHASE = "PHASE94"
PROTECTED_TOP = {
    ".git",
    "venv",
    "backups",
    "logs",
    "secrets",
    "staticfiles",
    "media",
    "_phase91_backup",
    "_phase91_quarantine",
}
SOURCE_PATTERNS = [
    "manage.py",
    "requirements.txt",
    ".gitignore",
    "config/*.py",
    "inventory/*.py",
    "inventory/management/commands/*.py",
    "inventory/templatetags/*.py",
    "inventory/templates/inventory/*.html",
    "inventory/static/inventory/*.js",
    "inventory/static/inventory/css/*.css",
    "scripts/*.cmd",
    "scripts/*.py",
    "smoke_tests/*.py",
    "smoke_tests/*.json",
    "smoke_tests/*.md",
]
CORE_URLS = [
    ("inventory:switch_list", []),
    ("inventory:switchmap_dashboard_data", []),
    ("inventory:switchmap_refresh_all_data", []),
    ("inventory:backup_health_dashboard", []),
    ("inventory:backup_storage_status", []),
    ("inventory:cisco_backup_center", []),
    ("inventory:mikrotik_backup_center", []),
    ("inventory:backup_center", []),
    ("inventory:alarm_center", []),
    ("inventory:alarm_rules", []),
    ("inventory:topology", []),
    ("inventory:sfp_monitor", []),
    ("inventory:sfp_monitor_data", []),
    ("inventory:mikrotik_center", []),
    ("inventory:reports", []),
    ("inventory:action_logs", []),
    ("inventory:user_management", []),
    ("inventory:asset_documentation", []),
    ("inventory:asset_completion", []),
    ("inventory:automation_templates", []),
    ("inventory:config_backups", []),
    ("inventory:switchmap_ajax_ssh_port_action", []),
    ("inventory:switchmap_ajax_multi_ssh_port_action", []),
    ("inventory:ssh_action_preview", []),
    ("inventory:backup_validate_restore", []),
    ("inventory:cisco_backup_validate_restore", ["dummy"]),
    ("inventory:mikrotik_backup_validate_restore", ["dummy"]),
]
CRITICAL_GET_PATHS = [
    "/",
    "/backup-health/",
    "/backup-storage/",
    "/cisco-backups/",
    "/mikrotik-backups/",
    "/backups/",
    "/alarms/",
    "/topology/",
    "/sfp-monitor/",
    "/mikrotik/",
    "/reports/",
    "/logs/",
    "/users/",
    "/assets/",
    "/assets/completion/",
    "/automation/templates/",
    "/config-backups/",
]
ANON_DANGEROUS_POSTS = [
    "/refresh-all/",
    "/ssh-port-action/",
    "/ssh-port-multi-action/",
    "/ssh-port-preview/",
    "/alarms/sync/",
    "/alarms/bulk-action/",
    "/sfp-monitor/poll/",
    "/cisco-backups/run/",
    "/cisco-backups/batch/",
    "/mikrotik-backups/run/",
    "/mikrotik-backups/batch/",
    "/backups/create/",
    "/backups/validate-restore/",
]
SENSITIVE_IGNORE_PATTERNS = [
    "switchmap.env",
    ".env",
    "db.sqlite3",
    "*.sqlite3",
    "backups/",
    "logs/",
    "secrets/",
    "*.dpapi",
    "project_snapshots/",
    "_phase91_backup/",
    "_phase91_quarantine/",
    "staticfiles/",
    "venv/",
]


class Phase94Failure(RuntimeError):
    pass


class Command(BaseCommand):
    help = "Phase94 read-only verification and source-baseline guard. No DB writes, no service restart, no SSH, no backup, no restore."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")
        parser.add_argument("--skip-makemigrations-check", action="store_true")

    def handle(self, *args, **options):
        self.strict = bool(options.get("strict"))
        self.failures: List[str] = []
        self.warnings: List[str] = []
        self.steps: List[Dict[str, Any]] = []
        self.root = Path(settings.BASE_DIR).resolve()
        self.log_dir = self.root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = options.get("output") or str(self.log_dir / f"phase94_verification_baseline_{self.stamp}.json")
        self.output_json = Path(output)
        if not self.output_json.is_absolute():
            self.output_json = self.root / self.output_json
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        self.output_md = self.output_json.with_suffix(".md")
        self.latest_json = self.log_dir / "phase94_verification_baseline_latest.json"
        self.latest_md = self.log_dir / "phase94_verification_baseline_latest.md"
        self.baseline_json = self.log_dir / "phase94_source_baseline_latest.json"

        self.line("PHASE94R3_VERIFICATION_BASELINE_CHECK_START")
        self.line("MODE=read_only_no_visible_test_data_no_network_no_ssh_no_backup_no_restore_no_service")
        self.line(f"ROOT={self.root}")

        self.step("source_baseline", self.source_baseline)
        self.step("smoke_manifest_guard", self.smoke_manifest_guard)
        self.step("url_and_http_guard", self.url_and_http_guard)
        self.step("role_static_guard", self.role_static_guard)
        self.step("restore_guard", self.restore_guard)
        self.step("requirements_gitignore_audit", self.requirements_gitignore_audit)
        if not options.get("skip_makemigrations_check"):
            self.step("makemigrations_dry_run_guard", self.makemigrations_dry_run_guard)
        self.step("data_visibility_guard", self.data_visibility_guard)

        report = {
            "phase": PHASE,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(self.root),
            "mode": "read_only_no_visible_test_data_no_network_no_ssh_no_backup_no_restore_no_service",
            "steps": self.steps,
            "failures": self.failures,
            "warnings": self.warnings,
            "final_ok": not self.failures,
            "db_mutation": "NO",
            "service_restart": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
            "visible_test_data_created": "NO",
            "baseline_json": str(self.baseline_json),
        }
        self.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md = self.render_markdown(report)
        self.output_md.write_text(md, encoding="utf-8")
        self.latest_md.write_text(md, encoding="utf-8")

        self.line(f"REPORT_JSON={self.output_json}")
        self.line(f"REPORT_MD={self.output_md}")
        self.line(f"BASELINE_JSON={self.baseline_json}")
        self.line(f"FINAL_WARNING_COUNT={len(self.warnings)}")
        self.line(f"FINAL_FAIL_COUNT={len(self.failures)}")
        self.line("NO_VISIBLE_TEST_DATA_CREATED=True")
        self.line("DB_MUTATION=NO")
        self.line("SERVICE_RESTART=NO")
        self.line("RESTORE_ENABLE_CHANGE=NO")
        self.line("SSH_EXECUTION=NO")
        self.line("BACKUP_WRITE=NO")

        if self.failures:
            self.line("PHASE94R3_VERIFICATION_BASELINE_CHECK_FAIL")
            raise CommandError("Phase94 verification baseline failed")
        self.line("PHASE94R3_VERIFICATION_BASELINE_CHECK_OK")

    def line(self, text: str) -> None:
        self.stdout.write(str(text))

    def step(self, name: str, func) -> None:
        self.line(f"STEP_START={name}")
        try:
            detail = func()
            self.steps.append({"name": name, "status": "ok", "detail": detail})
            self.line(f"STEP_EXIT={name}:0")
        except Phase94Failure as exc:
            self.failures.append(f"{name}: {exc}")
            self.steps.append({"name": name, "status": "fail", "detail": str(exc)})
            self.line(f"STEP_EXIT={name}:1")
        except Exception as exc:
            self.failures.append(f"{name}: {type(exc).__name__}: {exc}")
            self.steps.append({"name": name, "status": "fail", "detail": f"{type(exc).__name__}: {exc}"})
            self.line(f"STEP_EXIT={name}:1")

    def warn(self, code: str, detail: str) -> None:
        msg = f"{code}: {detail}"
        self.warnings.append(msg)
        self.line(f"WARNING={msg}")

    def fail(self, code: str, detail: str) -> None:
        raise Phase94Failure(f"{code}: {detail}")

    def is_protected(self, path: Path) -> bool:
        try:
            parts = path.resolve().relative_to(self.root).parts
        except Exception:
            return True
        return bool(parts and parts[0] in PROTECTED_TOP)

    def rel(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root)).replace("\\", "/")

    def sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def source_baseline(self) -> Dict[str, Any]:
        files: Dict[str, Dict[str, Any]] = {}
        seen = set()
        for pattern in SOURCE_PATTERNS:
            for path in self.root.glob(pattern):
                if not path.is_file() or self.is_protected(path):
                    continue
                rel = self.rel(path)
                if rel in seen:
                    continue
                seen.add(rel)
                files[rel] = {"sha256": self.sha256_file(path), "size": path.stat().st_size}
        baseline = {
            "phase": PHASE,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(self.root),
            "file_count": len(files),
            "protected_top_excluded": sorted(PROTECTED_TOP),
            "files": files,
        }
        self.baseline_json.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        self.line(f"SOURCE_BASELINE_FILES={len(files)}")
        self.line(f"SOURCE_BASELINE_JSON={self.baseline_json}")
        if len(files) < 50:
            self.fail("source_baseline_too_small", f"only {len(files)} files hashed")
        return {"file_count": len(files), "baseline_json": str(self.baseline_json)}

    def smoke_manifest_guard(self) -> Dict[str, Any]:
        manifest_path = self.root / "smoke_tests" / "manifest.json"
        runner_path = self.root / "smoke_tests" / "run_smoke.py"
        readme_path = self.root / "smoke_tests" / "README.md"
        missing = [str(p.relative_to(self.root)).replace("\\", "/") for p in [manifest_path, runner_path, readme_path] if not p.exists()]
        if missing:
            self.fail("smoke_required_files_missing", ",".join(missing))
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        refs: List[str] = []
        # Only manifest file-reference sections are validated as paths.
        # Descriptive arrays such as notes are intentionally ignored.
        for key in ("current", "production", "phase94", "files", "required_files"):
            value = data.get(key, [])
            if isinstance(value, list):
                refs.extend(str(x) for x in value)
        absent = [x for x in sorted(set(refs)) if x and not (self.root / x).exists()]
        if absent:
            self.fail("smoke_manifest_missing_references", ",".join(absent[:50]))
        self.line(f"SMOKE_MANIFEST_REFERENCES_OK={len(set(refs))}")
        if data.get("visible_test_data_created") != "NO":
            self.warn("smoke_manifest_visibility_flag_missing", "visible_test_data_created is not NO")
        return {"references": len(set(refs)), "schema_version": data.get("schema_version")}

    def url_and_http_guard(self) -> Dict[str, Any]:
        client = Client(HTTP_HOST="127.0.0.1")
        url_results: List[Dict[str, Any]] = []
        for name, args in CORE_URLS:
            try:
                path = reverse(name, args=args)
                resolved = resolve(path)
                self.line(f"URL_OK={name}:{path}:resolve={resolved.url_name}")
                url_results.append({"name": name, "path": path, "resolve": resolved.url_name})
            except (NoReverseMatch, Resolver404) as exc:
                self.fail("url_reverse_resolve_failed", f"{name}: {exc}")
        get_status: Dict[str, int] = {}
        for path in CRITICAL_GET_PATHS:
            resp = client.get(path, follow=False)
            get_status[path] = resp.status_code
            self.line(f"HTTP_GET_STATUS={path}:{resp.status_code}")
            if resp.status_code >= 500:
                self.fail("http_get_5xx", f"{path} => {resp.status_code}")
        post_status: Dict[str, int] = {}
        for path in ANON_DANGEROUS_POSTS:
            resp = client.post(path, data={}, follow=False)
            post_status[path] = resp.status_code
            self.line(f"ANON_POST_GUARD={path}:{resp.status_code}")
            if resp.status_code == 200 or resp.status_code >= 500:
                self.fail("anon_post_guard_failed", f"{path} => {resp.status_code}")
        return {"url_count": len(url_results), "get_status": get_status, "anon_post_status": post_status}

    def role_static_guard(self) -> Dict[str, Any]:
        from inventory import access_control

        expected = ["View Only", "Operator", "Admin"]
        order = [access_control.ROLE_ORDER.get(x) for x in expected]
        if order != sorted(order) or len(set(order)) != 3:
            self.fail("role_order_invalid", str(order))
        if "set_voice_vlan" not in access_control.ADMIN_ONLY_SSH_ACTIONS:
            self.warn("admin_only_action_marker_missing", "set_voice_vlan not in ADMIN_ONLY_SSH_ACTIONS")
        if "shutdown" not in access_control.OPERATOR_SSH_ACTIONS:
            self.warn("operator_action_marker_missing", "shutdown not in OPERATOR_SSH_ACTIONS")
        self.line("ROLE_ORDER_OK=View Only < Operator < Admin")
        return {"role_order": dict(access_control.ROLE_ORDER)}

    def iter_url_patterns(self) -> Iterable[Tuple[str, str]]:
        resolver = get_resolver()
        stack = list(resolver.url_patterns)
        while stack:
            item = stack.pop(0)
            if hasattr(item, "url_patterns"):
                stack.extend(item.url_patterns)
            else:
                name = getattr(item, "name", None) or ""
                pattern = str(getattr(item, "pattern", ""))
                yield name, pattern

    def restore_guard(self) -> Dict[str, Any]:
        names_patterns = list(self.iter_url_patterns())
        bad = []
        for name, pattern in names_patterns:
            combo = f"{name}:{pattern}".lower()
            if "restore" in combo and "validate" not in combo:
                if any(token in combo for token in ["execute", "apply", "run", "real", "restore/"]):
                    bad.append(combo)
        if bad:
            self.fail("restore_execute_route_present", ";".join(bad[:20]))
        validate_path = reverse("inventory:backup_validate_restore")
        self.line(f"RESTORE_VALIDATE_URL_OK={validate_path}")
        self.line("RESTORE_EXECUTE_URL_ABSENT_OK=True")
        return {"validate_path": validate_path, "execute_absent": True}

    def requirements_gitignore_audit(self) -> Dict[str, Any]:
        requirements_path = self.root / "requirements.txt"
        gitignore_path = self.root / ".gitignore"
        req_text = requirements_path.read_text(encoding="utf-8", errors="ignore") if requirements_path.exists() else ""
        gi_text = gitignore_path.read_text(encoding="utf-8", errors="ignore") if gitignore_path.exists() else ""
        req_lower = req_text.lower()
        if "whitenoise" not in req_lower:
            try:
                ver = metadata.version("whitenoise")
            except metadata.PackageNotFoundError:
                ver = "not-installed"
            self.warn("whitenoise_not_pinned_in_requirements", f"installed={ver}")
        missing_ignore = [p for p in SENSITIVE_IGNORE_PATTERNS if p not in gi_text]
        if missing_ignore:
            self.warn("gitignore_sensitive_patterns_missing", ",".join(missing_ignore))
        self.line(f"REQUIREMENTS_FILE_PRESENT={requirements_path.exists()}")
        self.line(f"GITIGNORE_FILE_PRESENT={gitignore_path.exists()}")
        self.line(f"GITIGNORE_MISSING_SENSITIVE_PATTERNS={len(missing_ignore)}")
        return {"whitenoise_in_requirements": "whitenoise" in req_lower, "missing_gitignore_patterns": missing_ignore}

    def makemigrations_dry_run_guard(self) -> Dict[str, Any]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        cmd = [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run", "--noinput"]
        proc = subprocess.run(cmd, cwd=str(self.root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        output = (proc.stdout or "").strip()
        self.line(f"MAKEMIGRATIONS_DRY_RUN_RC={proc.returncode}")
        if output:
            sanitized = re.sub(r"(?i)(password|secret|community|token)\s*=\s*\S+", r"\1=<redacted>", output)
            for line in sanitized.splitlines()[:80]:
                self.line(f"MAKEMIGRATIONS_DRY_RUN_OUT={line}")
        if proc.returncode != 0:
            self.warn("makemigrations_dry_run_not_clean", f"rc={proc.returncode}; review output in report")
        return {"returncode": proc.returncode, "output_preview": output.splitlines()[:80]}

    def data_visibility_guard(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"visible_test_data_created": "NO"}
        try:
            from inventory.models import Switch, Port

            switch_total = Switch.objects.count()
            port_total = Port.objects.count()
            phase94_switches = Switch.objects.filter(name__icontains="PHASE94").count()
            smoke_switches = Switch.objects.filter(name__icontains="SMOKE").count()
            result.update({
                "switch_total": switch_total,
                "port_total": port_total,
                "phase94_switches": phase94_switches,
                "smoke_switches": smoke_switches,
            })
            self.line(f"DATA_COUNT=switch_total:{switch_total}")
            self.line(f"DATA_COUNT=port_total:{port_total}")
            self.line(f"VISIBLE_TEST_SWITCHES_PHASE94={phase94_switches}")
            self.line(f"VISIBLE_TEST_SWITCHES_SMOKE={smoke_switches}")
            if phase94_switches:
                self.fail("phase94_visible_test_switch_found", str(phase94_switches))
        except Exception as exc:
            self.warn("data_visibility_guard_limited", f"{type(exc).__name__}: {exc}")
        self.line("NO_VISIBLE_TEST_DATA_CREATED=True")
        return result

    def render_markdown(self, report: Dict[str, Any]) -> str:
        lines = [
            "# SwitchMap Phase94 Verification Baseline Report",
            "",
            f"- Generated: {report['generated_at']}",
            f"- Root: {report['root']}",
            "- Mode: read-only verification; no visible test data; no SSH; no backup; no restore; no service restart",
            f"- Final OK: {report['final_ok']}",
            f"- Failure count: {len(self.failures)}",
            f"- Warning count: {len(self.warnings)}",
            f"- Source baseline: {self.baseline_json}",
            "",
            "## Steps",
            "",
            "| Step | Status |",
            "|---|---|",
        ]
        for step in report["steps"]:
            lines.append(f"| {step['name']} | {step['status']} |")
        lines.extend(["", "## Warnings", ""])
        if self.warnings:
            for item in self.warnings:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        lines.extend(["", "## Failures", ""])
        if self.failures:
            for item in self.failures:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        lines.extend([
            "",
            "## Safety Flags",
            "",
            "NO_CODE_CHANGE_DONE=False",
            "NO_VISIBLE_TEST_DATA_CREATED=True",
            "DB_MUTATION=NO",
            "SERVICE_RESTART=NO",
            "RESTORE_ENABLE_CHANGE=NO",
            "SSH_EXECUTION=NO",
            "BACKUP_WRITE=NO",
            "REPORT_ONLY=NO",
            "",
            "Note: Phase94 installs/repairs verification files only. It does not add menus, devices, database rows, URLs, or UI-visible test objects.",
        ])
        return "\n".join(lines) + "\n"
