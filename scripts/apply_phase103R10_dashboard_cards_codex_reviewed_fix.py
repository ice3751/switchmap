from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(os.environ.get("SWITCHMAP_PROJECT", r"C:\SwitchMap"))
PATCH_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = PATCH_ROOT / "payload"
TASK_NAME = "SwitchMap Waitress"
PHASE = "phase103R10_dashboard_cards_codex_reviewed_fix"

TARGETS = [
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css"),
    Path("inventory/static/inventory/brand/phase103/icons/card-connectivity.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-urgent.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-alarms.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-topology.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-topology-map.svg"),
    Path("inventory/management/commands/phase103_dashboard_cards_ui_check.py"),
]

FORBIDDEN_PAYLOAD_NAMES = {
    "db.sqlite3",
    "switchmap.env",
}
FORBIDDEN_PAYLOAD_PARTS = {
    "venv",
    "backups",
    "logs",
    "secrets",
    "staticfiles",
    "__pycache__",
    ".git",
}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(paths: List[Path]) -> Dict[str, str]:
    return {str(p).replace("\\", "/"): sha256_file(PROJECT_ROOT / p) for p in paths}


def migration_hashes() -> Dict[str, str]:
    mig_dir = PROJECT_ROOT / "inventory" / "migrations"
    if not mig_dir.exists():
        return {}
    return {str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256_file(p) for p in sorted(mig_dir.glob("*.py"))}


def db_hash() -> str:
    return sha256_file(PROJECT_ROOT / "db.sqlite3")


class Runner:
    def __init__(self) -> None:
        self.stamp = now_stamp()
        self.logs_dir = PROJECT_ROOT / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.logs_dir / f"{PHASE}_{self.stamp}.log"
        self.backup_dir = PROJECT_ROOT / "backups" / f"{PHASE}_{self.stamp}"
        self.manifest: Dict[str, object] = {
            "phase": PHASE,
            "project_root": str(PROJECT_ROOT),
            "patch_root": str(PATCH_ROOT),
            "started_at": self.stamp,
            "targets": [str(t).replace("\\", "/") for t in TARGETS],
            "commands": [],
            "final_ok": False,
            "rollback_done": False,
            "service_restart": "NO",
            "db_mutation": "UNKNOWN",
            "migration_write": "UNKNOWN",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "operational_backup_write": "NO",
            "visible_test_data_created": "NO",
        }

    def log(self, msg: str) -> None:
        print(msg)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def run(self, args: List[str], *, check: bool = True, acceptable: Tuple[int, ...] = (0,)) -> int:
        self.log("RUN=" + " ".join(args))
        proc = subprocess.run(args, cwd=str(PROJECT_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        out = proc.stdout or ""
        if out.strip():
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(out)
                if not out.endswith("\n"):
                    f.write("\n")
        self.manifest["commands"].append({"args": args, "returncode": proc.returncode})
        if check and proc.returncode not in acceptable:
            raise RuntimeError(f"COMMAND_FAILED rc={proc.returncode}: {' '.join(args)}")
        return proc.returncode

    def run_cmd(self, command: str, *, check: bool = True, acceptable: Tuple[int, ...] = (0,)) -> int:
        self.log("RUN_CMD=" + command)
        proc = subprocess.run(command, cwd=str(PROJECT_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        out = proc.stdout or ""
        if out.strip():
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(out)
                if not out.endswith("\n"):
                    f.write("\n")
        self.manifest["commands"].append({"cmd": command, "returncode": proc.returncode})
        if check and proc.returncode not in acceptable:
            raise RuntimeError(f"COMMAND_FAILED rc={proc.returncode}: {command}")
        return proc.returncode

    def validate_environment(self) -> Path:
        self.log(f"PHASE103R10_APPLY_START")
        self.log(f"PROJECT_ROOT={PROJECT_ROOT}")
        self.log(f"PATCH_ROOT={PATCH_ROOT}")
        if not PROJECT_ROOT.exists():
            raise RuntimeError(f"PROJECT_ROOT_NOT_FOUND={PROJECT_ROOT}")
        manage = PROJECT_ROOT / "manage.py"
        if not manage.exists():
            raise RuntimeError(f"MANAGE_PY_NOT_FOUND={manage}")
        py = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
        if not py.exists():
            raise RuntimeError(f"VENV_PYTHON_NOT_FOUND={py}")
        if not PAYLOAD_ROOT.exists():
            raise RuntimeError(f"PAYLOAD_ROOT_NOT_FOUND={PAYLOAD_ROOT}")
        for src in PAYLOAD_ROOT.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(PAYLOAD_ROOT)
            parts = {part.lower() for part in rel.parts}
            if src.name.lower() in FORBIDDEN_PAYLOAD_NAMES or (parts & FORBIDDEN_PAYLOAD_PARTS):
                raise RuntimeError(f"FORBIDDEN_PAYLOAD_FILE={rel}")
        for rel in TARGETS:
            src = PAYLOAD_ROOT / rel
            if not src.exists():
                raise RuntimeError(f"PAYLOAD_TARGET_MISSING={rel}")
        self.run_cmd(f'schtasks /Query /TN "{TASK_NAME}"', check=True)
        return py

    def backup_targets(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        missing = []
        for rel in TARGETS:
            src = PROJECT_ROOT / rel
            dst = self.backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst)
                self.log(f"BACKUP_FILE={rel}")
            else:
                missing.append(str(rel).replace("\\", "/"))
                self.log(f"BACKUP_FILE_MISSING={rel}")
        (self.backup_dir / "missing_targets.json").write_text(json.dumps(missing, ensure_ascii=False, indent=2), encoding="utf-8")
        self.manifest["backup_dir"] = str(self.backup_dir)

    def copy_payload(self) -> None:
        for rel in TARGETS:
            src = PAYLOAD_ROOT / rel
            dst = PROJECT_ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            self.log(f"APPLIED_FILE={rel}")

    def rollback(self) -> None:
        self.log("ROLLBACK_START")
        missing_file = self.backup_dir / "missing_targets.json"
        missing = set(json.loads(missing_file.read_text(encoding="utf-8"))) if missing_file.exists() else set()
        for rel in TARGETS:
            rel_s = str(rel).replace("\\", "/")
            dst = PROJECT_ROOT / rel
            backup = self.backup_dir / rel
            if rel_s in missing:
                if dst.exists():
                    dst.unlink()
                    self.log(f"ROLLBACK_REMOVED_NEW_FILE={rel}")
            elif backup.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, dst)
                self.log(f"ROLLBACK_RESTORED_FILE={rel}")
            else:
                self.log(f"ROLLBACK_WARNING_NO_BACKUP={rel}")
        self.manifest["rollback_done"] = True
        self.log("ROLLBACK_DONE")

    def verify(self, py: Path, before_db: str, before_migrations: Dict[str, str]) -> None:
        self.run([str(py), "-m", "py_compile", "inventory/management/commands/phase103_dashboard_cards_ui_check.py"])
        self.run([str(py), "manage.py", "check"])
        self.run([str(py), "manage.py", "makemigrations", "--check", "--dry-run"])
        self.run([str(py), "manage.py", "collectstatic", "--noinput"])
        self.run([str(py), "manage.py", "phase103_dashboard_cards_ui_check", "--strict", "--output", f"logs/{PHASE}_ui_check_{self.stamp}.json"])
        self.run([str(py), "smoke_tests/run_smoke.py", "--strict", "--output", f"logs/{PHASE}_smoke_{self.stamp}.json"])
        self.run([str(py), "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", f"logs/{PHASE}_release_lock_{self.stamp}.json"])
        after_db = db_hash()
        after_migrations = migration_hashes()
        self.manifest["db_hash_before"] = before_db
        self.manifest["db_hash_after"] = after_db
        self.manifest["migration_hashes_before"] = before_migrations
        self.manifest["migration_hashes_after"] = after_migrations
        if after_db != before_db:
            self.manifest["db_mutation"] = "YES"
            raise RuntimeError("DB_HASH_CHANGED")
        self.manifest["db_mutation"] = "NO"
        if after_migrations != before_migrations:
            self.manifest["migration_write"] = "YES"
            raise RuntimeError("MIGRATION_FILES_CHANGED")
        self.manifest["migration_write"] = "NO"

    def restart_service(self) -> None:
        self.log("SERVICE_RESTART_START_AFTER_VERIFY_OK")
        self.run_cmd(f'schtasks /End /TN "{TASK_NAME}"', check=False)
        self.run_cmd('cmd /c ping -n 3 127.0.0.1 ^>nul', check=False)
        self.run_cmd(f'schtasks /Run /TN "{TASK_NAME}"', check=True)
        self.manifest["service_restart"] = "YES_AFTER_VERIFY_OK"
        self.log("SERVICE_RESTART_DONE")

    def write_manifest(self) -> None:
        self.manifest["finished_at"] = now_stamp()
        report = self.logs_dir / f"{PHASE}_apply_report_{self.stamp}.json"
        report.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log(f"APPLY_REPORT_JSON={report}")

    def main(self) -> int:
        py = None
        before_db = "UNKNOWN"
        before_migrations: Dict[str, str] = {}
        try:
            py = self.validate_environment()
            before_db = db_hash()
            before_migrations = migration_hashes()
            self.manifest["target_hashes_before"] = tree_hashes(TARGETS)
            self.backup_targets()
            self.copy_payload()
            self.manifest["target_hashes_after_copy"] = tree_hashes(TARGETS)
            self.verify(py, before_db, before_migrations)
            self.restart_service()
            self.manifest["final_ok"] = True
            self.log("FINAL_FAIL_COUNT=0")
            self.log("FINAL_WARNING_COUNT=0")
            self.log("DB_MUTATION=NO")
            self.log("MIGRATION_WRITE=NO")
            self.log("RESTORE_ENABLE_CHANGE=NO")
            self.log("SSH_EXECUTION=NO")
            self.log("OPERATIONAL_BACKUP_WRITE=NO")
            self.log("VISIBLE_TEST_DATA_CREATED=NO")
            self.log("PHASE103R10_APPLY_OK")
            return 0
        except Exception as exc:
            self.log(f"ERROR={exc}")
            try:
                if self.backup_dir.exists():
                    self.rollback()
                    if py is not None:
                        self.run([str(py), "manage.py", "collectstatic", "--noinput"], check=False)
            except Exception as rb_exc:
                self.log(f"ROLLBACK_ERROR={rb_exc}")
            self.manifest["final_ok"] = False
            self.log("PHASE103R10_APPLY_FAIL")
            return 1
        finally:
            self.write_manifest()


if __name__ == "__main__":
    raise SystemExit(Runner().main())
