from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.dont_write_bytecode = True

PHASE = "PHASE93"
TASK_WAITRESS = "SwitchMap Waitress"
TASK_BACKUP = "SwitchMap Scheduled Backup Daily"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase93_performance_safe_refine"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase93_performance_safe_refine_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase93_performance_safe_refine_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase93_performance_safe_refine_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/context_processors.py"),
    Path("inventory/management/commands/phase93_performance_safe_refine_check.py"),
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
    "restore_enable_change": "NO",
}


def line(text: str) -> None:
    print(text)


def add_step(name: str, status: str, detail: object = None) -> None:
    report["steps"].append({"name": name, "status": status, "detail": detail})


def save_report() -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"PHASE={PHASE}",
        f"ROOT={ROOT}",
        f"FINAL_OK={report.get('final_ok')}",
        f"ROLLBACK_PERFORMED={report.get('rollback_performed')}",
        f"SERVICE_RESTART={report.get('service_restart')}",
        f"DB_MUTATION={report.get('db_mutation')}",
        f"RESTORE_ENABLE_CHANGE={report.get('restore_enable_change')}",
        f"REPORT_JSON={REPORT_JSON}",
        f"BACKUP_ROOT={BACKUP_ROOT}",
    ]
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: List[str], name: str, *, check: bool = True, allow_codes: List[int] | None = None) -> subprocess.CompletedProcess:
    allow = set(allow_codes or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    line(f"STEP_START={name}")
    line("CMD=" + " ".join(args))
    proc = subprocess.run(args, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout:
        line(proc.stdout.rstrip())
    line(f"STEP_EXIT={name}:{proc.returncode}")
    add_step(name, "ok" if proc.returncode == 0 or proc.returncode in allow else "fail", {"rc": proc.returncode})
    if check and proc.returncode != 0 and proc.returncode not in allow:
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
    protected_roots = {"venv", ".git", "logs", "secrets", "staticfiles", "media"}
    for rel in CHANGED_FILES:
        if rel.parts and rel.parts[0] in protected_roots:
            raise RuntimeError(f"refusing protected path: {rel}")
    line(f"ROOT={ROOT}")
    line(f"PAYLOAD={PAYLOAD}")
    line(f"BACKUP_ROOT={BACKUP_ROOT}")
    line("STEP_EXIT=preflight:0")
    add_step("preflight", "ok")


def backup_current_files() -> List[Dict[str, object]]:
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
    return manifest


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
    run([sys.executable, "-m", "py_compile", "inventory/context_processors.py", "inventory/management/commands/phase93_performance_safe_refine_check.py"], "py_compile_changed")
    run([sys.executable, "manage.py", "check"], "django_manage_check")
    run([sys.executable, "manage.py", "phase93_performance_safe_refine_check", "--strict", "--output", str(LOG_DIR / f"phase93_performance_check_{STAMP}.json")], "phase93_performance_check")
    run([sys.executable, "manage.py", "phase77_stabilization_check", "--output", str(LOG_DIR / f"phase93_phase77_stabilization_{STAMP}.txt")], "phase77_stabilization_check")
    run([sys.executable, "manage.py", "phase80_alarm_normalization_check"], "phase80_alarm_normalization_check")
    run([sys.executable, "manage.py", "scheduled_backup_credential_check", "--profile", "all", "--strict"], "scheduled_backup_credential_check")
    run([sys.executable, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict")
    run([sys.executable, "manage.py", "backup_health_report", "--strict"], "backup_health_report_strict")
    run(["schtasks", "/Query", "/TN", TASK_BACKUP, "/V", "/FO", "LIST"], "scheduled_backup_task_query")
    line("STEP_EXIT=verify_after_apply:0")
    add_step("verify_after_apply", "ok")


def _try_start_waitress_best_effort() -> None:
    try:
        subprocess.run(["schtasks", "/Run", "/TN", TASK_WAITRESS], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception:
        pass


def restart_waitress() -> None:
    line("STEP_START=restart_waitress")
    report["restart_step_started"] = True
    query_before = run(["schtasks", "/Query", "/TN", TASK_WAITRESS, "/V", "/FO", "LIST"], "waitress_task_query_before", check=False)
    if query_before.returncode != 0:
        line("WAITRESS_RESTART_SKIPPED=task_not_found")
        report["service_restart"] = "SKIPPED_TASK_NOT_FOUND"
        add_step("restart_waitress", "skipped", "task_not_found")
        return
    run(["schtasks", "/End", "/TN", TASK_WAITRESS], "waitress_task_end", check=False, allow_codes=[0, 1])
    time.sleep(2)
    run_proc = run(["schtasks", "/Run", "/TN", TASK_WAITRESS], "waitress_task_run", check=False)
    time.sleep(5)
    query_after = run(["schtasks", "/Query", "/TN", TASK_WAITRESS, "/V", "/FO", "LIST"], "waitress_task_query_after", check=False)
    running = query_after.returncode == 0 and ("Status:" not in query_after.stdout or "Running" in query_after.stdout)
    if not running:
        _try_start_waitress_best_effort()
        time.sleep(3)
        query_retry = run(["schtasks", "/Query", "/TN", TASK_WAITRESS, "/V", "/FO", "LIST"], "waitress_task_query_retry", check=False)
        running = query_retry.returncode == 0 and ("Status:" not in query_retry.stdout or "Running" in query_retry.stdout)
    if not running:
        raise RuntimeError(f"SwitchMap Waitress task is not Running after restart; run_rc={run_proc.returncode}")
    report["service_restart"] = "YES"
    line("WAITRESS_RESTART_OK=True")
    line("STEP_EXIT=restart_waitress:0")
    add_step("restart_waitress", "ok")


def main() -> int:
    line("PHASE93_PERFORMANCE_SAFE_REFINE_START")
    line("MODE=safe_code_refine_verify_restart_after_success")
    line(f"ROOT={ROOT}")
    line("EXPECTED_RESULT=context_processor_alarm_count_queries_reduced_and_existing_guards_ok")
    line("RISK=brief_waitress_restart_only_after_verify_success")
    line("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        preflight()
        backup_current_files()
        apply_payload()
        verify_after_apply()
        restart_waitress()
        report["final_ok"] = True
        save_report()
        line("PHASE93_FINAL_OK=True")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line(f"ROLLBACK_SOURCE={BACKUP_ROOT}")
        line("PHASE93_PERFORMANCE_SAFE_REFINE_OK")
        return 0
    except Exception as exc:
        report["final_ok"] = False
        report["error"] = repr(exc)
        line(f"PHASE93_FAIL={exc}")
        try:
            rollback()
        except Exception as rb_exc:
            report["rollback_error"] = repr(rb_exc)
            line(f"PHASE93_ROLLBACK_FAIL={rb_exc}")
        if report.get("restart_step_started"):
            line("WAITRESS_START_AFTER_FAILURE=best_effort")
            _try_start_waitress_best_effort()
        save_report()
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line("SERVICE_RESTART=NO_UNLESS_FAILURE_HAPPENED_AFTER_RESTART_STEP")
        line("DB_MUTATION=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
