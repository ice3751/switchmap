from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import NoReverseMatch, reverse

PHASE = "PHASE98_100"


def count_defs(source: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for match in re.finditer(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source, flags=re.MULTILINE):
        name = match.group(1)
        counts[name] = counts.get(name, 0) + 1
    return counts


def add(results: List[Dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


class Command(BaseCommand):
    help = "Phase98-100 final safe refine and release lock verification. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        results: List[Dict[str, Any]] = []
        self.stdout.write("PHASE98_100_FINAL_RELEASE_LOCK_CHECK_START")
        self.stdout.write("MODE=read_only_no_db_write_no_network_no_ssh_no_restore_no_service")

        alarm_policy = root / "inventory" / "alarm_policy.py"
        alarm_source = read_text(alarm_policy)
        counts = count_defs(alarm_source)
        expected_single = [
            "alarm_is_false_positive",
            "is_actionable_port_error",
            "is_actionable_interface_down",
            "is_explicitly_critical_port",
        ]
        add(results, "alarm_policy_marker", "PHASE98_CANONICAL_ALARM_POLICY" in alarm_source)
        for name in expected_single:
            add(results, f"alarm_policy_single_def:{name}", counts.get(name, 0) == 1, f"count={counts.get(name, 0)}")

        views_path = root / "inventory" / "views.py"
        views = read_text(views_path)
        add(results, "restore_safety_marker", "PHASE99_RESTORE_VALIDATE_SAFETY_GUARD" in views)
        add(results, "download_uses_fileresponse", "FileResponse" in views and "backup_download_view" in views)
        add(results, "restore_upload_limit_constant", "RESTORE_CANDIDATE_MAX_UPLOAD_BYTES" in views)
        add(results, "restore_zip_uncompressed_limit_constant", "RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES" in views)
        segment_match = re.search(r"def\s+backup_download_view\s*\(.*?\n\s*return\s+response\n", views, flags=re.DOTALL)
        segment = segment_match.group(0) if segment_match else ""
        add(results, "backup_download_no_read_bytes", "read_bytes" not in segment and "FileResponse" in segment)
        add(results, "path_containment_uses_relative_to", ".relative_to(" in views)
        add(results, "invalid_restore_candidate_cleanup", "restore_candidate_invalid_deleted" in views)

        try:
            validate_url = reverse("inventory:backup_validate_restore")
            add(results, "restore_validate_url", validate_url == "/backups/validate-restore/", validate_url)
        except NoReverseMatch as exc:
            add(results, "restore_validate_url", False, str(exc))
        try:
            reverse("inventory:backup_restore_execute")
            add(results, "restore_execute_url_absent", False, "unexpected route exists")
        except NoReverseMatch:
            add(results, "restore_execute_url_absent", True)

        requirements = read_text(root / "requirements.txt")
        add(results, "whitenoise_pinned", bool(re.search(r"(?im)^\s*whitenoise\s*==\s*6\.12\.0\s*$", requirements)))

        gitignore = read_text(root / ".gitignore")
        required_gitignore = ["secrets/", "*.dpapi", "project_snapshots/", "_phase91_backup/", "_phase91_quarantine/"]
        missing_gitignore = [item for item in required_gitignore if item not in gitignore]
        add(results, "gitignore_sensitive_patterns", not missing_gitignore, ",".join(missing_gitignore))

        source_scan = read_text(root / "scripts" / "phase77_make_safe_source_zip.py")
        snapshot_scan = read_text(root / "smoke_tests" / "switchmap_project_source_snapshot.py")
        add(results, "safe_source_script_check_only", "--check-only" in source_scan and "SAFE_SOURCE_SCAN_OK" in source_scan)
        add(results, "source_snapshot_script_check_only", "--check-only" in snapshot_scan and "PROJECT_SOURCE_SNAPSHOT_SCAN_OK" in snapshot_scan)

        failures = [item for item in results if not item["ok"]]
        report = {
            "phase": PHASE,
            "root": str(root),
            "results": results,
            "fail_count": len(failures),
            "final_ok": len(failures) == 0,
            "db_mutation": "NO",
            "service_restart": "NO",
            "migration_write": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
            "visible_test_data_created": "NO",
        }

        output = options.get("output") or ""
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            md = path.with_suffix(".md")
            lines = [
                "# Phase98-100 Final Release Lock Report",
                "",
                f"- Final OK: {report['final_ok']}",
                f"- Fail Count: {report['fail_count']}",
                "",
                "| Check | OK | Detail |",
                "|---|---:|---|",
            ]
            for item in results:
                lines.append(f"| {item['name']} | {item['ok']} | `{item.get('detail','')}` |")
            lines += [
                "",
                "DB_MUTATION=NO",
                "SERVICE_RESTART=NO",
                "MIGRATION_WRITE=NO",
                "RESTORE_ENABLE_CHANGE=NO",
                "SSH_EXECUTION=NO",
                "BACKUP_WRITE=NO",
                "VISIBLE_TEST_DATA_CREATED=NO",
            ]
            md.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.stdout.write(f"REPORT_JSON={path}")
            self.stdout.write(f"REPORT_MD={md}")

        for item in results:
            prefix = "OK" if item["ok"] else "FAIL"
            detail = f":{item['detail']}" if item.get("detail") else ""
            self.stdout.write(f"{prefix}={item['name']}{detail}")
        self.stdout.write(f"FINAL_FAIL_COUNT={len(failures)}")
        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("SERVICE_RESTART=NO")
        self.stdout.write("MIGRATION_WRITE=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("BACKUP_WRITE=NO")
        self.stdout.write("VISIBLE_TEST_DATA_CREATED=NO")

        if failures:
            self.stdout.write("PHASE98_100_FINAL_RELEASE_LOCK_CHECK_FAIL")
            raise CommandError("Phase98-100 final release lock check failed")
        self.stdout.write("PHASE98_100_FINAL_RELEASE_LOCK_CHECK_OK")
