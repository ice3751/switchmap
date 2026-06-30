from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import platform
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.utils import timezone


class SecureCredentialError(Exception):
    pass


BACKUP_ROOT = Path(os.environ.get("SWITCHMAP_BACKUP_ROOT", r"C:\SwitchMapData\backups"))
DEFAULT_CREDENTIAL_DIR = BACKUP_ROOT / "metadata" / "credentials"
CREDENTIAL_DIR = Path(os.environ.get("SWITCHMAP_CREDENTIAL_DIR", str(DEFAULT_CREDENTIAL_DIR)))
LEGACY_CREDENTIAL_DIR = Path(settings.BASE_DIR) / "secrets"
CREDENTIAL_PROFILES = {
    "cisco": "ssh-monitor-cisco-credential.dpapi",
    "mikrotik": "ssh-monitor-mikrotik-credential.dpapi",
}
LEGACY_CREDENTIAL_FILE = LEGACY_CREDENTIAL_DIR / "ssh-monitor-credential.dpapi"
CREDENTIAL_FILE = CREDENTIAL_DIR / CREDENTIAL_PROFILES["cisco"]
PURPOSE_PREFIX = "SwitchMap SSH Monitor Credential v3"
LEGACY_PURPOSE_PREFIX = "SwitchMap SSH Monitor Credential v2"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def normalize_profile(profile: str = "cisco") -> str:
    profile = str(profile or "cisco").strip().lower()
    if profile not in CREDENTIAL_PROFILES:
        raise SecureCredentialError(f"Credential profile نامعتبر است: {profile}")
    return profile


def credential_file(profile: str = "cisco") -> Path:
    return CREDENTIAL_DIR / CREDENTIAL_PROFILES[normalize_profile(profile)]


def legacy_credential_file(profile: str = "cisco") -> Path:
    return LEGACY_CREDENTIAL_DIR / CREDENTIAL_PROFILES[normalize_profile(profile)]


def _purpose(profile: str = "cisco") -> str:
    return f"{PURPOSE_PREFIX}::{normalize_profile(profile)}"


def _ensure_windows() -> None:
    if platform.system().lower() != "windows":
        raise SecureCredentialError("DPAPI فقط روی Windows قابل استفاده است.")


def _make_blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _protect(data: bytes, profile: str = "cisco") -> bytes:
    _ensure_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob, in_buffer = _make_blob(data)
    out_blob = DATA_BLOB()
    description = ctypes.create_unicode_buffer(_purpose(profile))

    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecureCredentialError("CryptProtectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
        _ = in_buffer


def _unprotect(data: bytes) -> bytes:
    _ensure_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob, in_buffer = _make_blob(data)
    out_blob = DATA_BLOB()
    description = ctypes.c_wchar_p()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecureCredentialError("CryptUnprotectData failed. Credential باید با همان Windows User و همان Task User باز شود.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
        _ = in_buffer


def _candidate_files(profile: str = "cisco", include_legacy: bool = True) -> list[Path]:
    profile = normalize_profile(profile)
    candidates = [credential_file(profile)]
    if include_legacy:
        candidates.append(legacy_credential_file(profile))
        if profile == "cisco":
            candidates.append(LEGACY_CREDENTIAL_FILE)
    unique: list[Path] = []
    seen = set()
    for item in candidates:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def credential_exists(profile: str = "cisco", include_legacy: bool = True) -> bool:
    return any(path.exists() for path in _candidate_files(profile, include_legacy=include_legacy))


def credential_status(profile: str = "cisco") -> dict:
    profile = normalize_profile(profile)
    selected = None
    for path in _candidate_files(profile, include_legacy=True):
        if path.exists():
            selected = path
            break
    location = "missing"
    if selected:
        if str(selected).lower().startswith(str(CREDENTIAL_DIR).lower()):
            location = "secure-storage"
        elif str(selected).lower().startswith(str(LEGACY_CREDENTIAL_DIR).lower()):
            location = "legacy-project-secrets"
        else:
            location = "legacy"
    return {
        "profile": profile,
        "exists": bool(selected),
        "file": str(selected or credential_file(profile)),
        "legacy": bool(selected and selected != credential_file(profile)),
        "location": location,
        "credential_dir": str(CREDENTIAL_DIR),
        "recommended_file": str(credential_file(profile)),
        "windows_user": os.environ.get("USERNAME", ""),
        "computer": os.environ.get("COMPUTERNAME", ""),
    }


def save_ssh_monitor_credentials(username: str, password: str, enable_password: str = "", profile: str = "cisco") -> Path:
    profile = normalize_profile(profile)
    username = str(username or "").strip()
    password = str(password or "")
    enable_password = str(enable_password or "")
    if not username:
        raise SecureCredentialError("Username خالی است.")
    if not password:
        raise SecureCredentialError("Password خالی است.")

    payload = {
        "type": "switchmap_ssh_monitor_credential",
        "version": 3,
        "profile": profile,
        "scope": "windows_current_user_dpapi",
        "storage": "outside_project",
        "username": username,
        "password": password,
        "enable_password": enable_password,
        "created_at": timezone.now().isoformat(),
        "windows_user": os.environ.get("USERNAME", ""),
        "computer": os.environ.get("COMPUTERNAME", ""),
    }
    encrypted = _protect(json.dumps(payload, ensure_ascii=False).encode("utf-8"), profile=profile)
    CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    path = credential_file(profile)
    path.write_text(base64.b64encode(encrypted).decode("ascii"), encoding="ascii")
    return path


def load_ssh_monitor_credentials(profile: str = "cisco") -> dict:
    profile = normalize_profile(profile)
    selected = None
    for path in _candidate_files(profile, include_legacy=True):
        if path.exists():
            selected = path
            break
    if selected is None:
        raise SecureCredentialError(f"Credential file not found: {credential_file(profile)}")

    try:
        encrypted = base64.b64decode(selected.read_text(encoding="ascii").strip())
        payload = json.loads(_unprotect(encrypted).decode("utf-8"))
    except SecureCredentialError:
        raise
    except Exception as exc:
        raise SecureCredentialError(str(exc)) from exc

    if payload.get("type") != "switchmap_ssh_monitor_credential":
        raise SecureCredentialError("Credential type نامعتبر است.")
    if not payload.get("username") or not payload.get("password"):
        raise SecureCredentialError("Credential ناقص است.")
    payload.setdefault("profile", profile)
    payload.setdefault("version", 2)
    payload.setdefault("scope", "windows_current_user_dpapi")
    payload["credential_file"] = str(selected)
    payload["credential_is_legacy"] = bool(selected != credential_file(profile))
    payload["credential_location"] = credential_status(profile).get("location")
    return payload


def delete_ssh_monitor_credentials(profile: str = "cisco", include_legacy: bool = True) -> bool:
    removed = False
    for path in _candidate_files(profile, include_legacy=include_legacy):
        if path.exists():
            path.unlink()
            removed = True
    return removed


def migrate_legacy_credential(profile: str = "cisco") -> dict:
    """Re-save an existing decryptable legacy credential into secure storage outside project."""
    profile = normalize_profile(profile)
    current = credential_status(profile)
    if not current.get("exists"):
        return {"profile": profile, "migrated": False, "reason": "missing"}
    if current.get("location") == "secure-storage":
        return {"profile": profile, "migrated": False, "reason": "already-secure", "file": current.get("file")}
    payload = load_ssh_monitor_credentials(profile=profile)
    path = save_ssh_monitor_credentials(
        username=payload.get("username", ""),
        password=payload.get("password", ""),
        enable_password=payload.get("enable_password", ""),
        profile=profile,
    )
    return {"profile": profile, "migrated": True, "file": str(path), "old_file": current.get("file")}
