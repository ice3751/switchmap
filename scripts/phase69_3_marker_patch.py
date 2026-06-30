from __future__ import annotations

import datetime
import shutil
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "backups" / f"phase69_3_phase68_base_marker_compat_{STAMP}"
MARKER = "phase68-quick-search-port-labels"

TARGETS = [
    (ROOT / "inventory" / "templates" / "inventory" / "base.html", f"<!-- {MARKER} compatibility marker -->\n", "html"),
    (ROOT / "inventory" / "templates" / "inventory" / "switch_list.html", f"<!-- {MARKER} compatibility marker -->\n", "html"),
    (ROOT / "inventory" / "static" / "inventory" / "switchmap.js", f"\n/* {MARKER} compatibility marker */\n", "js"),
    (ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-dashboard-stable-main.css", f"\n/* {MARKER} compatibility marker */\n", "css"),
]


def insert_marker(path: Path, marker_text: str, kind: str) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))

    rel = path.relative_to(ROOT)
    backup_path = BACKUP / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)

    text = path.read_text(encoding="utf-8", errors="ignore")
    if MARKER in text:
        return "ALREADY_OK"

    if kind == "html" and "</body>" in text:
        text = text.replace("</body>", marker_text + "</body>", 1)
    else:
        text = text.rstrip() + marker_text

    path.write_text(text, encoding="utf-8")
    return "PATCHED"


def main() -> None:
    if not ROOT.exists():
        raise SystemExit("PHASE69_3_FAIL missing C:\\SwitchMap")
    BACKUP.mkdir(parents=True, exist_ok=True)
    print(f"PHASE69_3_BACKUP_PATH={BACKUP}")
    for path, marker_text, kind in TARGETS:
        status = insert_marker(path, marker_text, kind)
        print(f"PHASE69_3_{status}={path.relative_to(ROOT)}")
    print("PHASE69_3_COMPAT_OK")


if __name__ == "__main__":
    main()
