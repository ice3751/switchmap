from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TARGETS = [
    "inventory/views.py",
    "inventory/templates/inventory/switch_list.html",
    "inventory/templates/inventory/includes/dashboard_device_browser.html",
    "inventory/management/commands/phase106_dashboard_deep_performance_check.py",
]
PHASE = "phase106_dashboard_deep_performance_fix"
TASK_NAME = "SwitchMap Waitress"


def norm_rel(path: str) -> Path:
    return Path(*Path(path).parts)


def line(text: str):
    print(str(text), flush=True)


def run_cmd(cmd, cwd: Path, log_lines: list[str]) -> int:
    display = " ".join(str(x) for x in cmd)
    line("RUN=" + display)
    log_lines.append("RUN=" + display)
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
        log_lines.append(proc.stdout)
    return proc.returncode


def run_shell(cmd: str, cwd: Path, log_lines: list[str], fail_ok=False) -> int:
    line("RUN_CMD=" + cmd)
    log_lines.append("RUN_CMD=" + cmd)
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
        log_lines.append(proc.stdout)
    if proc.returncode and not fail_ok:
        raise RuntimeError(f"command_failed rc={proc.returncode}: {cmd}")
    return proc.returncode


def copy_payload(project_root: Path, patch_root: Path, backup_dir: Path, log_lines: list[str]):
    payload_root = patch_root / "payload"
    if not payload_root.exists():
        raise RuntimeError(f"payload_missing:{payload_root}")
    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel in TARGETS:
        rel_path = norm_rel(rel)
        src = payload_root / rel_path
        dst = project_root / rel_path
        bak = backup_dir / rel_path
        if not src.exists():
            raise RuntimeError(f"payload_file_missing:{rel}")
        bak.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.copy2(dst, bak)
            line("BACKUP_FILE=" + rel.replace("/", "\\"))
            existed = True
        else:
            (bak.parent / (bak.name + ".MISSING")).write_text("missing before phase106\n", encoding="utf-8")
            line("BACKUP_FILE_MISSING=" + rel.replace("/", "\\"))
            existed = False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        line("APPLIED_FILE=" + rel.replace("/", "\\"))
        manifest.append({"rel": rel, "existed": existed})
    return manifest


def rollback(project_root: Path, backup_dir: Path, manifest: list[dict], log_lines: list[str]):
    line("ROLLBACK_START")
    log_lines.append("ROLLBACK_START")
    for item in reversed(manifest):
        rel = item["rel"]
        rel_path = norm_rel(rel)
        dst = project_root / rel_path
        bak = backup_dir / rel_path
        if item.get("existed") and bak.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bak, dst)
            line("ROLLBACK_FILE=" + rel.replace("/", "\\"))
        else:
            if dst.exists():
                dst.unlink()
                line("ROLLBACK_REMOVE_NEW_FILE=" + rel.replace("/", "\\"))
    line("ROLLBACK_DONE")
    log_lines.append("ROLLBACK_DONE")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--patch-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    patch_root = Path(args.patch_root).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "backups" / f"{PHASE}_{stamp}"
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{PHASE}_apply_{stamp}.log"
    report_file = logs_dir / f"{PHASE}_apply_report_{stamp}.json"
    log_lines: list[str] = []
    manifest: list[dict] = []

    line("PHASE106_DASHBOARD_DEEP_PERFORMANCE_APPLY_START")
    line("PROJECT_ROOT=" + str(project_root))
    line("PATCH_ROOT=" + str(patch_root))
    line("BACKUP_DIR=" + str(backup_dir))
    line("LOG=" + str(log_file))

    try:
        if not project_root.exists():
            raise RuntimeError(f"project_root_missing:{project_root}")
        run_shell(f'schtasks /Query /TN "{TASK_NAME}"', project_root, log_lines, fail_ok=True)
        manifest = copy_payload(project_root, patch_root, backup_dir, log_lines)

        py = project_root / "venv" / "Scripts" / "python.exe"
        commands = [
            [str(py), "-m", "py_compile", "inventory/views.py", "inventory/management/commands/phase106_dashboard_deep_performance_check.py"],
            [str(py), "manage.py", "check"],
            [str(py), "manage.py", "makemigrations", "--check", "--dry-run"],
            [str(py), "manage.py", "phase106_dashboard_deep_performance_check", "--strict", "--output", f"logs/{PHASE}_check_{stamp}.json"],
            [str(py), "smoke_tests/run_smoke.py", "--strict", "--output", f"logs/{PHASE}_smoke_{stamp}.json"],
            [str(py), "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", f"logs/{PHASE}_release_lock_{stamp}.json"],
        ]
        for cmd in commands:
            rc = run_cmd(cmd, project_root, log_lines)
            if rc != 0:
                raise RuntimeError(f"verify_failed rc={rc}: {' '.join(cmd)}")

        line("SERVICE_RESTART_START_AFTER_VERIFY_OK")
        run_shell(f'schtasks /End /TN "{TASK_NAME}"', project_root, log_lines, fail_ok=True)
        time.sleep(2)
        run_shell(f'schtasks /Run /TN "{TASK_NAME}"', project_root, log_lines, fail_ok=False)
        line("SERVICE_RESTART_DONE")

        final = {
            "phase": "Phase106",
            "ok": True,
            "backup_dir": str(backup_dir),
            "log": str(log_file),
            "targets": TARGETS,
            "db_mutation": "NO",
            "migration_write": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "operational_backup_write": "NO",
            "visible_test_data_created": "NO",
        }
        report_file.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        line("FINAL_FAIL_COUNT=0")
        line("FINAL_WARNING_COUNT=0")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("OPERATIONAL_BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE106_APPLY_OK")
        line("APPLY_REPORT_JSON=" + str(report_file))
        return 0
    except Exception as exc:
        line("PHASE106_APPLY_FAIL=" + repr(exc))
        if manifest:
            try:
                rollback(project_root, backup_dir, manifest, log_lines)
            except Exception as rb_exc:
                line("ROLLBACK_FAIL=" + repr(rb_exc))
        final = {
            "phase": "Phase106",
            "ok": False,
            "error": repr(exc),
            "backup_dir": str(backup_dir),
            "log": str(log_file),
            "targets": TARGETS,
        }
        try:
            report_file.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        line("FINAL_FAIL_COUNT=1")
        line("SERVICE_RESTART=NO")
        return 1
    finally:
        try:
            log_file.write_text("\n".join(log_lines), encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
