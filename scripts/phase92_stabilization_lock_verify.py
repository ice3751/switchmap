from __future__ import annotations

import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

sys.dont_write_bytecode = True

PHASE = "PHASE92R2"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase92r2_stabilization_lock_verify_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase92r2_stabilization_lock_verify_{STAMP}.txt"
LATEST_JSON = LOG_DIR / "phase92r2_stabilization_lock_verify_latest.json"
LATEST_TXT = LOG_DIR / "phase92r2_stabilization_lock_verify_latest.txt"
BASELINE_JSON = LOG_DIR / "phase92r2_stabilization_baseline_latest.json"

CORE_PY_DIRS = ["config", "inventory", "tools"]
CORE_FILE_PATTERNS = [
    "config/*.py",
    "inventory/*.py",
    "inventory/management/commands/*.py",
    "inventory/templatetags/*.py",
    "inventory/templates/inventory/*.html",
    "inventory/static/inventory/*.js",
    "inventory/static/inventory/css/*.css",
    "scripts/*.cmd",
    "scripts/*.py",
]
PROTECTED_TOP = {".git", "venv", "backups", "logs", "secrets", "staticfiles", "media", "_phase91_quarantine", "_phase91_backup"}

CORE_URL_NAMES = [
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

REQUIRED_FILES = [
    "manage.py",
    "config/settings.py",
    "config/urls.py",
    "inventory/models.py",
    "inventory/urls.py",
    "inventory/access_control.py",
    "inventory/alarm_engine.py",
    "inventory/alarm_rules.py",
    "inventory/backup_storage_tools.py",
    "inventory/cisco_backup_tools.py",
    "inventory/mikrotik_backup_tools.py",
    "inventory/secure_credentials.py",
    "inventory/ssh_views.py",
    "inventory/dashboard_views.py",
    "inventory/topology_views.py",
    "inventory/sfp_views.py",
    "inventory/templates/inventory/base.html",
    "inventory/templates/inventory/switch_list.html",
    "inventory/templates/inventory/backup_health_dashboard.html",
    "inventory/templates/inventory/backup_storage_status.html",
    "inventory/templates/inventory/cisco_backup_center.html",
    "inventory/templates/inventory/mikrotik_backup_center.html",
    "inventory/templates/inventory/alarm_center.html",
    "inventory/templates/inventory/topology.html",
    "inventory/templates/inventory/sfp_monitor.html",
    "inventory/static/inventory/switchmap.js",
    "inventory/static/inventory/css/switchmap-dashboard-stable-main.css",
]

REQUIRED_MARKERS = {
    "inventory/access_control.py": ["ROLE_VIEW_ONLY", "ROLE_OPERATOR", "ROLE_ADMIN", "operator_or_admin_required", "backup_management_required"],
    # R2: URL capability must be verified through Django reverse/resolve, not by forcing URL names to appear in base.html.
    # base.html may link Backup Health through a different menu block or not expose it in the global navbar.
    "inventory/urls.py": ["backup-health/", "backup-storage/", "cisco-backups/", "mikrotik-backups/", "ssh-port-action/", "validate-restore/", "backup_health_dashboard", "alarm_center", "topology"],
    "inventory/templates/inventory/base.html": ["asset_documentation", "automation_templates", "config_backups"],
    "inventory/templates/inventory/switch_list.html": ["data-switch-search", "Quick Search"],
    "inventory/static/inventory/switchmap.js": ["data-switch-search", "data-search-results"],
    "inventory/alarm_rules.py": ["snmp_timeout", "interface_error", "sfp_optical_threshold", "cisco_crc_delta"],
}

class Phase92Error(RuntimeError):
    pass

@dataclass
class StepResult:
    name: str
    status: str
    detail: object


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def is_protected(path: Path) -> bool:
    try:
        parts = path.resolve().relative_to(ROOT).parts
    except Exception:
        return True
    return bool(parts and parts[0] in PROTECTED_TOP)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(args: List[str], name: str, *, check: bool = True, allow_codes: Optional[Iterable[int]] = None) -> subprocess.CompletedProcess:
    allow = set(allow_codes or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    print(f"STEP_START={name}")
    print("CMD=" + " ".join(args))
    proc = subprocess.run(args, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout:
        print(proc.stdout.rstrip())
    print(f"STEP_EXIT={name}:{proc.returncode}")
    if check and proc.returncode != 0 and proc.returncode not in allow:
        raise Phase92Error(f"{name} failed rc={proc.returncode}")
    return proc


def file_and_marker_guard() -> Dict:
    print("STEP_START=file_and_marker_guard")
    missing_files: List[str] = []
    missing_markers: Dict[str, List[str]] = {}
    for item in REQUIRED_FILES:
        path = ROOT / item
        if not path.exists():
            missing_files.append(item)
    for item, markers in REQUIRED_MARKERS.items():
        path = ROOT / item
        if not path.exists():
            missing_markers[item] = markers
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        miss = [m for m in markers if m not in text]
        if miss:
            missing_markers[item] = miss
    if missing_files:
        for item in missing_files:
            print(f"MISSING_FILE={item}")
    if missing_markers:
        for item, markers in missing_markers.items():
            print(f"MISSING_MARKERS={item}:{','.join(markers)}")
    if missing_files or missing_markers:
        raise Phase92Error("file/marker guard failed")
    print(f"FILE_GUARD_OK={len(REQUIRED_FILES)}")
    print(f"MARKER_GUARD_OK={len(REQUIRED_MARKERS)}")
    print("STEP_EXIT=file_and_marker_guard:0")
    return {"required_files": len(REQUIRED_FILES), "marker_files": len(REQUIRED_MARKERS)}


def py_compile_core() -> Dict:
    print("STEP_START=py_compile_core")
    temp_dir = Path(tempfile.mkdtemp(prefix="switchmap_phase92_pycompile_"))
    total = 0
    failures: List[Tuple[str, str]] = []
    try:
        for base in CORE_PY_DIRS:
            base_path = ROOT / base
            if not base_path.exists():
                continue
            for path in base_path.rglob("*.py"):
                if is_protected(path) or "__pycache__" in path.parts:
                    continue
                total += 1
                cfile = temp_dir / path.relative_to(ROOT).with_suffix(".pyc")
                cfile.parent.mkdir(parents=True, exist_ok=True)
                try:
                    py_compile.compile(str(path), cfile=str(cfile), doraise=True)
                except Exception as exc:
                    failures.append((rel(path), str(exc)))
        if failures:
            for file_rel, err in failures[:50]:
                print(f"PY_COMPILE_FAIL={file_rel} :: {err}")
            raise Phase92Error(f"py_compile failed count={len(failures)}")
        print(f"PY_COMPILE_OK={total}")
        print("STEP_EXIT=py_compile_core:0")
        return {"total": total, "failures": []}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def build_hash_baseline() -> Dict:
    print("STEP_START=hash_baseline")
    files: Dict[str, Dict[str, object]] = {}
    seen = set()
    for pattern in CORE_FILE_PATTERNS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or is_protected(path):
                continue
            r = rel(path)
            if r in seen:
                continue
            seen.add(r)
            files[r] = {"sha256": sha256_file(path), "size": path.stat().st_size}
    baseline = {"created_at": datetime.now().isoformat(timespec="seconds"), "root": str(ROOT), "file_count": len(files), "files": files}
    BASELINE_JSON.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"HASH_BASELINE_FILES={len(files)}")
    print(f"HASH_BASELINE_JSON={BASELINE_JSON}")
    print("STEP_EXIT=hash_baseline:0")
    return {"file_count": len(files), "path": str(BASELINE_JSON)}


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import django
    django.setup()


def url_and_http_guard() -> Dict:
    print("STEP_START=url_and_http_guard")
    setup_django()
    from django.test import Client
    from django.urls import resolve, reverse

    reversed_urls: Dict[str, str] = {}
    for name, args in CORE_URL_NAMES:
        url = reverse(name, args=args)
        reversed_urls[name] = url
        print(f"URL_REVERSE_OK={name} => {url}")

    client = Client(HTTP_HOST="it-tools.winac-co.com")
    get_statuses: Dict[str, int] = {}
    for path in CRITICAL_GET_PATHS:
        response = client.get(path, follow=False)
        get_statuses[path] = int(response.status_code)
        try:
            resolved = resolve(path)
            resolved_name = resolved.url_name
        except Exception:
            resolved_name = "UNRESOLVED"
        print(f"HTTP_GET_STATUS={path}:{response.status_code}:resolve={resolved_name}")
        if response.status_code >= 500:
            raise Phase92Error(f"GET 500 guard failed for {path}")
        if response.status_code == 404:
            raise Phase92Error(f"GET 404 guard failed for {path}")

    post_statuses: Dict[str, int] = {}
    for path in ANON_DANGEROUS_POSTS:
        response = client.post(path, data={}, follow=False, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        post_statuses[path] = int(response.status_code)
        print(f"ANON_POST_GUARD={path}:{response.status_code}")
        if response.status_code >= 500:
            raise Phase92Error(f"anonymous dangerous POST 500 for {path}")
        if response.status_code == 200:
            raise Phase92Error(f"anonymous dangerous POST returned 200 for {path}; access guard suspect")
    print("STEP_EXIT=url_and_http_guard:0")
    return {"reverse": reversed_urls, "get_status": get_statuses, "anon_post_status": post_statuses}


def data_snapshot_guard() -> Dict:
    print("STEP_START=data_snapshot_guard")
    setup_django()
    from django.contrib.auth.models import Group, User
    from inventory.models import AlarmNotification, ConfigBackupSnapshot, Port, RouterHealthSnapshot, SfpMonitorSnapshot, Switch

    counts = {
        "switch_total": Switch.objects.count(),
        "switch_active": Switch.objects.filter(is_active=True).count(),
        "port_total": Port.objects.count(),
        "active_alarm": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count(),
        "sfp_snapshot": SfpMonitorSnapshot.objects.count(),
        "router_health_snapshot": RouterHealthSnapshot.objects.count(),
        "config_backup_snapshot": ConfigBackupSnapshot.objects.count(),
        "user_total": User.objects.count(),
        "group_total": Group.objects.count(),
    }
    for key, value in counts.items():
        print(f"DATA_COUNT={key}:{value}")
    if counts["switch_active"] <= 0:
        raise Phase92Error("no active switches")
    if counts["port_total"] <= 0:
        raise Phase92Error("no ports")
    role_groups = set(Group.objects.filter(name__in=["View Only", "Operator", "Admin"]).values_list("name", flat=True))
    missing_roles = sorted({"View Only", "Operator", "Admin"} - role_groups)
    if missing_roles:
        raise Phase92Error("missing role groups: " + ",".join(missing_roles))
    print("ROLE_GROUPS_OK=View Only,Operator,Admin")
    print("STEP_EXIT=data_snapshot_guard:0")
    return {"counts": counts, "role_groups": sorted(role_groups)}


def access_control_guard() -> Dict:
    print("STEP_START=access_control_guard")
    setup_django()
    from inventory import access_control as ac

    checks = {
        "view_only_level": ac.role_level(ac.ROLE_VIEW_ONLY),
        "operator_level": ac.role_level(ac.ROLE_OPERATOR),
        "admin_level": ac.role_level(ac.ROLE_ADMIN),
        "operator_actions": sorted(ac.OPERATOR_SSH_ACTIONS),
        "admin_only_actions": sorted(ac.ADMIN_ONLY_SSH_ACTIONS),
    }
    if not (checks["view_only_level"] < checks["operator_level"] < checks["admin_level"]):
        raise Phase92Error("role order invalid")
    dangerous_overlap = sorted(set(ac.OPERATOR_SSH_ACTIONS) & set(ac.ADMIN_ONLY_SSH_ACTIONS))
    if dangerous_overlap:
        raise Phase92Error("operator/admin-only SSH action overlap: " + ",".join(dangerous_overlap))
    print("ROLE_ORDER_OK=View Only < Operator < Admin")
    print("SSH_ACTION_SCOPE_OK=operator_admin_split")
    print("STEP_EXIT=access_control_guard:0")
    return checks


def restore_guard() -> Dict:
    print("STEP_START=restore_guard")
    urls_path = ROOT / "inventory" / "urls.py"
    urls_text = urls_path.read_text(encoding="utf-8", errors="ignore")
    restore_lines = [line.strip() for line in urls_text.splitlines() if "restore" in line.lower()]
    bad_url_lines = [line for line in restore_lines if "validate-restore" not in line and "backup_validate_restore" not in line]
    if bad_url_lines:
        for line in bad_url_lines:
            print(f"RESTORE_GUARD_BAD_URL={line}")
        raise Phase92Error("real restore URL guard failed")

    dangerous_function_re = re.compile(r"def\s+\w*(?:execute|apply|run)_?restore\w*|def\s+\w*restore_?(?:execute|apply|run)\w*", re.IGNORECASE)
    dangerous_tokens = [
        "configure replace",
        "/system backup load",
        "restore_execute",
        "execute_restore",
        "restore_apply",
        "apply_restore",
        "run_restore",
        "restore_run",
    ]
    bad_hits: List[str] = []
    for path in (ROOT / "inventory").rglob("*.py"):
        if is_protected(path) or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in dangerous_function_re.finditer(text):
            bad_hits.append(f"{rel(path)}:{match.group(0)}")
        low = text.lower()
        for token in dangerous_tokens:
            if token.lower() in low:
                bad_hits.append(f"{rel(path)}:token:{token}")
    if bad_hits:
        for hit in bad_hits[:50]:
            print(f"RESTORE_GUARD_BAD_HIT={hit}")
        raise Phase92Error(f"restore guard dangerous hit count={len(bad_hits)}")
    print("RESTORE_GUARD_OK=validate_restore_only")
    print("STEP_EXIT=restore_guard:0")
    return {"restore_url_lines": restore_lines, "dangerous_hits": []}


def scheduled_task_guard() -> Dict:
    print("STEP_START=scheduled_task_guard")
    if os.name != "nt":
        print("SCHEDULED_TASK_GUARD_SKIPPED=non_windows_runtime")
        return {"skipped": True}
    results: Dict[str, Dict[str, str]] = {}
    for task_name in ["SwitchMap Scheduled Backup Daily", "SwitchMap Waitress"]:
        proc = run_cmd(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"], f"schtasks_query_{task_name}")
        output = proc.stdout or ""
        last_result = ""
        status = ""
        task_to_run = ""
        logon_mode = ""
        for line in output.splitlines():
            low = line.lower()
            if low.startswith("last result:"):
                last_result = line.split(":", 1)[1].strip()
            elif low.startswith("status:"):
                status = line.split(":", 1)[1].strip()
            elif low.startswith("task to run:"):
                task_to_run = line.split(":", 1)[1].strip()
            elif low.startswith("logon mode:"):
                logon_mode = line.split(":", 1)[1].strip()
        print(f"TASK_STATUS={task_name}:{status}")
        print(f"TASK_LAST_RESULT={task_name}:{last_result}")
        print(f"TASK_LOGON_MODE={task_name}:{logon_mode}")
        if task_name == "SwitchMap Scheduled Backup Daily":
            if last_result and last_result not in {"0", "0x0"}:
                raise Phase92Error(f"Scheduled Backup Last Result is not 0: {last_result}")
            if "switchmap_scheduled_backup_daily.cmd" not in task_to_run.lower():
                raise Phase92Error("Scheduled Backup task runner path changed")
        if task_name == "SwitchMap Waitress":
            if status.lower() != "running":
                raise Phase92Error(f"Waitress task is not running: {status}")
        results[task_name] = {"status": status, "last_result": last_result, "task_to_run": task_to_run, "logon_mode": logon_mode}
    print("STEP_EXIT=scheduled_task_guard:0")
    return results


def backup_policy_guard() -> Dict:
    print("STEP_START=backup_policy_guard")
    setup_django()
    from inventory.backup_schedule_policy import DEFAULT_POLICY, POLICY_PATH

    policy = DEFAULT_POLICY
    if POLICY_PATH.exists():
        try:
            loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                policy = loaded
        except Exception as exc:
            raise Phase92Error(f"backup policy json read failed: {exc}")
    auto_include = bool(policy.get("auto_include_new_devices"))
    full_ids = [int(x) for x in ((policy.get("mikrotik") or {}).get("full_backup_ids") or [])]
    cisco_exclude = [int(x) for x in ((policy.get("cisco") or {}).get("exclude_ids") or [])]
    mt_exclude = [int(x) for x in ((policy.get("mikrotik") or {}).get("exclude_ids") or [])]
    print(f"AUTO_INCLUDE_NEW_DEVICES={auto_include}")
    print("MIKROTIK_FULL_BACKUP_IDS=" + ",".join(str(x) for x in full_ids))
    print("CISCO_EXCLUDE_IDS=" + ",".join(str(x) for x in cisco_exclude))
    print("MIKROTIK_EXCLUDE_IDS=" + ",".join(str(x) for x in mt_exclude))
    if not auto_include:
        raise Phase92Error("auto_include_new_devices is disabled")
    # Known current full backup scope: only explicitly tested MikroTik IDs should be here.
    unexpected_full = sorted(set(full_ids) - {18, 19})
    if unexpected_full:
        raise Phase92Error("unexpected MikroTik full-backup IDs: " + ",".join(str(x) for x in unexpected_full))
    print("BACKUP_POLICY_GUARD_OK=auto_include_on_full_backup_limited")
    print("STEP_EXIT=backup_policy_guard:0")
    return {"auto_include_new_devices": auto_include, "mikrotik_full_backup_ids": full_ids, "cisco_exclude_ids": cisco_exclude, "mikrotik_exclude_ids": mt_exclude}


def run_management_guards() -> Dict:
    print("STEP_START=management_guards")
    python_exe = sys.executable
    results: Dict[str, int] = {}
    commands = [
        ([python_exe, "manage.py", "check"], "django_manage_check"),
        ([python_exe, "manage.py", "showmigrations", "--plan"], "showmigrations_plan"),
        ([python_exe, "manage.py", "phase77_stabilization_check", "--output", str(LOG_DIR / f"phase92_phase77_stabilization_{STAMP}.txt")], "phase77_stabilization_check"),
        ([python_exe, "manage.py", "phase80_alarm_normalization_check"], "phase80_alarm_normalization_check"),
        ([python_exe, "manage.py", "scheduled_backup_credential_check", "--profile", "all", "--strict"], "scheduled_backup_credential_check"),
        ([python_exe, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict"),
        ([python_exe, "manage.py", "backup_health_report", "--strict"], "backup_health_report_strict"),
        ([python_exe, "manage.py", "backup_coverage_audit", "--candidate-only", "--no-report"], "backup_coverage_candidate_only"),
    ]
    for args, name in commands:
        proc = run_cmd(args, name)
        results[name] = proc.returncode
    print("STEP_EXIT=management_guards:0")
    return results


def write_report(report: Dict) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    REPORT_JSON.write_text(text, encoding="utf-8")
    LATEST_JSON.write_text(text, encoding="utf-8")
    lines = [
        f"{PHASE}_STABILIZATION_LOCK_VERIFY_REPORT",
        f"STATUS={report.get('status')}",
        f"ROOT={ROOT}",
        f"GENERATED_AT={report.get('generated_at')}",
        f"REPORT_JSON={REPORT_JSON}",
        f"BASELINE_JSON={BASELINE_JSON}",
        f"ERROR={report.get('error', '')}",
    ]
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LATEST_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print(f"{PHASE}_ROOT={ROOT}")
    print(f"{PHASE}_REPORT_JSON={REPORT_JSON}")
    report: Dict[str, object] = {
        "marker": f"{PHASE}_STABILIZATION_LOCK_VERIFY",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "STARTED",
        "root": str(ROOT),
        "mode": "read_only_no_restart_no_restore_no_ssh",
        "steps": {},
        "error": "",
    }
    try:
        report["status"] = "RUNNING"
        write_report(report)
        report["steps"]["file_and_marker_guard"] = file_and_marker_guard()
        report["steps"]["hash_baseline"] = build_hash_baseline()
        report["steps"]["py_compile_core"] = py_compile_core()
        report["steps"]["url_and_http_guard"] = url_and_http_guard()
        report["steps"]["data_snapshot_guard"] = data_snapshot_guard()
        report["steps"]["access_control_guard"] = access_control_guard()
        report["steps"]["restore_guard"] = restore_guard()
        report["steps"]["scheduled_task_guard"] = scheduled_task_guard()
        report["steps"]["backup_policy_guard"] = backup_policy_guard()
        report["steps"]["management_guards"] = run_management_guards()
        report["status"] = "OK"
        write_report(report)
        print(f"{PHASE}_FINAL_OK=True")
        print(f"REPORT_JSON={REPORT_JSON}")
        print(f"REPORT_TXT={REPORT_TXT}")
        print(f"BASELINE_JSON={BASELINE_JSON}")
        print("SERVICE_RESTART=NO")
        print("DB_MUTATION=NO")
        print("RESTORE_ENABLE_CHANGE=NO")
        return 0
    except Exception as exc:
        print(f"{PHASE}_FAIL={exc}")
        report["status"] = "FAIL"
        report["error"] = str(exc)
        write_report(report)
        print(f"REPORT_JSON={REPORT_JSON}")
        print(f"REPORT_TXT={REPORT_TXT}")
        print("SERVICE_RESTART=NO")
        print("DB_MUTATION=NO")
        print("RESTORE_ENABLE_CHANGE=NO")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
