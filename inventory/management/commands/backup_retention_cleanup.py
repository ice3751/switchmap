from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.backup_schedule_policy import load_policy
from inventory.backup_storage_tools import BACKUP_ROOT, INDEXES, _is_inside  # type: ignore

PHASE89_RETENTION_MARKER = "PHASE89_BACKUP_RETENTION_CLEANUP"
CONFIRM_TEXT = "DELETE_OLD_BACKUPS"


def _read(path: Path) -> List[Dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(path: Path, rows: List[Dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _device_id(row: Dict) -> str:
    return str(row.get("device_id") or row.get("switch_id") or "")


def _backup_type(row: Dict) -> str:
    return str(row.get("backup_type") or row.get("type") or "")


def _file_candidates(row: Dict) -> List[Path]:
    values = []
    for key in ("file_path", "diff_file_path"):
        val = str(row.get(key) or "").strip()
        if val:
            values.append(Path(val))
    fp = str(row.get("file_path") or "").strip()
    if fp:
        values.append(Path(fp + ".diff.txt"))
    # de-duplicate preserving order
    out = []
    seen = set()
    for p in values:
        s = str(p)
        if s not in seen:
            out.append(p)
            seen.add(s)
    return out


def _plan_for_index(family: str, path: Path, keep: int) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    rows = _read(path)
    groups = defaultdict(list)
    for idx, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("success"):
            continue
        if row.get("keep") or row.get("manual_keep") or str(row.get("retention") or "").lower() == "keep":
            continue
        key = (family, _device_id(row), _backup_type(row))
        groups[key].append((idx, row))

    delete_indexes = set()
    candidates = []
    kept = []
    for key, items in groups.items():
        items.sort(key=lambda pair: str(pair[1].get("created_at") or ""), reverse=True)
        for pos, (idx, row) in enumerate(items):
            if pos < keep:
                kept.append(row)
                continue
            safe = True
            files = []
            for f in _file_candidates(row):
                if not _is_inside(f, BACKUP_ROOT):
                    safe = False
                files.append(str(f))
            candidate = {"family": family, "index": idx, "backup_id": row.get("backup_id"), "device_id": _device_id(row), "backup_type": _backup_type(row), "created_at": row.get("created_at"), "files": files, "safe": safe}
            candidates.append(candidate)
            if safe:
                delete_indexes.add(idx)
    new_rows = [row for idx, row in enumerate(rows) if idx not in delete_indexes]
    return rows, new_rows, candidates


class Command(BaseCommand):
    help = "Phase89: retention cleanup. Dry-run by default; apply requires --apply --confirm DELETE_OLD_BACKUPS."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=None, help="Keep latest N successful backups per device/type.")
        parser.add_argument("--apply", action="store_true", help="Actually delete safe old files and remove rows from index.")
        parser.add_argument("--confirm", default="", help="Required text for apply: DELETE_OLD_BACKUPS")
        parser.add_argument("--sample", type=int, default=25)

    def handle(self, *args, **options):
        policy = load_policy(create=True)
        keep = int(options.get("keep") or policy.get("retention_keep_latest_per_device_type") or 30)
        apply = bool(options.get("apply"))
        confirm = str(options.get("confirm") or "")
        sample = int(options.get("sample") or 25)
        self.stdout.write("PHASE89_BACKUP_RETENTION_CLEANUP_START")
        self.stdout.write("MODE=" + ("apply" if apply else "dry-run"))
        self.stdout.write("KEEP_LATEST_PER_DEVICE_TYPE=" + str(keep))
        if apply and confirm != CONFIRM_TEXT:
            raise SystemExit(f"CONFIRM_REQUIRED={CONFIRM_TEXT}")

        total_candidates = 0
        total_safe = 0
        total_deleted_files = 0
        total_removed_rows = 0
        reports = []
        for family, index_path in INDEXES.items():
            rows, new_rows, candidates = _plan_for_index(family, index_path, keep)
            safe_candidates = [c for c in candidates if c.get("safe")]
            total_candidates += len(candidates)
            total_safe += len(safe_candidates)
            self.stdout.write(f"INDEX family={family} rows={len(rows)} candidates={len(candidates)} safe={len(safe_candidates)} path={index_path}")
            for cand in candidates[:sample]:
                self.stdout.write(f"CANDIDATE family={family} device_id={cand.get('device_id')} type={cand.get('backup_type')} created_at={cand.get('created_at')} safe={cand.get('safe')}")
            if apply:
                delete_indexes = {int(c["index"]) for c in safe_candidates}
                for cand in safe_candidates:
                    for file_text in cand.get("files") or []:
                        p = Path(file_text)
                        if p.exists() and _is_inside(p, BACKUP_ROOT):
                            try:
                                p.unlink()
                                total_deleted_files += 1
                            except Exception as exc:
                                self.stdout.write(f"DELETE_FILE_FAIL path={p} error={exc}")
                _write(index_path, new_rows)
                total_removed_rows += len(delete_indexes)
            reports.append({"family": family, "index_path": str(index_path), "rows": len(rows), "candidates": candidates})

        report_path = Path(os.environ.get("SWITCHMAP_RETENTION_REPORT", r"C:\SwitchMap\logs\backup_retention_latest.json"))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"marker": PHASE89_RETENTION_MARKER, "generated_at": timezone.localtime().isoformat(), "mode": "apply" if apply else "dry-run", "keep": keep, "total_candidates": total_candidates, "total_safe": total_safe, "deleted_files": total_deleted_files, "removed_rows": total_removed_rows, "reports": reports}, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write("TOTAL_CANDIDATES=" + str(total_candidates))
        self.stdout.write("TOTAL_SAFE_CANDIDATES=" + str(total_safe))
        self.stdout.write("DELETED_FILES=" + str(total_deleted_files))
        self.stdout.write("REMOVED_INDEX_ROWS=" + str(total_removed_rows))
        self.stdout.write("REPORT=" + str(report_path))
        self.stdout.write("PHASE89_BACKUP_RETENTION_CLEANUP_DONE")
