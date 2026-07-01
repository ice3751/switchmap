from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from django.conf import settings
from django.utils import timezone

PHASE86_MARKER = "PHASE86_SECURE_BACKUP_STORAGE"

BACKUP_ROOT = Path(os.environ.get("SWITCHMAP_BACKUP_ROOT", r"C:\SwitchMapData\backups"))
CISCO_DIR = BACKUP_ROOT / "cisco"
MIKROTIK_DIR = BACKUP_ROOT / "mikrotik"
METADATA_DIR = BACKUP_ROOT / "metadata"
LOG_DIR = BACKUP_ROOT / "logs"
CISCO_INDEX = METADATA_DIR / "cisco_backup_index.json"
MIKROTIK_INDEX = METADATA_DIR / "mikrotik_backup_index.json"

REQUIRED_DIRS = {
    "root": BACKUP_ROOT,
    "cisco": CISCO_DIR,
    "mikrotik": MIKROTIK_DIR,
    "metadata": METADATA_DIR,
    "logs": LOG_DIR,
}

INDEXES = {
    "cisco": CISCO_INDEX,
    "mikrotik": MIKROTIK_INDEX,
}


def setup_secure_backup_storage() -> Dict[str, object]:
    created = []
    for name, path in REQUIRED_DIRS.items():
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))
    for name, path in INDEXES.items():
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
            created.append(str(path))
    return {"root": str(BACKUP_ROOT), "created": created, "required_dirs": {k: str(v) for k, v in REQUIRED_DIRS.items()}}


def _read_json_list(path: Path) -> List[Dict]:
    try:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
        return child_resolved == parent_resolved or parent_resolved in child_resolved.parents
    except Exception:
        return False


def _project_root() -> Path:
    try:
        return Path(settings.BASE_DIR).resolve()
    except Exception:
        return Path.cwd().resolve()


def _row_time(row: Dict):
    raw = str(row.get("created_at") or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def load_all_backup_rows() -> List[Dict]:
    rows: List[Dict] = []
    for family, index_path in INDEXES.items():
        for row in _read_json_list(index_path):
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["family"] = family
            item["index_path"] = str(index_path)
            rows.append(item)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def retention_plan(rows: Iterable[Dict]) -> Dict[str, object]:
    """Dry-run retention classification. No files are deleted here."""
    groups: Dict[Tuple[str, str, str], List[Dict]] = defaultdict(list)
    for row in rows:
        if not row.get("success"):
            continue
        key = (str(row.get("family") or ""), str(row.get("device_id") or ""), str(row.get("backup_type") or ""))
        groups[key].append(row)

    keep_ids = set()
    classes = defaultdict(int)
    candidates = []
    for key, items in groups.items():
        items.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        daily = set()
        weekly = set()
        monthly = set()
        manual_keep = set()
        for row in items:
            created = _row_time(row)
            if row.get("keep") or row.get("manual_keep") or str(row.get("retention") or "").lower() == "keep":
                manual_keep.add(row.get("backup_id"))
            if created:
                daily.add((created.year, created.month, created.day))
                weekly.add((created.isocalendar().year, created.isocalendar().week))
                monthly.add((created.year, created.month))
        seen_daily = set()
        seen_weekly = set()
        seen_monthly = set()
        for idx, row in enumerate(items):
            created = _row_time(row)
            bid = row.get("backup_id")
            reasons = []
            if idx == 0:
                reasons.append("latest")
            if bid in manual_keep:
                reasons.append("manual_keep")
            if created:
                dkey = (created.year, created.month, created.day)
                wkey = (created.isocalendar().year, created.isocalendar().week)
                mkey = (created.year, created.month)
                if dkey not in seen_daily:
                    reasons.append("daily")
                    seen_daily.add(dkey)
                if wkey not in seen_weekly:
                    reasons.append("weekly")
                    seen_weekly.add(wkey)
                if mkey not in seen_monthly:
                    reasons.append("monthly")
                    seen_monthly.add(mkey)
            if reasons:
                keep_ids.add(bid)
                for reason in reasons:
                    classes[reason] += 1
            else:
                candidates.append(row)
    return {"keep_count": len(keep_ids), "delete_candidates": len(candidates), "classes": dict(classes), "candidate_sample": candidates[:20]}


def verify_secure_backup_storage() -> Dict[str, object]:
    setup = setup_secure_backup_storage()
    rows = load_all_backup_rows()
    project = _project_root()
    root_under_project = _is_inside(BACKUP_ROOT, project)
    required = []
    for name, path in REQUIRED_DIRS.items():
        required.append({"name": name, "path": str(path), "exists": path.exists(), "is_dir": path.is_dir()})
    index_status = []
    for name, path in INDEXES.items():
        index_status.append({"name": name, "path": str(path), "exists": path.exists(), "rows": len(_read_json_list(path))})

    stats = {
        "total_rows": len(rows),
        "success_rows": 0,
        "failed_rows": 0,
        "missing_files": 0,
        "hash_mismatch": 0,
        "outside_root": 0,
        "inside_project": 0,
        "zero_size_success": 0,
        "download_scope_warnings": 0,
        "warning_issues": 0,
        "failure_issues": 0,
        "verified_files": 0,
        "total_bytes": 0,
    }
    issues = []
    samples = []
    for row in rows:
        success = bool(row.get("success"))
        if success:
            stats["success_rows"] += 1
        else:
            stats["failed_rows"] += 1
        path_text = str(row.get("file_path") or "").strip()
        if not path_text:
            if success:
                stats["missing_files"] += 1
                issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "successful row has no file_path"})
            continue
        path = Path(path_text)
        if not _is_inside(path, BACKUP_ROOT):
            if success:
                stats["outside_root"] += 1
                issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "file_path outside backup root", "path": path_text})
            else:
                issues.append({"severity": "warn", "backup_id": row.get("backup_id"), "issue": "failed row path outside backup root", "path": path_text})
            continue
        if _is_inside(path, project):
            if success:
                stats["inside_project"] += 1
                issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "backup file is inside project directory", "path": path_text})
            else:
                issues.append({"severity": "warn", "backup_id": row.get("backup_id"), "issue": "failed row path inside project directory", "path": path_text})
        if not path.exists():
            if success:
                stats["missing_files"] += 1
                issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "file missing", "path": path_text})
            continue
        size = path.stat().st_size
        stats["total_bytes"] += size
        if success and size <= 0:
            stats["zero_size_success"] += 1
            issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "successful backup has zero-size file", "path": path_text})
        expected_hash = str(row.get("file_hash") or "").strip().lower()
        if success and expected_hash:
            actual_hash = _sha256(path)
            stats["verified_files"] += 1
            if actual_hash != expected_hash:
                stats["hash_mismatch"] += 1
                issues.append({"severity": "fail", "backup_id": row.get("backup_id"), "issue": "sha256 mismatch", "path": path_text})
        scope = str(row.get("download_scope") or "").lower()
        if success and row.get("family") in {"cisco", "mikrotik"} and scope and scope != "admin-only":
            stats["download_scope_warnings"] += 1
            issues.append({"severity": "warn", "backup_id": row.get("backup_id"), "issue": "download_scope is not admin-only"})
        if len(samples) < 12:
            samples.append({
                "family": row.get("family"),
                "device": row.get("device"),
                "type": row.get("backup_type_label") or row.get("backup_type"),
                "created_at": row.get("created_at"),
                "success": success,
                "size": size if path.exists() else row.get("size"),
            })
    ret = retention_plan(rows)
    ok = (
        not root_under_project
        and all(item["exists"] and item["is_dir"] for item in required)
        and stats["outside_root"] == 0
        and stats["inside_project"] == 0
        and stats["missing_files"] == 0
        and stats["hash_mismatch"] == 0
        and stats["zero_size_success"] == 0
    )
    stats["failure_issues"] = sum(1 for item in issues if item.get("severity") == "fail")
    stats["warning_issues"] = sum(1 for item in issues if item.get("severity") == "warn")
    return {
        "marker": PHASE86_MARKER,
        "ok": ok,
        "root": str(BACKUP_ROOT),
        "root_under_project": root_under_project,
        "project_root": str(project),
        "setup": setup,
        "required_dirs": required,
        "indexes": index_status,
        "stats": stats,
        "issues": issues[:200],
        "samples": samples,
        "retention": ret,
        "checked_at": timezone.localtime().isoformat(),
    }
