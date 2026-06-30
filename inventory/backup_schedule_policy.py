from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from django.conf import settings
from django.db.models import Q

from inventory.models import Switch

try:
    from inventory.backup_storage_tools import BACKUP_ROOT, METADATA_DIR
except Exception:  # pragma: no cover
    BACKUP_ROOT = Path(os.environ.get("SWITCHMAP_BACKUP_ROOT", r"C:\SwitchMapData\backups"))
    METADATA_DIR = BACKUP_ROOT / "metadata"

POLICY_PATH = METADATA_DIR / "backup_schedule_policy.json"
PHASE89_POLICY_MARKER = "PHASE89_BACKUP_POLICY_AUTO_INCLUDE"

DEFAULT_POLICY: Dict[str, object] = {
    "marker": PHASE89_POLICY_MARKER,
    "version": "89.1",
    "auto_include_new_devices": True,
    "schedule_time": "23:30",
    "stale_hours": 36,
    "retention_keep_latest_per_device_type": 30,
    "cisco": {
        "enabled": True,
        "exclude_ids": [97],
        "backup_types": ["running-config", "startup-config"],
        "exclude_name_contains": ["PHASE", "BULK-TEST", "TEST-ONLY"],
    },
    "mikrotik": {
        "enabled": True,
        "exclude_ids": [20, 21, 22, 23, 25, 26, 27, 28, 106],
        "export_auto_include": True,
        "export_types": ["export"],
        "full_backup_ids": [18, 19],
        "full_backup_types": ["full-backup"],
        "exclude_name_contains": [],
    },
}


def _deep_merge(default: Dict, current: Dict) -> Dict:
    result = dict(default)
    for key, value in (current or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_policy(create: bool = True) -> Dict[str, object]:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    if POLICY_PATH.exists():
        try:
            current = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except Exception:
            current = {}
        policy = _deep_merge(DEFAULT_POLICY, current)
    else:
        policy = dict(DEFAULT_POLICY)
    if create:
        save_policy(policy)
    return policy


def save_policy(policy: Dict[str, object]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = POLICY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(POLICY_PATH)


def _text(sw: Switch) -> str:
    parts = []
    for field in ("vendor", "device_family", "model", "name", "notes"):
        try:
            parts.append(str(getattr(sw, field, "") or ""))
        except Exception:
            pass
    return " ".join(parts).lower()


def is_cisco(sw: Switch) -> bool:
    text = _text(sw)
    if any(token in text for token in ("mikrotik", "routeros", "routerboard")):
        return False
    return any(token in text for token in ("cisco", "catalyst", "nexus", "ios", "nx-os", "nxos", "3850", "2960", "3750", "9300", "9500"))


def is_mikrotik(sw: Switch) -> bool:
    text = _text(sw)
    if "cisco" in text:
        return False
    return any(token in text for token in ("mikrotik", "routeros", "routerboard", "rb5009", "rb2011", "crs", "hap", "hex", "cap-", "chr"))


def _excluded_by_name(sw: Switch, values: List[str]) -> bool:
    name = str(sw.name or "").lower()
    return any(str(v).lower() in name for v in (values or []))


def _candidate_switches() -> List[Switch]:
    return list(Switch.objects.filter(is_active=True, ssh_enabled=True).order_by("id"))


def schedule_candidates(policy: Dict[str, object] | None = None) -> Dict[str, object]:
    policy = policy or load_policy()
    cisco_policy = dict(policy.get("cisco") or {})
    mt_policy = dict(policy.get("mikrotik") or {})

    cisco_exclude = {int(x) for x in cisco_policy.get("exclude_ids") or []}
    mt_exclude = {int(x) for x in mt_policy.get("exclude_ids") or []}
    full_ids_config = {int(x) for x in mt_policy.get("full_backup_ids") or []}

    cisco = []
    mt_export = []
    mt_full = []
    skipped = []

    for sw in _candidate_switches():
        sid = int(sw.id)
        if is_cisco(sw):
            if sid in cisco_exclude or _excluded_by_name(sw, cisco_policy.get("exclude_name_contains") or []):
                skipped.append({"profile": "cisco", "id": sid, "name": sw.name, "reason": "policy excluded"})
                continue
            if cisco_policy.get("enabled", True):
                cisco.append(sw)
            continue
        if is_mikrotik(sw):
            if sid in mt_exclude or _excluded_by_name(sw, mt_policy.get("exclude_name_contains") or []):
                skipped.append({"profile": "mikrotik", "id": sid, "name": sw.name, "reason": "policy excluded"})
                continue
            if mt_policy.get("enabled", True) and mt_policy.get("export_auto_include", True):
                mt_export.append(sw)
            if sid in full_ids_config:
                mt_full.append(sw)
            continue
        skipped.append({"profile": "unknown", "id": sid, "name": sw.name, "reason": "vendor not matched"})

    return {
        "policy_path": str(POLICY_PATH),
        "cisco": cisco,
        "mikrotik_export": mt_export,
        "mikrotik_full": mt_full,
        "skipped": skipped,
        "cisco_types": list(cisco_policy.get("backup_types") or ["running-config", "startup-config"]),
        "mikrotik_export_types": list(mt_policy.get("export_types") or ["export"]),
        "mikrotik_full_types": list(mt_policy.get("full_backup_types") or ["full-backup"]),
    }


def ids(devices: List[Switch]) -> List[int]:
    return [int(sw.id) for sw in devices]
