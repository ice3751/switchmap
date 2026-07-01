from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from .models import Switch
from .ssh_tools import SshActionError

PHASE84_MARKER = "PHASE84_CISCO_BACKUP_CENTER"

BACKUP_ROOT = Path(os.environ.get("SWITCHMAP_BACKUP_ROOT", r"C:\SwitchMapData\backups"))
CISCO_DIR = BACKUP_ROOT / "cisco"
METADATA_DIR = BACKUP_ROOT / "metadata"
LOG_DIR = BACKUP_ROOT / "logs"
INDEX_PATH = METADATA_DIR / "cisco_backup_index.json"

COMMANDS = {
    "running-config": "show running-config",
    "startup-config": "show startup-config",
    "version": "show version",
    "inventory": "show inventory",
}

EXTENSIONS = {
    "running-config": "txt",
    "startup-config": "txt",
    "version": "txt",
    "inventory": "txt",
}

BACKUP_TYPE_LABELS = {
    "running-config": "Running Config",
    "startup-config": "Startup Config",
    "version": "Version",
    "inventory": "Inventory",
}

DANGEROUS_RESTORE_PATTERNS = (
    re.compile(r"^\s*crypto\s+key\s+", re.I),
    re.compile(r"^\s*username\s+\S+\s+privilege\s+15\s+secret\s+", re.I),
    re.compile(r"^\s*enable\s+secret\s+", re.I),
    re.compile(r"^\s*interface\s+vlan\s+\d+", re.I),
    re.compile(r"^\s*ip\s+route\s+", re.I),
    re.compile(r"^\s*router\s+\w+", re.I),
    re.compile(r"^\s*line\s+vty\s+", re.I),
    re.compile(r"^\s*aaa\s+", re.I),
)


MIN_VALID_SIZE = {
    "running-config": 200,
    "startup-config": 200,
    "version": 200,
    "inventory": 50,
}

INVALID_CLI_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "unknown command",
    "authorization failed",
    "authentication failed",
)

PROMPT_RE = re.compile(r"^[\w.()/:@\-]+(?:\([^)]+\))?[#>]\s*$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# PHASE84_3_CISCO_BACKUP_SECURITY_HARDENING
SENSITIVE_LINE_PATTERNS = (
    re.compile(r"^(\s*enable\s+(?:secret|password)\b).*$", re.I),
    re.compile(r"^(\s*username\s+\S+.*\b(?:secret|password)\b).*$", re.I),
    re.compile(r"^(\s*snmp-server\s+community\s+)\S+(.*)$", re.I),
    re.compile(r"^(\s*snmp-server\s+user\s+\S+\s+\S+.*\b(?:auth|priv)\b).*$", re.I),
    re.compile(r"^(\s*(?:radius|tacacs)\s+server\s+\S+.*\bkey\b).*$", re.I),
    re.compile(r"^(\s*(?:radius-server|tacacs-server)\s+key\b).*$", re.I),
    re.compile(r"^(\s*key\s+\d+\s+).*$", re.I),
    re.compile(r"^(\s*password\s+\d*\s*).*$", re.I),
    re.compile(r"^(\s*ppp\s+chap\s+password\s+).*$", re.I),
    re.compile(r"^(\s*crypto\s+isakmp\s+key\s+).*$", re.I),
    re.compile(r"^(\s*tunnel\s+protection\s+ipsec\s+profile\s+).*$", re.I),
    re.compile(r"^(\s*private-key\s+).*$", re.I),
)

SENSITIVE_BLOCK_START_PATTERNS = (
    re.compile(r"^\s*crypto\s+pki\s+certificate\s+(?:chain|pool)\b", re.I),
    re.compile(r"^\s*certificate\s+(?:self-signed|ca)\b", re.I),
    re.compile(r"^\s*crypto\s+key\b", re.I),
    re.compile(r"^-+BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-+", re.I),
    re.compile(r"^-+BEGIN\s+CERTIFICATE-+", re.I),
)

SENSITIVE_BLOCK_END_PATTERNS = (
    re.compile(r"^\s*quit\s*$", re.I),
    re.compile(r"^\s*!\s*$"),
    re.compile(r"^-+END\s+(?:RSA\s+)?PRIVATE\s+KEY-+", re.I),
    re.compile(r"^-+END\s+CERTIFICATE-+", re.I),
)

MASK_TOKEN = "<MASKED_BY_SWITCHMAP>"


def mask_sensitive_config(content: str) -> Tuple[str, int]:
    """Return UI-safe content and number of masked sensitive lines/blocks.

    Full backup files are not modified.  This is only for Preview/Diff/Restore dry-run UI.
    """
    lines = (content or "").replace("\r", "").split("\n")
    masked = []
    sensitive_count = 0
    in_block = False
    for line in lines:
        stripped = line.strip()
        if in_block:
            if any(pattern.search(line) for pattern in SENSITIVE_BLOCK_END_PATTERNS):
                masked.append(line)
                in_block = False
            else:
                if not masked or masked[-1].strip() != MASK_TOKEN:
                    masked.append(MASK_TOKEN)
                sensitive_count += 1
            continue
        if any(pattern.search(line) for pattern in SENSITIVE_BLOCK_START_PATTERNS):
            masked.append(line)
            in_block = True
            continue
        replaced = None
        for pattern in SENSITIVE_LINE_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            try:
                if pattern.pattern.startswith("^(\\s*snmp-server\\s+community"):
                    replaced = f"{match.group(1)}{MASK_TOKEN}{match.group(2) or ''}"
                else:
                    replaced = f"{match.group(1)} {MASK_TOKEN}"
            except Exception:
                replaced = MASK_TOKEN
            sensitive_count += 1
            break
        masked.append(replaced if replaced is not None else line)
    return "\n".join(masked), sensitive_count


def safe_content_preview(content: str, limit: int = 80000) -> str:
    masked, _ = mask_sensitive_config(content or "")
    return masked[:limit]


def safe_diff(previous_content: str, current_content: str, *, previous_name: str = "previous", current_name: str = "current") -> str:
    previous_masked, _ = mask_sensitive_config(previous_content or "")
    current_masked, _ = mask_sensitive_config(current_content or "")
    return "\n".join(
        difflib.unified_diff(
            previous_masked.splitlines(),
            current_masked.splitlines(),
            fromfile=previous_name,
            tofile=current_name,
            lineterm="",
        )
    )[:300000]


def audit_backup_security_metadata() -> Dict[str, int]:
    setup_storage()
    rows = _read_index()
    changed = 0
    scanned = 0
    sensitive_rows = 0
    for row in rows:
        if not row.get("success"):
            continue
        content = read_backup_content(row)
        if not content:
            continue
        scanned += 1
        _, count = mask_sensitive_config(content)
        old = int(row.get("sensitive_line_count") or 0)
        if old != count or row.get("ui_preview") != "masked":
            row["sensitive_line_count"] = count
            row["ui_preview"] = "masked"
            row["download_scope"] = "admin-only"
            changed += 1
        if count:
            sensitive_rows += 1
    if changed:
        _write_index(rows)
    return {"scanned": scanned, "changed": changed, "sensitive_rows": sensitive_rows}



def _require_paramiko():
    try:
        import paramiko  # type: ignore
        return paramiko
    except Exception as exc:  # pragma: no cover
        raise SshActionError("Paramiko نصب نیست یا قابل Import نیست.") from exc


def _send_raw(channel, command: str) -> None:
    channel.send(command + "\n")


def _read_until_quiet_or_prompt(channel, *, total_timeout: float, idle_timeout: float = 1.8) -> str:
    output = ""
    start = time.time()
    last_data = None
    while time.time() - start < total_timeout:
        got = False
        while channel.recv_ready():
            chunk = channel.recv(65535).decode("utf-8", errors="ignore")
            if chunk:
                output += chunk
                last_data = time.time()
                got = True
        if last_data is not None:
            lines = [line.strip() for line in output.replace("\r", "").split("\n") if line.strip()]
            tail = lines[-1] if lines else ""
            if PROMPT_RE.match(tail) and time.time() - last_data >= 0.25:
                break
            # If no prompt is seen, do not stop early.  Some Cisco platforms print
            # "Building configuration..." then pause before sending the config.
            if time.time() - last_data >= idle_timeout and PROMPT_RE.match(tail):
                break
        time.sleep(0.08 if got else 0.12)
    return output


def _clean_cisco_output(raw_output: str, command: str) -> str:
    raw_output = ANSI_RE.sub("", raw_output or "").replace("\r", "")
    command_lower = (command or "").strip().lower()
    drop_exact = {
        command_lower,
        "terminal length 0",
        "terminal width 511",
        "terminal no monitor",
    }
    cleaned = []
    for line in raw_output.split("\n"):
        text = line.rstrip()
        stripped = text.strip()
        if not stripped:
            cleaned.append("")
            continue
        low = stripped.lower()
        if low in drop_exact:
            continue
        if PROMPT_RE.match(stripped):
            continue
        if stripped.endswith(command) and "#" in stripped:
            continue
        if stripped.endswith(command) and ">" in stripped:
            continue
        cleaned.append(text)
    content = "\n".join(cleaned).strip()
    return content


def run_cisco_show_command_direct(
    *,
    switch: Switch,
    username: str,
    password: str,
    enable_password: str = "",
    command: str,
    backup_type: str = "",
) -> str:
    if not switch.ssh_enabled:
        raise SshActionError("SSH برای این سوییچ فعال نیست.")
    username = (username or switch.ssh_username or "").strip()
    password = password or ""
    enable_password = enable_password or ""
    if not username:
        raise SshActionError("Username خالی است.")
    if not password:
        raise SshActionError("Password خالی است.")

    paramiko = _require_paramiko()
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            str(switch.management_ip),
            port=int(switch.ssh_port or 22),
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=15,
            auth_timeout=15,
            banner_timeout=15,
        )
        channel = client.invoke_shell(width=240, height=2000)
        _read_until_quiet_or_prompt(channel, total_timeout=3, idle_timeout=0.7)

        for prep in ("terminal length 0", "terminal width 511", "terminal no monitor"):
            _send_raw(channel, prep)
            _read_until_quiet_or_prompt(channel, total_timeout=4, idle_timeout=0.7)

        if enable_password:
            _send_raw(channel, "enable")
            enable_output = _read_until_quiet_or_prompt(channel, total_timeout=4, idle_timeout=0.7)
            if "password" in enable_output.lower():
                _send_raw(channel, enable_password)
                _read_until_quiet_or_prompt(channel, total_timeout=5, idle_timeout=0.7)

        timeout = 65 if backup_type in {"running-config", "startup-config"} else 25
        _send_raw(channel, command)
        raw = _read_until_quiet_or_prompt(channel, total_timeout=timeout, idle_timeout=2.0)
        content = _clean_cisco_output(raw, command)
        lowered = content.lower()
        if any(marker in lowered for marker in INVALID_CLI_MARKERS):
            raise SshActionError("خروجی CLI شامل خطاست.")
        return content
    except paramiko.AuthenticationException as exc:
        raise SshActionError("SSH Authentication failed.") from exc
    except (TimeoutError, OSError) as exc:
        raise SshActionError("SSH Timeout.") from exc
    except SshActionError:
        raise
    except Exception as exc:
        raise SshActionError(str(exc)) from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def validate_backup_content(content: str, backup_type: str) -> Tuple[bool, str]:
    text = (content or "").replace("\r", "").strip()
    low = text.lower()
    non_empty = [line.strip() for line in text.split("\n") if line.strip()]
    min_size = MIN_VALID_SIZE.get(backup_type, 50)
    if len(text.encode("utf-8", errors="ignore")) < min_size:
        return False, f"Backup output too small for {backup_type}."
    if low in {"building configuration...", "building configuration"}:
        return False, "Running-config capture stopped at Building configuration."
    if any(marker in low for marker in INVALID_CLI_MARKERS):
        return False, "CLI error marker found in backup output."
    if backup_type in {"running-config", "startup-config"}:
        if len(non_empty) < 10:
            return False, "Config output has too few lines."
        config_markers = ("version ", "hostname ", "interface ", "vlan ", "ip ", "line ", "snmp-server", "service timestamps")
        if not any(line.lower().startswith(config_markers) for line in non_empty[:120]):
            return False, "Cisco config markers not found."
    elif backup_type == "version":
        if not any(token in low for token in ("cisco ios", "ios xe", "nx-os", "cisco nexus", "system version", "software")):
            return False, "Cisco version markers not found."
    elif backup_type == "inventory":
        if not any(token in low for token in ("name:", "pid:", "descr:", "sn:")):
            return False, "Cisco inventory markers not found."
    return True, ""


def audit_existing_backup_index() -> Dict[str, int]:
    setup_storage()
    rows = _read_index()
    changed = 0
    invalid_success = 0
    for row in rows:
        if not row.get("success"):
            continue
        backup_type = row.get("backup_type") or ""
        content = read_backup_content(row)
        ok, reason = validate_backup_content(content, backup_type)
        if not ok:
            row["success"] = False
            row["error"] = f"Invalid legacy backup: {reason}"
            row["validation_status"] = "invalid"
            invalid_success += 1
            changed += 1
        else:
            row["validation_status"] = "valid"
            changed += 1
    if changed:
        _write_index(rows)
    return {"checked": len(rows), "changed": changed, "invalid_success": invalid_success}


def setup_storage() -> None:
    CISCO_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _safe_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
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
    if hasattr(value, "date"):
        dt = value
    else:
        dt = timezone.localtime()
    jy, jm, jd = _jalali_from_gregorian(dt.year, dt.month, dt.day)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def is_cisco_switch(switch: Switch) -> bool:
    parts = []
    for field in ("vendor", "device_family", "model", "name", "notes"):
        try:
            parts.append(str(getattr(switch, field, "") or ""))
        except Exception:
            pass
    text = " ".join(parts).lower()
    if "mikrotik" in text or "routeros" in text:
        return False
    return any(token in text for token in ("cisco", "catalyst", "nexus", "ios", "nx-os", "nxos", "3850", "2960", "3750", "9300", "9500"))


def cisco_switches():
    return [sw for sw in Switch.objects.filter(is_active=True).order_by("topology_position", "name") if is_cisco_switch(sw)]


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


def _append_metadata(row: Dict) -> Dict:
    items = [item for item in _read_index() if item.get("backup_id") != row.get("backup_id")]
    items.append(row)
    _write_index(items)
    return row


def _file_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8", errors="ignore")).hexdigest()


def _file_hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content or b"").hexdigest()


def _backup_id(switch: Switch, backup_type: str, created_at, content_hash: str) -> str:
    base = f"{switch.id}:{switch.name}:{backup_type}:{created_at.isoformat()}:{content_hash}"
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _filename(switch: Switch, backup_type: str, created_at) -> str:
    jdate = jalali_date_text(created_at)
    t = timezone.localtime(created_at).strftime("%H%M%S")
    ext = EXTENSIONS.get(backup_type, "txt")
    return f"{_safe_text(switch.name)}__{jdate}__{t}__{backup_type}.{ext}"


def command_for_type(backup_type: str) -> str:
    backup_type = str(backup_type or "").strip()
    if backup_type not in COMMANDS:
        raise ValueError("backup_type نامعتبر است.")
    return COMMANDS[backup_type]


def extract_command_output(raw_output: str, command: str) -> str:
    return _clean_cisco_output(raw_output or "", command or "")


def latest_previous_backup(switch_id: int, backup_type: str, before_backup_id: str = "") -> Optional[Dict]:
    rows = [
        row
        for row in _read_index()
        if int(row.get("device_id") or 0) == int(switch_id)
        and row.get("backup_type") == backup_type
        and bool(row.get("success", True))
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


def read_backup_content(row: Dict) -> str:
    raw_path = str(row.get("file_path") or "").strip()
    if not raw_path:
        return ""
    path = Path(raw_path)
    try:
        resolved = path.resolve()
        cisco_root = CISCO_DIR.resolve()
    except Exception:
        return ""
    if not path.exists():
        return ""
    if cisco_root not in resolved.parents and resolved != cisco_root:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def make_diff(previous: Optional[Dict], current_content: str) -> str:
    if not previous:
        return ""
    previous_content = read_backup_content(previous)
    if not previous_content:
        return ""
    return safe_diff(
        previous_content,
        current_content or "",
        previous_name=previous.get("filename", "previous"),
        current_name="current",
    )


def save_backup_record(
    *,
    switch: Switch,
    backup_type: str,
    content: str,
    command: str,
    created_by: str = "",
    source: str = "manual-ssh",
    success: bool = True,
    error: str = "",
) -> Dict:
    setup_storage()
    created_at = timezone.localtime()
    content = content or ""
    if success:
        ok, validation_error = validate_backup_content(content, backup_type)
        if not ok:
            raise SshActionError(validation_error)
    file_bytes = content.encode("utf-8", errors="ignore")
    content_hash = _file_hash_bytes(file_bytes)
    backup_id = _backup_id(switch, backup_type, created_at, content_hash)
    filename = _filename(switch, backup_type, created_at)
    device_dir = CISCO_DIR / _safe_text(switch.name)
    device_dir.mkdir(parents=True, exist_ok=True)
    file_path = device_dir / filename
    file_path.write_bytes(file_bytes)
    content_hash = _file_hash_bytes(file_path.read_bytes())
    previous = latest_previous_backup(switch.id, backup_type)
    diff_text = make_diff(previous, content)
    diff_path = ""
    if diff_text:
        diff_path_obj = device_dir / f"{filename}.diff.txt"
        diff_path_obj.write_text(diff_text, encoding="utf-8", errors="ignore")
        diff_path = str(diff_path_obj)
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
        "file_hash": content_hash,
        "hash_algorithm": "sha256-file-bytes",
        "size": file_path.stat().st_size,
        "success": bool(success),
        "error": error or "",
        "filename": filename,
        "file_path": str(file_path),
        "diff_path": diff_path,
        "previous_backup_id": previous.get("backup_id") if previous else "",
        "ui_preview": "masked",
        "download_scope": "admin-only",
        "sensitive_line_count": mask_sensitive_config(content)[1] if success else 0,
    }
    return _append_metadata(row)


def save_backup_failure(
    *,
    switch: Switch,
    backup_type: str,
    command: str,
    error: str,
    created_by: str = "",
    source: str = "manual-ssh",
) -> Dict:
    setup_storage()
    created_at = timezone.localtime()
    error = str(error or "Backup failed")
    content_hash = hashlib.sha256(f"{switch.id}:{backup_type}:{created_at.isoformat()}:{error}".encode("utf-8", errors="ignore")).hexdigest()
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
        "file_hash": "",
        "size": 0,
        "success": False,
        "error": error,
        "filename": "",
        "file_path": "",
        "diff_path": "",
        "previous_backup_id": "",
    }
    return _append_metadata(row)


def run_single_backup(
    *,
    switch: Switch,
    backup_type: str,
    username: str,
    password: str,
    enable_password: str = "",
    created_by: str = "",
    source: str = "manual-ssh",
) -> Dict:
    command = command_for_type(backup_type)
    content = run_cisco_show_command_direct(
        switch=switch,
        username=username,
        password=password,
        enable_password=enable_password,
        command=command,
        backup_type=backup_type,
    )
    ok, validation_error = validate_backup_content(content, backup_type)
    if not ok:
        raise SshActionError(validation_error)
    return save_backup_record(
        switch=switch,
        backup_type=backup_type,
        content=content,
        command=command,
        created_by=created_by,
        source=source,
    )


def validate_restore_candidate(content: str, backup_type: str = "running-config") -> Dict:
    lines = (content or "").replace("\r", "").split("\n")
    non_empty = [line for line in lines if line.strip()]
    warnings: List[str] = []
    blockers: List[str] = []
    if backup_type not in {"running-config", "startup-config"}:
        blockers.append("Restore فقط برای running-config یا startup-config قابل Prepare است.")
    if len(non_empty) < 5:
        blockers.append("فایل خیلی کوتاه است و Restore Candidate معتبر نیست.")
    if any("% invalid" in line.lower() for line in non_empty[:20]):
        blockers.append("خروجی شامل خطای CLI است.")
    if not any(line.strip().lower().startswith(("version", "hostname", "interface", "feature", "vlan", "ip ", "snmp-server")) for line in non_empty[:80]):
        warnings.append("نشانه‌های معمول Cisco config در ابتدای فایل کم است.")
    dangerous = []
    for line_no, line in enumerate(lines, 1):
        if any(pattern.search(line) for pattern in DANGEROUS_RESTORE_PATTERNS):
            masked_line, _ = mask_sensitive_config(line)
            dangerous.append(f"L{line_no}: {masked_line.strip()[:160]}")
    if dangerous:
        warnings.append("خطوط حساس برای Restore: " + " | ".join(dangerous[:20]))
    return {
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "line_count": len(lines),
        "non_empty_count": len(non_empty),
        "dangerous_count": len(dangerous),
        "dry_run_only": True,
        "message": "Restore واقعی در این فاز اجرا نمی‌شود؛ فقط Validate/Dry-run/Prepare انجام می‌شود.",
    }
