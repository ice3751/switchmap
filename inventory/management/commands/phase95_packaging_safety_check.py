from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Phase95 read-only packaging/dependency safety guard. No DB, service, SSH, backup, or restore action."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        root = Path.cwd().resolve()
        strict = bool(options.get("strict"))
        output = options.get("output") or ""
        report: dict[str, Any] = {
            "phase": "PHASE95",
            "mode": "read_only_packaging_dependency_guard_no_db_no_service_no_restore_no_ssh",
            "root": str(root),
            "checks": [],
            "warnings": [],
            "failures": [],
            "db_mutation": "NO",
            "service_restart": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
        }

        def log(text: str) -> None:
            self.stdout.write(text)

        def ok(name: str, detail: Any = None) -> None:
            report["checks"].append({"name": name, "status": "ok", "detail": detail})
            if detail is None:
                log(f"OK={name}")
            else:
                log(f"OK={name}:{detail}")

        def warn(name: str, detail: Any = None) -> None:
            report["warnings"].append({"name": name, "detail": detail})
            log(f"WARNING={name}:{detail}")

        def fail(name: str, detail: Any = None) -> None:
            report["failures"].append({"name": name, "detail": detail})
            log(f"FAIL={name}:{detail}")

        log("PHASE95_PACKAGING_SAFETY_CHECK_START")
        log("MODE=read_only_packaging_dependency_guard_no_db_no_service_no_restore_no_ssh")
        log(f"ROOT={root}")

        req_path = root / "requirements.txt"
        gitignore_path = root / ".gitignore"
        safe_zip_path = root / "scripts" / "phase77_make_safe_source_zip.py"
        snapshot_path = root / "smoke_tests" / "switchmap_project_source_snapshot.py"

        # requirements.txt guard
        if not req_path.exists():
            fail("requirements_missing", str(req_path))
        else:
            req_lines = [line.strip() for line in req_path.read_text(encoding="utf-8", errors="replace").splitlines()]
            whitenoise_lines = [line for line in req_lines if line.lower().startswith("whitenoise==")]
            if not whitenoise_lines:
                fail("whitenoise_not_pinned_in_requirements", "missing")
            else:
                pinned = whitenoise_lines[0].split("==", 1)[1]
                try:
                    installed = metadata.version("whitenoise")
                except metadata.PackageNotFoundError:
                    installed = "NOT_INSTALLED"
                if installed != "NOT_INSTALLED" and pinned != installed:
                    fail("whitenoise_pin_mismatch", f"pinned={pinned};installed={installed}")
                else:
                    ok("whitenoise_pinned", f"pinned={pinned};installed={installed}")

        # .gitignore guard
        required_gitignore = [
            "switchmap.env",
            "db.sqlite3",
            "secrets/",
            "*.dpapi",
            "project_snapshots/",
            "_phase91_backup/",
            "_phase91_quarantine/",
            "restore_candidates/",
            "dist/",
            "*.sqlite",
            "*.db",
        ]
        if not gitignore_path.exists():
            fail("gitignore_missing", str(gitignore_path))
        else:
            gitignore_lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.strip().startswith("#")}
            missing = [item for item in required_gitignore if item not in gitignore_lines]
            if missing:
                fail("gitignore_sensitive_patterns_missing", ",".join(missing))
            else:
                ok("gitignore_sensitive_patterns", len(required_gitignore))

        # script source markers
        script_checks = [
            (safe_zip_path, ["DENY_DIR_NAMES", "DENY_PREFIX_DIRS", "DENY_PATTERNS", "--check-only", "SAFE_SOURCE_SCAN_OK"]),
            (snapshot_path, ["DENY_DIR_NAMES", "DENY_PREFIX_DIRS", "--check-only", "PROJECT_SOURCE_SNAPSHOT_SCAN_OK", "shell=False"]),
        ]
        for path, markers in script_checks:
            if not path.exists():
                fail("safety_script_missing", str(path))
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            missing = [marker for marker in markers if marker not in text]
            if missing:
                fail("safety_script_markers_missing", f"{path.relative_to(root)}:{','.join(missing)}")
            else:
                ok("safety_script_markers", str(path.relative_to(root)).replace("\\", "/"))
            if "shell=True" in text:
                fail("shell_true_present", str(path.relative_to(root)).replace("\\", "/"))

        # read-only scans through the hardened tools; they must not create archives/snapshots.
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        scan_commands = [
            ([sys.executable, str(safe_zip_path), "--check-only"], "safe_source_zip_check_only"),
            ([sys.executable, str(snapshot_path), "--check-only"], "source_snapshot_check_only"),
        ]
        for cmd, name in scan_commands:
            if not Path(cmd[1]).exists():
                continue
            proc = subprocess.run(cmd, cwd=str(root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            output_text = (proc.stdout or "").strip()
            if output_text:
                for line in output_text.splitlines():
                    log(line)
            if proc.returncode == 0:
                ok(name, "rc=0")
            else:
                fail(name, f"rc={proc.returncode}")

        final_fail_count = len(report["failures"])
        final_warning_count = len(report["warnings"])
        report["final_fail_count"] = final_fail_count
        report["final_warning_count"] = final_warning_count
        report["final_ok"] = final_fail_count == 0

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"REPORT_JSON={out_path}")

        log(f"FINAL_WARNING_COUNT={final_warning_count}")
        log(f"FINAL_FAIL_COUNT={final_fail_count}")
        log("DB_MUTATION=NO")
        log("SERVICE_RESTART=NO")
        log("RESTORE_ENABLE_CHANGE=NO")
        log("SSH_EXECUTION=NO")
        log("BACKUP_WRITE=NO")

        if strict and final_fail_count:
            log("PHASE95_PACKAGING_SAFETY_CHECK_FAIL")
            raise CommandError("Phase95 packaging safety check failed")
        log("PHASE95_PACKAGING_SAFETY_CHECK_OK")
