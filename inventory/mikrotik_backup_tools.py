from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

from .models import Switch
from .ssh_tools import SshActionError

PHASE85_MARKER = "PHASE85_MIKROTIK_BACKUP_CENTER"

BACKUP_ROOT = Path(os.environ.get("SWITCHMAP_BACKUP_ROOT", r"C:\SwitchMapData\backups"))
MIKROTIK_DIR = BACKUP_ROOT / "mikrotik"
METADATA_DIR = BACKUP_ROOT / "metadata"
LOG_DIR = BACKUP_ROOT / "logs"
INDEX_PATH = METADATA_DIR / "mikrotik_backup_index.json"

BACKUP_TYPE_LABELS = {
    "export": "Export RSC",
    "full-backup": "Full Binary Backup",
}

EXTENSIONS = {
    "export": "rsc",
    "full-backup": "backup",
}

COMMANDS = {
    "export": "/export",
    "full-backup": "/system backup save name=<generated>",
}

INVALID_CLI_MARKERS = (
    "bad command name",
    "failure:",
    "syntax error",
    "interrupted",
    "invalid value",
    "expected end of command",
    "permission denied",
    "authentication failed",
)

PROMPT_RE = re.compile(r"^\[.*@.*\]\s*[>/#]\s*$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
MASK_TOKEN = "<MASKED_BY_SWITCHMAP>"

SENSITIVE_PATTERNS = (
    re.compile(r"(password=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(secret=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(shared-secret=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(authentication-key=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(wpa(?:2|3)?-pre-shared-key=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(private-key=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(private-key-file=)(\"[^\"]*\"|\S+)", re.I),
    re.compile(r"(passphrase=)(\"[^\"]*\"|\S+)", re.I),
)


def setup_storage() -> None:
    MIKROTIK_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _safe_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^A-Za-z0-9_.\-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-._")
    return text or fallback


def _jalali_from_gregorian(year: int, month: int, day: int) -> Tuple[int, int, int]:
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    gy = year - 1600
    gm = month - 1
    gd = day - 1
    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((gy + 1600) % 4 == 0 and ((gy + 1600) % 100 != 0 or (gy + 1600) % 400 == 0)):
        g_day_no += 1
    g_day_no += gd
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    jm = 0
    while jm < 11 and j_day_no >= j_days_in_month[jm]:
        j_day_no -= j_days_in_month[jm]
        jm += 1
    return jy, jm + 1, j_day_no + 1


def jalali_date_text(value=None) -> str:
    value = value or timezone.localtime()
    jy, jm, jd = _jalali_from_gregorian(value.year, value.month, value.day)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def _read_index() -> List[Dict]:
    setup_storage()
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _write_index(items: List[Dict]) -> None:
    setup_storage()
    tmp = INDEX_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(INDEX_PATH)


def _append_metadata(row: Dict) -> Dict:
    items = [item for item in _read_index() if item.get("backup_id") != row.get("backup_id")]
    items.append(row)
    _write_index(items)
    return row


def _file_hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content or b"").hexdigest()


def _backup_id(switch: Switch, backup_type: str, created_at, content_hash: str) -> str:
    base = f"{switch.id}:{switch.name}:{backup_type}:{created_at.isoformat()}:{content_hash}"
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _filename(switch: Switch, backup_type: str, created_at) -> str:
    jdate = jalali_date_text(created_at)
    t = timezone.localtime(created_at).strftime("%H%M%S")
    suffix = "export" if backup_type == "export" else "full"
    ext = EXTENSIONS.get(backup_type, "txt")
    return f"{_safe_text(switch.name)}__{jdate}__{t}__{suffix}.{ext}"


def is_mikrotik_switch(switch: Switch) -> bool:
    parts = []
    for field in ("vendor", "device_family", "model", "name", "notes"):
        try:
            parts.append(str(getattr(switch, field, "") or ""))
        except Exception:
            pass
    text = " ".join(parts).lower()
    return any(token in text for token in ("mikrotik", "routeros", "routerboard", "rb", "crs", "haph", "hap", "hex")) and "cisco" not in text


def mikrotik_switches():
    return [sw for sw in Switch.objects.filter(is_active=True).order_by("topology_position", "name") if is_mikrotik_switch(sw)]


def list_backups(limit: int = 500, device_id: Optional[int] = None, backup_type: str = "") -> List[Dict]:
    rows = _read_index()
    if device_id:
        rows = [row for row in rows if int(row.get("device_id") or 0) == int(device_id)]
    if backup_type:
        rows = [row for row in rows if row.get("backup_type") == backup_type]
    rows.sort(key=lambda item: (item.get("created_at") or "", item.get("backup_id") or ""), reverse=True)
    return rows[:limit]


def find_backup(backup_id: str) -> Optional[Dict]:
    backup_id = str(backup_id or "").strip()
    for row in _read_index():
        if row.get("backup_id") == backup_id:
            return row
    return None


def latest_previous_backup(switch_id: int, backup_type: str, before_backup_id: str = "") -> Optional[Dict]:
    rows = [
        row for row in _read_index()
        if int(row.get("device_id") or 0) == int(switch_id)
        and row.get("backup_type") == backup_type
        and bool(row.get("success"))
        and row.get("file_path")
    ]
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    if before_backup_id:
        seen = False
        for row in rows:
            if row.get("backup_id") == before_backup_id:
                seen = True
                continue
            if seen:
                return row
        return None
    return rows[0] if rows else None


def read_backup_bytes(row: Dict) -> bytes:
    raw_path = str(row.get("file_path") or "").strip()
    if not raw_path:
        return b""
    path = Path(raw_path)
    try:
        resolved = path.resolve()
        root = MIKROTIK_DIR.resolve()
    except Exception:
        return b""
    if not path.exists():
        return b""
    if root not in resolved.parents and resolved != root:
        return b""
    try:
        return path.read_bytes()
    except Exception:
        return b""


def read_backup_content(row: Dict) -> str:
    data = read_backup_bytes(row)
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def mask_sensitive_export(content: str) -> Tuple[str, int]:
    lines = (content or "").replace("\r", "").split("\n")
    out = []
    count = 0
    for line in lines:
        new_line = line
        for pattern in SENSITIVE_PATTERNS:
            def repl(match):
                nonlocal count
                count += 1
                return match.group(1) + MASK_TOKEN
            new_line = pattern.sub(repl, new_line)
        out.append(new_line)
    return "\n".join(out), count


def safe_content_preview(content: str, limit: int = 80000) -> str:
    return mask_sensitive_export(content or "")[0][:limit]


def safe_diff(previous_content: str, current_content: str, *, previous_name: str = "previous", current_name: str = "current") -> str:
    previous_masked, _ = mask_sensitive_export(previous_content or "")
    current_masked, _ = mask_sensitive_export(current_content or "")
    return "\n".join(difflib.unified_diff(previous_masked.splitlines(), current_masked.splitlines(), fromfile=previous_name, tofile=current_name, lineterm=""))[:300000]


def _require_paramiko():
    try:
        import paramiko  # type: ignore
        return paramiko
    except Exception as exc:  # pragma: no cover
        raise SshActionError("Paramiko نصب نیست یا قابل Import نیست.") from exc


def _connect(switch: Switch, username: str, password: str):
    if not switch.ssh_enabled:
        raise SshActionError("SSH برای این دستگاه فعال نیست.")
    username = (username or switch.ssh_username or "").strip()
    if not username:
        raise SshActionError("Username خالی است.")
    if not password:
        raise SshActionError("Password خالی است.")
    paramiko = _require_paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(str(switch.management_ip), port=int(switch.ssh_port or 22), username=username, password=password, look_for_keys=False, allow_agent=False, timeout=15, auth_timeout=15, banner_timeout=15)
        return client
    except paramiko.AuthenticationException as exc:
        try:
            client.close()
        except Exception:
            pass
        raise SshActionError("SSH Authentication failed.") from exc
    except Exception as exc:
        try:
            client.close()
        except Exception:
            pass
        raise SshActionError(str(exc)) from exc


def _clean_routeros_output(raw: str, command: str) -> str:
    raw = ANSI_RE.sub("", raw or "").replace("\r", "")
    cleaned = []
    command = (command or "").strip()
    for line in raw.split("\n"):
        text = line.rstrip()
        stripped = text.strip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped == command or stripped.endswith(" " + command):
            continue
        if PROMPT_RE.match(stripped):
            continue
        cleaned.append(text)
    return "\n".join(cleaned).strip()


def run_routeros_command(switch: Switch, username: str, password: str, command: str, *, timeout: int = 70) -> str:
    client = _connect(switch, username, password)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        # RouterOS sometimes writes nothing until command finishes.
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        content = _clean_routeros_output(out + ("\n" + err if err else ""), command)
        low = content.lower()
        if any(marker in low for marker in INVALID_CLI_MARKERS):
            raise SshActionError(content[:500] or "RouterOS CLI error")
        return content
    finally:
        try:
            client.close()
        except Exception:
            pass


def validate_export_content(content: str) -> Tuple[bool, str]:
    text = (content or "").replace("\r", "").strip()
    low = text.lower()
    if len(text.encode("utf-8", errors="ignore")) < 80:
        return False, "Export output too small."
    if any(marker in low for marker in INVALID_CLI_MARKERS):
        return False, "RouterOS CLI error marker found."
    markers = ("/interface", "/ip", "/system", "/routing", "/tool", "add ", "set ", "#")
    if not any(marker in low for marker in markers):
        return False, "RouterOS export markers not found."
    return True, ""


def validate_full_backup_bytes(data: bytes) -> Tuple[bool, str]:
    if not data or len(data) < 256:
        return False, "Full backup file too small."
    return True, ""


def _store_file(*, switch: Switch, backup_type: str, content: bytes, created_by: str, source: str, command: str, success: bool = True, error: str = "") -> Dict:
    setup_storage()
    created_at = timezone.localtime()
    content_hash = _file_hash_bytes(content if success else f"{switch.id}:{backup_type}:{created_at.isoformat()}:{error}".encode("utf-8"))
    backup_id = _backup_id(switch, backup_type, created_at, content_hash)
    row = {
        "backup_id": backup_id,
        "device_id": switch.id,
        "device": switch.name,
        "model": switch.model,
        "management_ip": str(switch.management_ip),
        "backup_type": backup_type,
        "backup_type_label": BACKUP_TYPE_LABELS.get(backup_type, backup_type),
        "command": command,
        "source": source,
        "created_by": created_by or "",
        "created_at": created_at.isoformat(),
        "jalali_date": jalali_date_text(created_at),
        "file_hash": content_hash if success else "",
        "size": len(content) if success else 0,
        "success": bool(success),
        "error": error or "",
        "filename": "",
        "file_path": "",
        "diff_path": "",
        "previous_backup_id": "",
        "ui_preview": "masked" if backup_type == "export" else "metadata-only",
        "download_scope": "admin-only",
        "sensitive_line_count": 0,
    }
    if success:
        filename = _filename(switch, backup_type, created_at)
        device_dir = MIKROTIK_DIR / _safe_text(switch.name)
        device_dir.mkdir(parents=True, exist_ok=True)
        file_path = device_dir / filename
        file_path.write_bytes(content)
        row["filename"] = filename
        row["file_path"] = str(file_path)
        if backup_type == "export":
            text = content.decode("utf-8", errors="replace")
            row["sensitive_line_count"] = mask_sensitive_export(text)[1]
            previous = latest_previous_backup(switch.id, backup_type)
            if previous:
                previous_content = read_backup_content(previous)
                diff_text = safe_diff(previous_content, text, previous_name=previous.get("filename", "previous"), current_name=filename)
                if diff_text:
                    diff_path = device_dir / f"{filename}.diff.txt"
                    diff_path.write_text(diff_text, encoding="utf-8", errors="ignore")
                    row["diff_path"] = str(diff_path)
                    row["previous_backup_id"] = previous.get("backup_id", "")
    return _append_metadata(row)


def save_backup_failure(*, switch: Switch, backup_type: str, command: str, error: str, created_by: str = "", source: str = "manual-ssh") -> Dict:
    return _store_file(switch=switch, backup_type=backup_type, content=b"", created_by=created_by, source=source, command=command, success=False, error=str(error or "Backup failed"))


def run_export_backup(*, switch: Switch, username: str, password: str, created_by: str = "", source: str = "manual-ssh") -> Dict:
    command = "/export"
    content = run_routeros_command(switch, username, password, command, timeout=80)
    ok, reason = validate_export_content(content)
    if not ok:
        raise SshActionError(reason)
    return _store_file(switch=switch, backup_type="export", content=content.encode("utf-8", errors="ignore"), created_by=created_by, source=source, command=command)


def run_full_backup(*, switch: Switch, username: str, password: str, created_by: str = "", source: str = "manual-ssh") -> Dict:
    client = _connect(switch, username, password)
    remote_base = f"switchmap-{_safe_text(switch.name)}-{int(time.time())}"
    remote_file = f"{remote_base}.backup"
    command = f"/system backup save name={remote_base}"
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        out = stdout.read().decode("utf-8", errors="ignore") + stderr.read().decode("utf-8", errors="ignore")
        if any(marker in out.lower() for marker in INVALID_CLI_MARKERS):
            raise SshActionError(out[:500] or "RouterOS backup save failed")
        time.sleep(1.0)
        try:
            sftp = client.open_sftp()
        except Exception as exc:
            raise SshActionError("SFTP برای دریافت full backup در RouterOS/SSH فعال یا قابل استفاده نیست.") from exc
        try:
            with sftp.open(remote_file, "rb") as handle:
                data = handle.read()
        finally:
            try:
                sftp.remove(remote_file)
            except Exception:
                pass
            try:
                sftp.close()
            except Exception:
                pass
        ok, reason = validate_full_backup_bytes(data)
        if not ok:
            raise SshActionError(reason)
        return _store_file(switch=switch, backup_type="full-backup", content=data, created_by=created_by, source=source, command=command)
    finally:
        try:
            client.close()
        except Exception:
            pass


def run_single_backup(*, switch: Switch, backup_type: str, username: str, password: str, created_by: str = "", source: str = "manual-ssh") -> Dict:
    if backup_type == "export":
        return run_export_backup(switch=switch, username=username, password=password, created_by=created_by, source=source)
    if backup_type == "full-backup":
        return run_full_backup(switch=switch, username=username, password=password, created_by=created_by, source=source)
    raise SshActionError("backup_type نامعتبر است.")


def validate_restore_candidate(row: Dict) -> Dict:
    backup_type = row.get("backup_type") or ""
    blockers = []
    warnings = []
    if backup_type == "export":
        content = read_backup_content(row)
        ok, reason = validate_export_content(content)
        if not ok:
            blockers.append(reason)
        masked, sensitive_count = mask_sensitive_export(content)
        if sensitive_count:
            warnings.append(f"{sensitive_count} مقدار حساس در Preview ماسک شده است.")
        if "\n/system identity" in content or "/system identity" in content:
            warnings.append("Import ممکن است identity/system values را تغییر دهد.")
        return {"ok": not blockers, "blockers": blockers, "warnings": warnings, "line_count": len(content.splitlines()), "dry_run_only": True, "message": "Restore واقعی در Phase85 اجرا نمی‌شود؛ فقط Validate/Dry-run است."}
    if backup_type == "full-backup":
        data = read_backup_bytes(row)
        ok, reason = validate_full_backup_bytes(data)
        if not ok:
            blockers.append(reason)
        warnings.append("Full backup باینری برای همان دستگاه/RouterOS مناسب‌تر است و Restore واقعی بسیار پرریسک است.")
        return {"ok": not blockers, "blockers": blockers, "warnings": warnings, "line_count": 0, "dry_run_only": True, "message": "Restore کامل MikroTik در این فاز فقط Prepare است و اجرا نمی‌شود."}
    return {"ok": False, "blockers": ["backup_type نامعتبر است."], "warnings": [], "line_count": 0, "dry_run_only": True, "message": "نامعتبر"}
