from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PHASE = "phase66_11_dashboard_final_main"
FILES = [
    "inventory/templates/inventory/switch_list.html",
    "inventory/static/inventory/css/switchmap-dashboard-command-final.css",
    "smoke_tests/switchmap_66_11_dashboard_final_main_smoke_test.py",
    "docs/PHASE66_11_DASHBOARD_FINAL_MAIN.md",
]
SMOKE_REL = "smoke_tests/switchmap_66_11_dashboard_final_main_smoke_test.py"


def fail(message: str) -> None:
    print("PHASE66_11_COPY_FAIL=" + message)
    raise SystemExit(1)


def backup_file(root: Path, backup: Path, rel: str) -> None:
    dst = root / rel
    if dst.exists():
        b = backup / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, b)


def copy_files(root: Path, src: Path, backup: Path) -> None:
    for rel in FILES:
        s = src / rel
        d = root / rel
        if not s.exists():
            fail(f"source missing: {rel}")
        backup_file(root, backup, rel)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        print(f"PHASE66_11_COPIED={rel}")


def patch_manifest(root: Path, backup: Path) -> None:
    rel = "smoke_tests/manifest.json"
    p = root / rel
    if not p.exists():
        print("PHASE66_11_MANIFEST_SKIPPED_MISSING")
        return
    backup_file(root, backup, rel)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"manifest parse failed: {exc}")
    current = data.setdefault("current", [])
    if SMOKE_REL not in current:
        current.append(SMOKE_REL)
    data["phase66_11"] = [SMOKE_REL]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PHASE66_11_MANIFEST_PATCHED")


def main() -> int:
    if len(sys.argv) != 4:
        fail("bad args")
    root = Path(sys.argv[1])
    src = Path(sys.argv[2])
    backup = Path(sys.argv[3])
    backup.mkdir(parents=True, exist_ok=True)
    copy_files(root, src, backup)
    patch_manifest(root, backup)
    print("PHASE66_11_COPY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
