import shutil
import sys
from pathlib import Path

FILES = [
    r"inventory\templates\inventory\base.html",
    r"inventory\templates\inventory\switch_list.html",
    r"inventory\static\inventory\css\switchmap-phase42.css",
    r"inventory\static\inventory\switchmap.js",
    r"inventory\views.py",
    r"smoke_tests\switchmap_66_5_dashboard_command_center_smoke_test.py",
    r"smoke_tests\manifest.json",
    r"docs\PHASE66_5_DASHBOARD_COMMAND_CENTER_LAYOUT.md",
]


def rel_parts(rel: str):
    return Path(*rel.split("\\"))


def main() -> int:
    if len(sys.argv) != 4:
        print("PHASE66_5_COPY_FAIL_USAGE")
        return 2
    root = Path(sys.argv[1])
    src_root = Path(sys.argv[2])
    backup_root = Path(sys.argv[3])
    if not root.exists():
        print(f"PHASE66_5_COPY_FAIL_ROOT_NOT_FOUND={root}")
        return 1
    if not src_root.exists():
        print(f"PHASE66_5_COPY_FAIL_SRC_NOT_FOUND={src_root}")
        return 1
    backup_root.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        rel_path = rel_parts(rel)
        src = src_root / rel_path
        dst = root / rel_path
        bak = backup_root / rel_path
        if not src.exists():
            print(f"PHASE66_5_COPY_FAIL_MISSING_SRC={src}")
            return 1
        if dst.exists():
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, bak)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"PHASE66_5_COPIED={rel}")
    print("PHASE66_5_COPY_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
