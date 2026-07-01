
# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
REPORT_DIR = ROOT / "reports"
TARGET_RELS = [
    "inventory/endpoint_display_policy.py",
    "inventory/views.py",
    "inventory/urls.py",
]

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")

def latest_backup() -> Path | None:
    items = [p for p in (ROOT / "backups").glob("phase114r2_apply_*") if p.is_dir()]
    if not items:
        return None
    return sorted(items, key=lambda p: p.stat().st_mtime, reverse=True)[0]

def main() -> int:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    b = latest_backup()
    result = {"phase": "PHASE114R2_ROLLBACK", "backup": str(b) if b else None, "restored": [], "errors": []}
    if not b:
        result["errors"].append("BACKUP_NOT_FOUND")
    else:
        for rel in TARGET_RELS:
            src = b / rel
            dst = ROOT / rel
            missing = b / (rel + ".missing")
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                result["restored"].append(rel)
            elif missing.exists() and dst.exists():
                dst.unlink()
                result["restored"].append(rel + ":removed")
            else:
                result["errors"].append(f"MISSING_BACKUP:{rel}")

    report = REPORT_DIR / f"phase114r2_rollback_{ts}.json"
    write_text(report, json.dumps(result, ensure_ascii=False, indent=2))
    print(f"REPORT={report}")
    print(f"ERRORS={len(result['errors'])}")
    return 1 if result["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
