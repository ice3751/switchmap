from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

sys.dont_write_bytecode = True

PHASE = "PHASE91"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase91_project_cleanup_refine_verify_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase91_project_cleanup_refine_verify_{STAMP}.txt"
LATEST_JSON = LOG_DIR / "phase91_project_cleanup_refine_verify_latest.json"
LATEST_TXT = LOG_DIR / "phase91_project_cleanup_refine_verify_latest.txt"

QUARANTINE_ROOT = ROOT / "_phase91_quarantine" / STAMP
CHANGE_BACKUP_ROOT = ROOT / "_phase91_backup" / STAMP
ROLLBACK_CMD = LOG_DIR / f"phase91_rollback_{STAMP}.cmd"

PROTECTED_TOP = {
    ".git",
    "venv",
    "backups",
    "logs",
    "secrets",
    "staticfiles",
    "static",
    "media",
    "project_snapshots",
    "_phase91_quarantine",
    "_phase91_backup",
}
PROTECTED_FILE_NAMES = {
    "db.sqlite3",
    "switchmap.env",
    ".env",
}
PROTECTED_SUFFIXES = {
    ".dpapi",
    ".sqlite3",
    ".bak",
}
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEMP_SUFFIXES = {".pyc", ".pyo", ".tmp"}
TEMP_FILE_NAMES = {"%LOG%"}
PATCH_PAYLOAD_DIR_RE = re.compile(r"^(payload|phase\d+(?:_\d+)*_payload)$", re.IGNORECASE)
ROOT_PATCH_FILE_RE = re.compile(
    r"^(phase\d+[\w.-]*|PHASE\d+[\w.-]*|PHASE\d+R\w+[\w.-]*).*(?:\.txt|\.zip)$",
    re.IGNORECASE,
)

CORE_PY_DIRS = ["config", "inventory", "tools"]
CORE_ROOT_PY_FILES = ["manage.py", "run_waitress.py"]
URL_NAMES = [
    ("inventory:switch_list", None),
    ("inventory:backup_health_dashboard", None),
    ("inventory:backup_storage_status", None),
    ("inventory:cisco_backup_center", None),
    ("inventory:mikrotik_backup_center", None),
    ("inventory:alarm_center", None),
    ("inventory:topology", None),
    ("inventory:sfp_monitor", None),
    ("inventory:backup_center", None),
    ("inventory:user_management", None),
    ("inventory:switchmap_ajax_ssh_port_action", None),
    ("inventory:switchmap_ajax_multi_ssh_port_action", None),
    ("inventory:backup_validate_restore", None),
    ("inventory:cisco_backup_validate_restore", ["dummy"]),
    ("inventory:mikrotik_backup_validate_restore", ["dummy"]),
]
URL_PATHS = [
    "/",
    "/backup-health/",
    "/backup-storage/",
    "/cisco-backups/",
    "/mikrotik-backups/",
    "/alarms/",
    "/topology/",
    "/sfp-monitor/",
    "/backups/",
]


class Phase91Error(RuntimeError):
    pass


@dataclass
class Candidate:
    rel: str
    kind: str
    reason: str
    risk: str


@dataclass
class MoveRecord:
    rel: str
    kind: str
    reason: str
    original: str
    quarantine: str
    backup: str


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def path_from_rel(value: str) -> Path:
    return ROOT / Path(value.replace("/", os.sep))


def is_protected(path: Path) -> bool:
    try:
        r = path.resolve().relative_to(ROOT)
    except Exception:
        return True
    parts = r.parts
    if not parts:
        return False
    if parts[0] in PROTECTED_TOP:
        return True
    if path.name in PROTECTED_FILE_NAMES:
        return True
    if path.suffix.lower() in PROTECTED_SUFFIXES:
        return True
    return False


def is_root_patch_file(path: Path) -> bool:
    try:
        r = path.resolve().relative_to(ROOT)
    except Exception:
        return False
    if len(r.parts) != 1:
        return False
    return ROOT_PATCH_FILE_RE.match(path.name) is not None


def is_patch_payload_dir(path: Path) -> bool:
    try:
        r = path.resolve().relative_to(ROOT)
    except Exception:
        return False
    if len(r.parts) != 1:
        return False
    return PATCH_PAYLOAD_DIR_RE.match(path.name) is not None


def scan_project() -> Dict:
    categories: Dict[str, int] = {}
    top_dirs: Dict[str, int] = {}
    candidates: List[Candidate] = []
    report_only_patch: List[str] = []
    protected_seen: List[str] = []
    file_count = 0
    dir_count = 0

    for current_root, dirnames, filenames in os.walk(ROOT):
        current = Path(current_root)
        try:
            current_rel = current.resolve().relative_to(ROOT)
        except Exception:
            continue

        kept_dirs: List[str] = []
        for dirname in dirnames:
            dpath = current / dirname
            if is_protected(dpath):
                protected_seen.append(rel(dpath))
                continue
            if dirname in CACHE_DIR_NAMES:
                candidates.append(Candidate(rel(dpath), "dir", "python_cache_dir", "low"))
                continue
            if is_patch_payload_dir(dpath):
                candidates.append(Candidate(rel(dpath), "dir", "old_patch_payload_dir", "low"))
                continue
            if dirname.lower() in {"patches", "smoke_tests", "reports"}:
                report_only_patch.append(rel(dpath))
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        if current_rel.parts:
            top_dirs[current_rel.parts[0]] = top_dirs.get(current_rel.parts[0], 0) + 1
        dir_count += 1

        for filename in filenames:
            path = current / filename
            if is_protected(path):
                protected_seen.append(rel(path))
                continue
            file_count += 1
            suffix = path.suffix.lower() or "[none]"
            categories[suffix] = categories.get(suffix, 0) + 1
            if suffix in TEMP_SUFFIXES or filename.endswith("~") or filename in TEMP_FILE_NAMES:
                candidates.append(Candidate(rel(path), "file", "python_temp_file", "low"))
            elif is_root_patch_file(path):
                candidates.append(Candidate(rel(path), "file", "old_root_patch_artifact", "low"))
            elif "phase" in filename.lower() and suffix in {".txt", ".zip"} and len(path.resolve().relative_to(ROOT).parts) == 1:
                candidates.append(Candidate(rel(path), "file", "old_root_patch_artifact", "low"))

    # de-duplicate and remove children of selected directories
    unique: Dict[str, Candidate] = {}
    for item in candidates:
        unique[item.rel] = item
    sorted_candidates = sorted(unique.values(), key=lambda c: (c.rel.count("/"), c.rel.lower()))
    selected: List[Candidate] = []
    selected_dirs: List[str] = []
    for item in sorted_candidates:
        if any(item.rel == d or item.rel.startswith(d + "/") for d in selected_dirs):
            continue
        selected.append(item)
        if item.kind == "dir":
            selected_dirs.append(item.rel)

    return {
        "root": str(ROOT),
        "scanned_file_count": file_count,
        "scanned_dir_count": dir_count,
        "file_categories": categories,
        "top_dirs": top_dirs,
        "candidates": [asdict(c) for c in selected],
        "candidate_count": len(selected),
        "report_only_patch_dirs": sorted(set(report_only_patch)),
        "protected_seen_count": len(protected_seen),
        "protected_seen_sample": protected_seen[:200],
        "never_touch": sorted(PROTECTED_TOP | PROTECTED_FILE_NAMES | {r"C:\SwitchMapData\backups"}),
        "risk_scope": {
            "code_behavior_change": "NO",
            "database_change": "NO",
            "credential_change": "NO",
            "backup_storage_change": "NO",
            "restore_enable_change": "NO",
            "quarantine_only": "YES",
        },
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_for_backup(src: Path, dst: Path) -> None:
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        ensure_parent(dst)
        shutil.copy2(src, dst)


def move_to_quarantine(candidates: List[Dict]) -> List[MoveRecord]:
    moved: List[MoveRecord] = []
    if not candidates:
        return moved
    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
    CHANGE_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for item in candidates:
        src = path_from_rel(item["rel"])
        if not src.exists():
            continue
        if is_protected(src):
            continue
        qdst = QUARANTINE_ROOT / Path(item["rel"].replace("/", os.sep))
        bdst = CHANGE_BACKUP_ROOT / Path(item["rel"].replace("/", os.sep))
        copy_for_backup(src, bdst)
        ensure_parent(qdst)
        shutil.move(str(src), str(qdst))
        moved.append(
            MoveRecord(
                rel=item["rel"],
                kind=item["kind"],
                reason=item["reason"],
                original=str(src),
                quarantine=str(qdst),
                backup=str(bdst),
            )
        )
        print(f"QUARANTINED={item['rel']} reason={item['reason']}")
    return moved


def write_rollback_cmd(moved: List[MoveRecord]) -> None:
    lines = [
        "@echo off",
        "setlocal EnableExtensions",
        "cd /d C:\\SwitchMap",
        f"echo {PHASE}_ROLLBACK_START",
    ]
    for rec in reversed(moved):
        q = rec.quarantine
        o = rec.original
        lines.append(f"if not exist \"{o}\" if exist \"{q}\" move /Y \"{q}\" \"{o}\" >nul")
    lines.append(f"echo {PHASE}_ROLLBACK_DONE")
    lines.append("exit /b 0")
    ROLLBACK_CMD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rollback(moved: List[MoveRecord]) -> List[str]:
    messages: List[str] = []
    for rec in reversed(moved):
        original = Path(rec.original)
        quarantine = Path(rec.quarantine)
        if original.exists():
            messages.append(f"ROLLBACK_SKIP_EXISTS={rec.rel}")
            continue
        if not quarantine.exists():
            messages.append(f"ROLLBACK_MISSING_QUARANTINE={rec.rel}")
            continue
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(quarantine), str(original))
        messages.append(f"ROLLBACK_RESTORED={rec.rel}")
    return messages


def run_cmd(args: List[str], name: str, *, check: bool = True, allow_codes: Optional[Iterable[int]] = None) -> subprocess.CompletedProcess:
    allow = set(allow_codes or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    print(f"STEP_START={name}")
    print("CMD=" + " ".join(args))
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    print(f"STEP_EXIT={name}:{proc.returncode}")
    if check and proc.returncode != 0 and proc.returncode not in allow:
        raise Phase91Error(f"{name} failed rc={proc.returncode}")
    return proc


def py_compile_core() -> Dict:
    print("STEP_START=py_compile_core")
    temp_dir = Path(tempfile.mkdtemp(prefix="switchmap_phase91_pycompile_"))
    total = 0
    failures: List[Tuple[str, str]] = []
    try:
        paths = []
        for filename in CORE_ROOT_PY_FILES:
            path = ROOT / filename
            if path.exists() and not is_protected(path):
                paths.append(path)
        for base in CORE_PY_DIRS:
            base_path = ROOT / base
            if not base_path.exists():
                continue
            for path in base_path.rglob("*.py"):
                if is_protected(path) or "__pycache__" in path.parts:
                    continue
                paths.append(path)
        for path in sorted(set(paths), key=lambda p: str(p.relative_to(ROOT)).lower()):
            total += 1
            cfile = temp_dir / path.relative_to(ROOT).with_suffix(".pyc")
            cfile.parent.mkdir(parents=True, exist_ok=True)
            try:
                py_compile.compile(str(path), cfile=str(cfile), doraise=True)
            except Exception as exc:
                failures.append((rel(path), str(exc)))
        if failures:
            for item in failures[:50]:
                print(f"PY_COMPILE_FAIL={item[0]} :: {item[1]}")
            raise Phase91Error(f"py_compile failed count={len(failures)}")
        print(f"PY_COMPILE_OK={total}")
        print("STEP_EXIT=py_compile_core:0")
        return {"total": total, "failures": failures}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import django

    django.setup()


def verify_urls_and_pages() -> Dict:
    print("STEP_START=url_reverse_resolve_http_guard")
    setup_django()
    from django.test import Client
    from django.urls import resolve, reverse

    reversed_urls: Dict[str, str] = {}
    for name, args in URL_NAMES:
        if args is None:
            reversed_urls[name] = reverse(name)
        else:
            reversed_urls[name] = reverse(name, args=args)
        print(f"URL_REVERSE_OK={name} => {reversed_urls[name]}")

    resolved_paths: Dict[str, str] = {}
    for path in URL_PATHS:
        match = resolve(path)
        resolved_paths[path] = str(match.url_name)
        print(f"URL_RESOLVE_OK={path} => {match.url_name}")

    client = Client(HTTP_HOST="it-tools.winac-co.com")
    statuses: Dict[str, int] = {}
    for path in URL_PATHS:
        response = client.get(path, follow=False)
        statuses[path] = int(response.status_code)
        print(f"HTTP_STATUS={path}:{response.status_code}")
        if response.status_code >= 500:
            raise Phase91Error(f"HTTP 500 guard failed for {path}")
    print("STEP_EXIT=url_reverse_resolve_http_guard:0")
    return {"reverse": reversed_urls, "resolve": resolved_paths, "http_status": statuses}


def restore_guard() -> Dict:
    print("STEP_START=restore_guard")
    urls_py = (ROOT / "inventory" / "urls.py").read_text(encoding="utf-8", errors="ignore")
    url_restore_lines = [line.strip() for line in urls_py.splitlines() if "restore" in line.lower()]
    bad_url_lines = [line for line in url_restore_lines if "validate-restore" not in line and "backup_validate_restore" not in line]
    if bad_url_lines:
        for line in bad_url_lines:
            print(f"RESTORE_GUARD_BAD_URL={line}")
        raise Phase91Error("real restore URL guard failed")

    dangerous_function_re = re.compile(
        r"def\s+\w*(?:execute|apply|run)_?restore\w*|def\s+\w*restore_?(?:execute|apply|run)\w*",
        re.IGNORECASE,
    )
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
        raise Phase91Error(f"restore guard dangerous hit count={len(bad_hits)}")
    print("RESTORE_GUARD_OK=validate_restore_only")
    print("STEP_EXIT=restore_guard:0")
    return {"restore_url_lines": url_restore_lines, "dangerous_hits": []}


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
        for line in output.splitlines():
            if line.lower().startswith("last result:"):
                last_result = line.split(":", 1)[1].strip()
            if line.lower().startswith("status:"):
                status = line.split(":", 1)[1].strip()
        print(f"TASK_STATUS={task_name}:{status}")
        print(f"TASK_LAST_RESULT={task_name}:{last_result}")
        if task_name == "SwitchMap Scheduled Backup Daily" and last_result and last_result not in {"0", "0x0"}:
            raise Phase91Error(f"Scheduled Backup Last Result is not 0: {last_result}")
        results[task_name] = {"status": status, "last_result": last_result}
    print("STEP_EXIT=scheduled_task_guard:0")
    return results


def restart_waitress_after_success() -> Dict:
    print("STEP_START=waitress_restart_after_success")
    if os.name != "nt":
        print("WAITRESS_RESTART_SKIPPED=non_windows_runtime")
        return {"skipped": True}
    end_proc = run_cmd(["schtasks", "/End", "/TN", "SwitchMap Waitress"], "waitress_end", check=False)
    print(f"WAITRESS_END_RC={end_proc.returncode}")
    time.sleep(2)
    run_proc = run_cmd(["schtasks", "/Run", "/TN", "SwitchMap Waitress"], "waitress_run", check=True)
    print(f"WAITRESS_RUN_RC={run_proc.returncode}")
    print("STEP_EXIT=waitress_restart_after_success:0")
    return {"end_rc": end_proc.returncode, "run_rc": run_proc.returncode}


def verify_all() -> Dict:
    result: Dict[str, object] = {}
    python_exe = sys.executable
    result["manage_check"] = run_cmd([python_exe, "manage.py", "check"], "django_manage_check").returncode
    result["py_compile"] = py_compile_core()
    result["urls"] = verify_urls_and_pages()
    result["restore_guard"] = restore_guard()
    result["scheduled_tasks"] = scheduled_task_guard()
    result["backup_storage_verify"] = run_cmd([python_exe, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict").returncode
    result["backup_health_report"] = run_cmd([python_exe, "manage.py", "backup_health_report", "--strict"], "backup_health_report_strict").returncode
    return result


def write_report(report: Dict) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    REPORT_JSON.write_text(text, encoding="utf-8")
    LATEST_JSON.write_text(text, encoding="utf-8")
    lines = [
        f"{PHASE}_PROJECT_CLEANUP_REFINE_VERIFY_REPORT",
        f"STATUS={report.get('status')}",
        f"ROOT={ROOT}",
        f"GENERATED_AT={report.get('generated_at')}",
        f"SCANNED_FILES={report.get('scan', {}).get('scanned_file_count')}",
        f"CANDIDATES={report.get('scan', {}).get('candidate_count')}",
        f"QUARANTINED={len(report.get('quarantined', []))}",
        f"QUARANTINE_ROOT={report.get('quarantine_root')}",
        f"CHANGE_BACKUP_ROOT={report.get('change_backup_root')}",
        f"ROLLBACK_CMD={report.get('rollback_cmd')}",
        f"ERROR={report.get('error', '')}",
    ]
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LATEST_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print(f"{PHASE}_ROOT={ROOT}")
    print(f"{PHASE}_REPORT_JSON={REPORT_JSON}")
    moved: List[MoveRecord] = []
    scan = scan_project()
    report: Dict = {
        "marker": f"{PHASE}_PROJECT_CLEANUP_REFINE_FINAL_VERIFY",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "STARTED",
        "root": str(ROOT),
        "scan": scan,
        "quarantine_root": str(QUARANTINE_ROOT),
        "change_backup_root": str(CHANGE_BACKUP_ROOT),
        "rollback_cmd": str(ROLLBACK_CMD),
        "quarantined": [],
        "rollback_messages": [],
        "verify": {},
        "service_restart": {},
        "error": "",
    }

    print(f"SCAN_FILES={scan['scanned_file_count']}")
    print(f"SCAN_DIRS={scan['scanned_dir_count']}")
    print(f"CANDIDATES={scan['candidate_count']}")
    print(f"PROTECTED_SEEN={scan['protected_seen_count']}")

    try:
        moved = move_to_quarantine(scan["candidates"])
        write_rollback_cmd(moved)
        report["quarantined"] = [asdict(m) for m in moved]
        report["status"] = "QUARANTINED_VERIFYING"
        write_report(report)

        report["verify"] = verify_all()
        report["service_restart"] = {"skipped": True, "reason": "cleanup_quarantine_only_no_runtime_restart_required"}
        print("WAITRESS_RESTART_SKIPPED=cleanup_quarantine_only_no_runtime_restart_required")
        report["status"] = "OK"
        write_report(report)
        print(f"{PHASE}_FINAL_OK=True")
        print(f"REPORT_JSON={REPORT_JSON}")
        print(f"REPORT_TXT={REPORT_TXT}")
        print(f"ROLLBACK_CMD={ROLLBACK_CMD}")
        return 0
    except Exception as exc:
        print(f"{PHASE}_FAIL={exc}")
        report["error"] = str(exc)
        try:
            rollback_messages = rollback(moved)
            for message in rollback_messages:
                print(message)
            report["rollback_messages"] = rollback_messages
            report["status"] = "FAILED_ROLLED_BACK"
        except Exception as rb_exc:
            print(f"{PHASE}_ROLLBACK_FAIL={rb_exc}")
            report["rollback_messages"] = [f"ROLLBACK_FAIL={rb_exc}"]
            report["status"] = "FAILED_ROLLBACK_ERROR"
        write_report(report)
        print(f"REPORT_JSON={REPORT_JSON}")
        print(f"REPORT_TXT={REPORT_TXT}")
        print(f"ROLLBACK_CMD={ROLLBACK_CMD}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
