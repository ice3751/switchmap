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

PHASE = "PHASE101"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase101_backup_storage_menu_refine"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase101_backup_storage_menu_refine_apply_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase101_backup_storage_menu_refine_apply_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase101_backup_storage_menu_refine_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/templates/inventory/backup_storage_status.html"),
    Path("inventory/management/commands/phase101_backup_storage_menu_ui_check.py"),
]
PAYLOAD_COPY_FILES = [
    Path("inventory/templates/inventory/backup_storage_status.html"),
    Path("inventory/management/commands/phase101_backup_storage_menu_ui_check.py"),
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

OLD_MENU_BLOCK = '''                <details class="topbar-dropdown command-menu-dropdown automation-dropdown">
                    <summary class="topbar-link {% if current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'config_backups' or current == 'config_backup_detail' or current == 'automation_templates' or current == 'automation_template_create' or current == 'automation_template_edit' or current == 'automation_template_preview' or current == 'action_logs' or current == 'reports' %}active{% endif %}">عملیات</summary>
                    <div class="dropdown-panel command-dropdown-panel compact-dropdown-panel">
                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'backup_center' %}active{% endif %}" href="{% url 'inventory:backup_center' %}">Backup / Restore</a>{% endif %}
                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}" href="{% url 'inventory:cisco_backup_center' %}">Cisco Backup Center</a>{% endif %}
                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'mikrotik_backup_center' or current == 'mikrotik_backup_detail' %}active{% endif %}" href="{% url 'inventory:mikrotik_backup_center' %}">MikroTik Backup</a>{% endif %}
                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'backup_credential_prepare' %}active{% endif %}" href="{% url 'inventory:backup_credential_prepare' %}">Scheduled Credentials</a>{% endif %}
                                                {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'backup_storage_status' %}active{% endif %}" href="{% url 'inventory:backup_storage_status' %}">Secure Backup Storage</a>{% endif %}
                        {% if swmap_can_ssh %}<a class="command-dropdown-item {% if current == 'automation_templates' or current == 'automation_template_create' or current == 'automation_template_edit' or current == 'automation_template_preview' %}active{% endif %}" href="{% url 'inventory:automation_templates' %}">Automation Templates</a>{% endif %}
                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'config_backups' or current == 'config_backup_detail' %}active{% endif %}" href="{% url 'inventory:config_backups' %}">Config Backup / Diff</a>{% endif %}
                        <a class="command-dropdown-item {% if current == 'action_logs' %}active{% endif %}" href="{% url 'inventory:action_logs' %}">لاگ‌ها</a>
                        <a class="command-dropdown-item {% if current == 'reports' %}active{% endif %}" href="{% url 'inventory:reports' %}">گزارش‌ها</a>
                    </div>
                </details>
'''

NEW_MENU_BLOCK = '''                <details class="topbar-dropdown command-menu-dropdown automation-dropdown" data-phase101-operations-menu-refine>
                    <summary class="topbar-link {% if current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'mikrotik_backup_center' or current == 'mikrotik_backup_detail' or current == 'backup_storage_status' or current == 'config_backups' or current == 'config_backup_detail' or current == 'automation_templates' or current == 'automation_template_create' or current == 'automation_template_edit' or current == 'automation_template_preview' or current == 'action_logs' or current == 'reports' %}active{% endif %}">عملیات</summary>
                    <div class="dropdown-panel command-dropdown-panel compact-dropdown-panel phase101-operations-panel">
                        {% if swmap_can_manage_backups %}
                            <div class="command-dropdown-section-label">Backup / Restore</div>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'backup_center' %}active{% endif %}" href="{% url 'inventory:backup_center' %}">Overview / Restore Guard</a>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}" href="{% url 'inventory:cisco_backup_center' %}">Cisco Backup Center</a>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'mikrotik_backup_center' or current == 'mikrotik_backup_detail' %}active{% endif %}" href="{% url 'inventory:mikrotik_backup_center' %}">MikroTik Backup</a>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'backup_storage_status' %}active{% endif %}" href="{% url 'inventory:backup_storage_status' %}">Secure Backup Storage</a>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'config_backups' or current == 'config_backup_detail' %}active{% endif %}" href="{% url 'inventory:config_backups' %}">Config Backup / Diff</a>
                        {% endif %}

                        {% if swmap_can_ssh %}
                            <div class="command-dropdown-section-label">SSH Automation</div>
                            <a class="command-dropdown-item phase101-subitem {% if current == 'automation_templates' or current == 'automation_template_create' or current == 'automation_template_edit' or current == 'automation_template_preview' %}active{% endif %}" href="{% url 'inventory:automation_templates' %}">Automation Templates</a>
                        {% endif %}

                        <div class="command-dropdown-section-label">Reports</div>
                        <a class="command-dropdown-item phase101-subitem {% if current == 'action_logs' %}active{% endif %}" href="{% url 'inventory:action_logs' %}">لاگ‌ها</a>
                        <a class="command-dropdown-item phase101-subitem {% if current == 'reports' %}active{% endif %}" href="{% url 'inventory:reports' %}">گزارش‌ها</a>
                    </div>
                </details>
'''

MENU_STYLE = '''
    <style>
      .phase101-operations-panel .command-dropdown-section-label{margin:8px 8px 4px;padding:7px 10px;border-top:1px solid rgba(148,163,184,.22);color:#93a4bd;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}
      .phase101-operations-panel .command-dropdown-section-label:first-child{border-top:0;margin-top:2px}
      .phase101-operations-panel .phase101-subitem{padding-inline-start:22px}
    </style>
'''


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
    if not PAYLOAD.exists():
        raise RuntimeError(f"missing payload: {PAYLOAD}")
    missing = [str(p).replace("\\", "/") for p in PAYLOAD_COPY_FILES if not (PAYLOAD / p).exists()]
    if missing:
        raise RuntimeError("missing payload files: " + ",".join(missing))
    protected_roots = {"venv", ".git", "logs", "secrets", "staticfiles", "media", "backups", "_phase91_backup", "_phase91_quarantine", "db.sqlite3"}
    for rel in CHANGED_FILES:
        if rel.parts and rel.parts[0] in protected_roots:
            raise RuntimeError(f"refusing protected path: {rel}")
    base = ROOT / "inventory" / "templates" / "inventory" / "base.html"
    storage = ROOT / "inventory" / "templates" / "inventory" / "backup_storage_status.html"
    if not base.exists() or not storage.exists():
        raise RuntimeError("missing required template files")
    base_text = base.read_text(encoding="utf-8")
    if "data-phase101-operations-menu-refine" not in base_text and OLD_MENU_BLOCK not in base_text:
        raise RuntimeError("operations menu block did not match expected safe patch target")
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


def patch_base_template() -> None:
    path = ROOT / "inventory" / "templates" / "inventory" / "base.html"
    text = path.read_text(encoding="utf-8")
    if "data-phase101-operations-menu-refine" not in text:
        if OLD_MENU_BLOCK not in text:
            raise RuntimeError("operations menu target not found")
        text = text.replace(OLD_MENU_BLOCK, NEW_MENU_BLOCK, 1)
    if "phase101-operations-panel .command-dropdown-section-label" not in text:
        marker = "    {% block extra_head %}{% endblock %}"
        if marker not in text:
            raise RuntimeError("extra_head marker not found")
        text = text.replace(marker, MENU_STYLE + marker, 1)
    path.write_text(text, encoding="utf-8")
    line("PATCHED_FILE=inventory/templates/inventory/base.html")


def apply_payload() -> None:
    line("STEP_START=apply_payload")
    patch_base_template()
    for rel in PAYLOAD_COPY_FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        line(f"APPLIED_FILE={rel}")
    line("STEP_EXIT=apply_payload:0")
    add_step("apply_payload", "ok")


def rollback() -> None:
    line("STEP_START=rollback")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.exists() else []
    for entry in manifest:
        rel = Path(entry["path"])
        target = ROOT / rel
        backup = BACKUP_FILES / rel
        if entry.get("existed"):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            line(f"ROLLBACK_RESTORED={rel}")
        else:
            if target.exists():
                target.unlink()
                line(f"ROLLBACK_REMOVED_NEW_FILE={rel}")
    report["rollback_performed"] = True
    line("STEP_EXIT=rollback:0")
    add_step("rollback", "ok")


def verify_after_apply() -> None:
    line("STEP_START=verify_after_apply")
    py = str(Path(sys.executable))
    run([py, "-m", "py_compile", "inventory/management/commands/phase101_backup_storage_menu_ui_check.py"], "py_compile_changed")
    run([py, "manage.py", "check"], "django_manage_check")
    run([py, "manage.py", "phase101_backup_storage_menu_ui_check", "--strict", "--output", str(LOG_DIR / f"phase101_backup_storage_menu_ui_check_{STAMP}.json")], "phase101_backup_storage_menu_ui_check")
    smoke = ROOT / "smoke_tests" / "run_smoke.py"
    if smoke.exists():
        run([py, "smoke_tests/run_smoke.py", "--strict", "--output", str(LOG_DIR / f"phase101_phase94_smoke_runner_{STAMP}.json")], "phase94_smoke_runner")
    final_check = ROOT / "inventory" / "management" / "commands" / "phase98_100_final_release_lock_check.py"
    if final_check.exists():
        run([py, "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", str(LOG_DIR / f"phase101_phase98_100_final_release_lock_{STAMP}.json")], "phase98_100_final_release_lock_check")
    run([py, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict")
    line("STEP_EXIT=verify_after_apply:0")
    add_step("verify_after_apply", "ok")


def main() -> int:
    line("PHASE101_BACKUP_STORAGE_MENU_REFINE_START")
    line("MODE=file_only_ui_refine_no_db_no_restart_no_restore_no_ssh")
    line(f"ROOT={ROOT}")
    line("EXPECTED_RESULT=backup_storage_filters_and_operations_menu_refined_without_runtime_change")
    line("RISK=file_only_template_changes_no_runtime_restart")
    line("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        preflight()
        backup_current_files()
        apply_payload()
        verify_after_apply()
        report["final_ok"] = True
        line("PHASE101_FINAL_OK=True")
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
        line("PHASE101_BACKUP_STORAGE_MENU_REFINE_OK")
        return 0
    except Exception as exc:
        line(f"PHASE101_ERROR={type(exc).__name__}:{exc}")
        try:
            if MANIFEST_JSON.exists():
                rollback()
        except Exception as rb_exc:
            line(f"PHASE101_ROLLBACK_ERROR={type(rb_exc).__name__}:{rb_exc}")
        report["final_ok"] = False
        line("PHASE101_FINAL_OK=False")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line("SERVICE_RESTART=NO")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE101_BACKUP_STORAGE_MENU_REFINE_FAIL")
        return 1
    finally:
        save_report()


if __name__ == "__main__":
    raise SystemExit(main())
