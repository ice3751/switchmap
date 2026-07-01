from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand


PHASE90_MARKER = "PHASE90_4_PROJECT_REFINE_AUDIT_SAFE_REVIEWED"


class Command(BaseCommand):
    help = "Phase90 safe project audit/refine. No direct delete; only quarantine obvious generated clutter when requested."

    def add_arguments(self, parser):
        parser.add_argument("--safe-cleanup", action="store_true", help="Quarantine obvious generated clutter such as __pycache__ and *.pyc")
        parser.add_argument("--quarantine", action="store_true", help="Required for cleanup; without it the command only reports")
        parser.add_argument("--json-report", default="", help="Optional report path")

    def handle(self, *args, **options):
        root = Path(getattr(settings, "BASE_DIR", r"C:\SwitchMap"))
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path(options.get("json_report") or logs / "phase90_project_refine_audit_latest.json")
        quarantine_root = root / "backups" / f"phase90_4_quarantine_{ts}"

        protected_dir_names = {"venv", ".git", "node_modules", "backups", "logs", "secrets", ".idea", ".vscode"}
        protected_files = {"db.sqlite3", "manage.py"}
        source_ext = {".py", ".html", ".css", ".js", ".json", ".cmd", ".bat", ".ps1", ".md", ".txt"}
        cleanup_ext = {".pyc", ".pyo", ".tmp"}
        cleanup_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        categories: Dict[str, int] = {}
        cleanup_candidates: List[str] = []
        quarantined: List[str] = []
        skipped_protected: List[str] = []

        def rel(path: Path) -> str:
            return str(path.relative_to(root))

        for current_root, dirnames, filenames in os.walk(root):
            current = Path(current_root)
            kept_dirs = []
            for dirname in dirnames:
                dpath = current / dirname
                if dirname in protected_dir_names:
                    skipped_protected.append(rel(dpath))
                    continue
                if dirname in cleanup_dirs:
                    cleanup_candidates.append(rel(dpath))
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            for filename in filenames:
                path = current / filename
                if path.name in protected_files:
                    skipped_protected.append(rel(path))
                    continue
                suffix = path.suffix.lower()
                r = rel(path)
                if suffix in source_ext:
                    cat = suffix.lstrip(".") or "source"
                elif "backup" in r.lower():
                    cat = "backup_related"
                elif "log" in r.lower():
                    cat = "log_related"
                else:
                    cat = "other"
                categories[cat] = categories.get(cat, 0) + 1
                if suffix in cleanup_ext or path.name.endswith("~"):
                    cleanup_candidates.append(r)

        if options.get("safe_cleanup") and options.get("quarantine"):
            for r in cleanup_candidates:
                src = root / r
                if not src.exists():
                    continue
                dst = quarantine_root / r
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(src), str(dst))
                    quarantined.append(r)
                except Exception as exc:
                    quarantined.append(f"FAILED:{r}:{exc}")

        report = {
            "marker": PHASE90_MARKER,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(root),
            "categories": categories,
            "cleanup_candidates_count": len(cleanup_candidates),
            "cleanup_candidates": cleanup_candidates[:500],
            "quarantine_root": str(quarantine_root) if quarantined else "",
            "quarantined_count": len(quarantined),
            "quarantined": quarantined[:500],
            "skipped_protected_count": len(skipped_protected),
            "skipped_protected_sample": skipped_protected[:200],
            "core_safety": "No direct delete. Protected dirs pruned: venv/.git/node_modules/backups/logs/secrets. Only generated clutter is quarantined.",
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write("PHASE90_4_PROJECT_REFINE_AUDIT_SAFE_REVIEWED_DONE")
        self.stdout.write(f"REPORT={report_path}")
        self.stdout.write(f"CLEANUP_CANDIDATES={len(cleanup_candidates)}")
        self.stdout.write(f"QUARANTINED={len(quarantined)}")
        self.stdout.write(f"SKIPPED_PROTECTED={len(skipped_protected)}")
        if quarantined:
            self.stdout.write(f"QUARANTINE_ROOT={quarantine_root}")
