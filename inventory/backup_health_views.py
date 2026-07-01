from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


PHASE90_MARKER = "PHASE90_4_BACKUP_HEALTH_UI_SAFE_REVIEWED"


def _safe_read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _backup_root() -> Path:
    return Path(r"C:\SwitchMapData\backups")


def _project_root() -> Path:
    return Path(getattr(settings, "BASE_DIR", r"C:\SwitchMap"))


def _log_root() -> Path:
    return _project_root() / "logs"


def _metadata_root() -> Path:
    return _backup_root() / "metadata"


def _rows_from_index(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("rows", "backups", "items", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        rows: List[Dict[str, Any]] = []
        for value in data.values():
            if isinstance(value, dict):
                rows.append(value)
            elif isinstance(value, list):
                rows.extend([x for x in value if isinstance(x, dict)])
        return rows
    return []


def _first(row: Dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return default


def _row_success(row: Dict[str, Any]) -> bool:
    value = row.get("success")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "ok", "success", "done"}
    status = _first(row, ("status", "result"), "").strip().lower()
    return status in {"ok", "success", "done"}


def _latest_backups() -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    indexes = [
        ("cisco", _metadata_root() / "cisco_backup_index.json"),
        ("mikrotik", _metadata_root() / "mikrotik_backup_index.json"),
    ]
    latest: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    total_rows = 0
    success_rows = 0
    failed_rows = 0

    for family, path in indexes:
        data = _safe_read_json(path, [])
        rows = _rows_from_index(data)
        total_rows += len(rows)
        for row in rows:
            ok = _row_success(row)
            if ok:
                success_rows += 1
            else:
                failed_rows += 1
                continue
            device = _first(row, ("device_name", "switch_name", "switch", "device", "name", "hostname"), "unknown")
            backup_type = _first(row, ("backup_type", "type", "kind"), "unknown")
            created_at = _first(row, ("created_at", "timestamp", "time", "date"), "")
            file_name = _first(row, ("file_name", "filename"), "")
            file_path = _first(row, ("file_path", "path", "local_path"), "")
            size = _first(row, ("size", "size_bytes"), "")
            key = (family, device, backup_type)
            current = latest.get(key)
            if current is None or created_at >= current.get("created_at", ""):
                latest[key] = {
                    "family": family,
                    "device": device,
                    "backup_type": backup_type,
                    "created_at": created_at,
                    "file_name": file_name or Path(file_path).name,
                    "size": size,
                }

    rows_sorted = sorted(latest.values(), key=lambda x: (x["family"], x["device"], x["backup_type"]))
    return rows_sorted, {"total_rows": total_rows, "success_rows": success_rows, "failed_rows": failed_rows}


def _run_manage_command(args: List[str], timeout: int = 900) -> Tuple[int, str]:
    cmd = [sys.executable, str(_project_root() / "manage.py"), *args]
    proc = subprocess.run(
        cmd,
        cwd=str(_project_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or ""


def _profile_admin(user) -> bool:
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    for attr in ("role", "user_role", "access_level"):
        value = getattr(profile, attr, "")
        if str(value).strip().lower() in {"admin", "administrator"}:
            return True
        name = getattr(value, "name", "")
        if str(name).strip().lower() in {"admin", "administrator"}:
            return True
    return False


def _is_admin(user) -> bool:
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        if user.groups.filter(name__iexact="Admin").exists():
            return True
    except Exception:
        pass
    return _profile_admin(user)


@login_required
@require_http_methods(["GET", "POST"])
def backup_health_dashboard(request):
    is_admin = _is_admin(request.user)

    if request.method == "POST":
        action = request.POST.get("action", "")
        keep = request.POST.get("keep", "30").strip() or "30"
        if not keep.isdigit():
            keep = "30"

        if action == "retention_dry_run":
            status, output = _run_manage_command(["backup_retention_cleanup", "--keep", keep])
            if status == 0:
                messages.success(request, "Retention dry-run completed.")
            else:
                messages.error(request, "Retention dry-run failed. Check logs.")
        elif action == "retention_apply":
            confirm = request.POST.get("confirm", "")
            if not is_admin:
                messages.error(request, "Only Admin can apply retention cleanup.")
            elif confirm != "DELETE_OLD_BACKUPS":
                messages.error(request, "Confirm text is invalid. No file deleted.")
            else:
                status, output = _run_manage_command([
                    "backup_retention_cleanup", "--keep", keep, "--apply", "--confirm", "DELETE_OLD_BACKUPS"
                ], timeout=1800)
                if status == 0:
                    messages.success(request, "Retention apply completed.")
                else:
                    messages.error(request, "Retention apply failed. Check logs.")
        elif action == "health_refresh":
            status, output = _run_manage_command(["backup_health_report"])
            if status == 0:
                messages.success(request, "Backup health report refreshed.")
            else:
                messages.error(request, "Backup health report refresh failed.")
        return redirect("inventory:backup_health_dashboard")

    policy = _safe_read_json(_metadata_root() / "backup_schedule_policy.json", {})
    health = _safe_read_json(_log_root() / "backup_health_report_latest.json", {})
    retention = _safe_read_json(_log_root() / "backup_retention_latest.json", {})
    latest_rows, index_stats = _latest_backups()

    health_ok = bool(health.get("health_ok") or health.get("HEALTH_OK") or health.get("ok") or health.get("OK"))
    expected = health.get("expected_count") or health.get("EXPECTED") or health.get("expected") or ""
    ok_count = health.get("ok_count") or health.get("OK") or health.get("ok") or ""
    missing = health.get("missing_count") or health.get("MISSING") or health.get("missing") or 0
    stale = health.get("stale_count") or health.get("STALE") or health.get("stale") or 0
    health_items = health.get("items") if isinstance(health.get("items"), list) else []
    health_issue_items = [x for x in health_items if isinstance(x, dict) and x.get("status") != "OK"]

    context = {
        "phase90_marker": PHASE90_MARKER,
        "policy": policy,
        "health": health,
        "health_ok": health_ok,
        "expected": expected,
        "ok_count": ok_count,
        "missing": missing,
        "stale": stale,
        "health_items": health_items,
        "health_issue_items": health_issue_items,
        "retention": retention,
        "latest_rows": latest_rows,
        "index_stats": index_stats,
        "is_admin": is_admin,
        "backup_root": str(_backup_root()),
        "policy_path": str(_metadata_root() / "backup_schedule_policy.json"),
        "health_report_path": str(_log_root() / "backup_health_report_latest.json"),
        "retention_report_path": str(_log_root() / "backup_retention_latest.json"),
    }
    return render(request, "inventory/backup_health_dashboard.html", context)
