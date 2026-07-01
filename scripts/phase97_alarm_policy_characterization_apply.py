from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.dont_write_bytecode = True

PHASE = "PHASE97"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase97_alarm_policy_characterization"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase97_alarm_policy_characterization_apply_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase97_alarm_policy_characterization_apply_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase97_alarm_policy_characterization_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/management/commands/phase97_alarm_policy_characterization_check.py"),
]

report: Dict[str, object] = {
    "phase": PHASE,
    "root": str(ROOT),
    "stamp": STAMP,
    "changed_files": [str(p).replace("\\", "/") for p in CHANGED_FILES],
    "steps": [],
    "rollback_performed": False,
    "service_restart": "NO",
    "db_mutation": "NO",
    "migration_write": "NO",
    "restore_enable_change": "NO",
    "ssh_execution": "NO",
    "backup_write": "NO",
    "visible_test_data_created": "NO",
}


def line(text: str) -> None:
    print(text)


def add_step(name: str, status: str, detail: object = None) -> None:
    report.setdefault("steps", []).append({"name": name, "status": status, "detail": detail})


def save_report() -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"PHASE={PHASE}",
        f"ROOT={ROOT}",
        f"FINAL_OK={report.get('final_ok')}",
        f"ROLLBACK_PERFORMED={report.get('rollback_performed')}",
        f"SERVICE_RESTART={report.get('service_restart')}",
        f"DB_MUTATION={report.get('db_mutation')}",
        f"MIGRATION_WRITE={report.get('migration_write')}",
        f"RESTORE_ENABLE_CHANGE={report.get('restore_enable_change')}",
        f"SSH_EXECUTION={report.get('ssh_execution')}",
        f"BACKUP_WRITE={report.get('backup_write')}",
        f"VISIBLE_TEST_DATA_CREATED={report.get('visible_test_data_created')}",
        f"REPORT_JSON={REPORT_JSON}",
        f"BACKUP_ROOT={BACKUP_ROOT}",
    ]
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: List[str], name: str, *, check: bool = True, allow_codes: Optional[List[int]] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    allow = set(allow_codes or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    line(f"STEP_START={name}")
    line("CMD=" + " ".join(args))
    proc = subprocess.run(args, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if proc.stdout:
        line(proc.stdout.rstrip())
    line(f"STEP_EXIT={name}:{proc.returncode}")
    ok = proc.returncode == 0 or proc.returncode in allow
    add_step(name, "ok" if ok else "fail", {"rc": proc.returncode})
    if check and not ok:
        raise RuntimeError(f"{name} failed rc={proc.returncode}")
    return proc


def preflight() -> None:
    line("STEP_START=preflight")
    if not (ROOT / "manage.py").exists():
        raise RuntimeError("missing manage.py")
    if not Path(sys.executable).exists():
        raise RuntimeError("missing python executable")
    if not PAYLOAD.exists():
        raise RuntimeError(f"missing payload: {PAYLOAD}")
    missing_payload = [str(p).replace("\\", "/") for p in CHANGED_FILES if not (PAYLOAD / p).exists()]
    if missing_payload:
        raise RuntimeError("missing payload files: " + ",".join(missing_payload))
    protected_roots = {"venv", ".git", "logs", "secrets", "staticfiles", "media", "backups", "_phase91_backup", "_phase91_quarantine", "db.sqlite3"}
    for rel in CHANGED_FILES:
        if rel.parts and rel.parts[0] in protected_roots:
            raise RuntimeError(f"refusing protected path: {rel}")
    line(f"ROOT={ROOT}")
    line(f"PAYLOAD={PAYLOAD}")
    line(f"BACKUP_ROOT={BACKUP_ROOT}")
    line("STEP_EXIT=preflight:0")
    add_step("preflight", "ok")


def backup_current_files() -> None:
    line("STEP_START=backup_current_files")
    BACKUP_FILES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for rel in CHANGED_FILES:
        src = ROOT / rel
        dst = BACKUP_FILES / rel
        entry = {"path": str(rel).replace("\\", "/"), "existed": src.exists()}
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            line(f"BACKUP_FILE={rel}")
        else:
            line(f"BACKUP_NEW_FILE_MARKER={rel}")
        manifest.append(entry)
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    line(f"BACKUP_MANIFEST={MANIFEST_JSON}")
    line("STEP_EXIT=backup_current_files:0")
    add_step("backup_current_files", "ok", manifest)


def apply_payload() -> None:
    line("STEP_START=apply_payload")
    for rel in CHANGED_FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        line(f"APPLIED_FILE={rel}")
    line("STEP_EXIT=apply_payload:0")
    add_step("apply_payload", "ok")


def rollback() -> None:
    line("STEP_START=rollback")
    report["rollback_performed"] = True
    if not MANIFEST_JSON.exists():
        line("ROLLBACK_SKIP=no_manifest")
        add_step("rollback", "skipped", "no_manifest")
        return
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    for entry in reversed(manifest):
        rel = Path(entry["path"])
        dst = ROOT / rel
        backup = BACKUP_FILES / rel
        if entry.get("existed"):
            if backup.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, dst)
                line(f"ROLLBACK_RESTORED={rel}")
            else:
                line(f"ROLLBACK_MISSING_BACKUP={rel}")
        else:
            if dst.exists():
                dst.unlink()
                line(f"ROLLBACK_REMOVED_NEW_FILE={rel}")
    line("STEP_EXIT=rollback:0")
    add_step("rollback", "ok")


def verify_after_apply() -> None:
    line("STEP_START=verify_after_apply")
    run([sys.executable, "-m", "py_compile", "inventory/management/commands/phase97_alarm_policy_characterization_check.py"], "py_compile_changed")
    run([sys.executable, "manage.py", "check"], "django_manage_check")
    run([sys.executable, "manage.py", "phase97_alarm_policy_characterization_check", "--strict", "--output", str(LOG_DIR / f"phase97_alarm_policy_characterization_{STAMP}.json")], "phase97_alarm_policy_characterization_check", timeout=180)
    if (ROOT / "smoke_tests" / "run_smoke.py").exists():
        run([sys.executable, "smoke_tests/run_smoke.py", "--strict", "--output", str(LOG_DIR / f"phase97_phase94_smoke_runner_{STAMP}.json")], "phase94_smoke_runner", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "phase77_stabilization_check.py").exists():
        run([sys.executable, "manage.py", "phase77_stabilization_check", "--output", str(LOG_DIR / f"phase97_phase77_stabilization_{STAMP}.txt")], "phase77_stabilization_check", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "phase80_alarm_normalization_check.py").exists():
        run([sys.executable, "manage.py", "phase80_alarm_normalization_check"], "phase80_alarm_normalization_check", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "backup_storage_verify.py").exists():
        run([sys.executable, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict", timeout=300)
    if (ROOT / "inventory" / "management" / "commands" / "backup_health_report.py").exists():
        run([sys.executable, "manage.py", "backup_health_report", "--strict"], "backup_health_report_strict", timeout=300)
    line("STEP_EXIT=verify_after_apply:0")
    add_step("verify_after_apply", "ok")


def main() -> int:
    line("PHASE97_ALARM_POLICY_CHARACTERIZATION_START")
    line("MODE=file_only_readonly_alarm_policy_tests_no_visible_test_data_no_restart_no_restore_no_ssh")
    line(f"ROOT={ROOT}")
    line("EXPECTED_RESULT=alarm_policy_current_behavior_characterized_before_any_cleanup")
    line("RISK=file_only_new_management_command_no_runtime_restart")
    line("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        preflight()
        backup_current_files()
        apply_payload()
        verify_after_apply()
        report["final_ok"] = True
        save_report()
        line("PHASE97_FINAL_OK=True")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line(f"ROLLBACK_SOURCE={BACKUP_ROOT}")
        line("SERVICE_RESTART=NO")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE97_ALARM_POLICY_CHARACTERIZATION_OK")
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
        line(f"PHASE97_ERROR={type(exc).__name__}:{exc}")
        try:
            rollback()
        except Exception as rb_exc:
            report["rollback_error"] = f"{type(rb_exc).__name__}:{rb_exc}"
            line(f"PHASE97_ROLLBACK_ERROR={type(rb_exc).__name__}:{rb_exc}")
        report["final_ok"] = False
        save_report()
        line("PHASE97_FINAL_OK=False")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line("SERVICE_RESTART=NO")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE97_ALARM_POLICY_CHARACTERIZATION_FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
