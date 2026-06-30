from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path.cwd()
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = BASE / "backups" / f"phase86_2_backup_hash_repair_{STAMP}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json_list(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_json_list(path: Path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def is_inside(child: Path, parent: Path) -> bool:
    try:
        c = child.resolve()
        p = parent.resolve()
        return c == p or p in c.parents
    except Exception:
        return False


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print("PHASE86_2_BACKUP_HASH_REPAIR_START")
    print("BACKUP_DIR=", BACKUP_DIR)

    import django
    django.setup()

    from inventory.backup_storage_tools import BACKUP_ROOT, INDEXES, verify_secure_backup_storage

    print("STORAGE_ROOT=", BACKUP_ROOT)
    total = changed = skipped_failed = missing = outside = 0
    for family, index_path in INDEXES.items():
        index_path = Path(index_path)
        if not index_path.exists():
            print("INDEX_MISSING=", family, index_path)
            continue
        target = BACKUP_DIR / index_path.name
        shutil.copy2(index_path, target)
        rows = read_json_list(index_path)
        for row in rows:
            if not isinstance(row, dict):
                continue
            total += 1
            if not row.get("success"):
                skipped_failed += 1
                continue
            path_text = str(row.get("file_path") or "").strip()
            if not path_text:
                missing += 1
                continue
            file_path = Path(path_text)
            if not is_inside(file_path, BACKUP_ROOT):
                outside += 1
                continue
            if not file_path.exists():
                missing += 1
                continue
            actual_hash = sha256_file(file_path)
            old_hash = str(row.get("file_hash") or "").strip().lower()
            actual_size = file_path.stat().st_size
            if old_hash != actual_hash or int(row.get("size") or 0) != actual_size or row.get("hash_algorithm") != "sha256-file-bytes":
                if old_hash and old_hash != actual_hash and not row.get("legacy_file_hash"):
                    row["legacy_file_hash"] = old_hash
                row["file_hash"] = actual_hash
                row["hash_algorithm"] = "sha256-file-bytes"
                row["size"] = actual_size
                row["hash_repaired_at"] = datetime.now().isoformat()
                changed += 1
        write_json_list(index_path, rows)
        print("INDEX_REPAIRED=", family, "ROWS=", len(rows))

    report = verify_secure_backup_storage()
    stats = report.get("stats", {})
    print("TOTAL_ROWS_SEEN=", total)
    print("HASH_ROWS_REPAIRED=", changed)
    print("SKIPPED_FAILED_ROWS=", skipped_failed)
    print("MISSING_OR_NO_PATH=", missing)
    print("OUTSIDE_ROOT=", outside)
    print("VERIFY_OK=", report.get("ok"))
    print("VERIFY_HASH_MISMATCH=", stats.get("hash_mismatch"))
    print("VERIFY_MISSING_FILES=", stats.get("missing_files"))
    print("VERIFY_FAILURE_ISSUES=", stats.get("failure_issues"))
    if not report.get("ok"):
        print("PHASE86_2_BACKUP_HASH_REPAIR_VERIFY_FAILED")
        raise SystemExit(2)
    print("PHASE86_2_BACKUP_HASH_REPAIR_OK")


if __name__ == "__main__":
    main()
