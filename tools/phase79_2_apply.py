from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
BACKUP_DIR = ROOT / "backups" / f"phase79_2_port_last_connected_ui_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

FILES = [
    "inventory/views.py",
    "inventory/templates/inventory/base.html",
    "inventory/templates/inventory/switch_list.html",
    "inventory/templates/inventory/switch_detail.html",
    "inventory/static/inventory/switchmap.js",
    "inventory/static/inventory/css/switchmap-phase79.css",
]


def copy_file(rel: str) -> None:
    src = PAYLOAD / rel
    dst = ROOT / rel
    if not src.exists():
        raise SystemExit(f"PHASE79_2_FAIL missing payload: {rel}")
    if dst.exists():
        backup = BACKUP_DIR / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        copy_file(rel)
    manifest = BACKUP_DIR / "changed_files.txt"
    manifest.write_text("\n".join(FILES) + "\n", encoding="utf-8")
    print(f"PHASE79_2_PATCH_OK backup_dir={BACKUP_DIR}")


if __name__ == "__main__":
    main()
