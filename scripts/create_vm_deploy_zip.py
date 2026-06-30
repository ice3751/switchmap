import os
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "deploy"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT = OUTPUT_DIR / f"SwitchMap_VM_DEPLOY_{STAMP}.zip"

EXCLUDED_DIRS = {
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "staticfiles",
    "logs",
    "deploy",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
}
EXCLUDED_FILES = {
    "switchmap.env",
}

# Keep db.sqlite3 because this is the real SQLite data for the first VM move.
# Exclude old backups to avoid a very large and confusing deployment package.
EXCLUDED_TOP_LEVEL_DIRS = {"backups"}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = set(rel.parts)
    if rel.parts and rel.parts[0] in EXCLUDED_TOP_LEVEL_DIRS:
        return True
    if parts & EXCLUDED_DIRS:
        return True
    if path.name in EXCLUDED_FILES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if path.name.startswith("SwitchMap_VM_DEPLOY_") and path.suffix.lower() == ".zip":
        return True
    return False

with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in ROOT.rglob("*"):
        if path.is_dir() or should_skip(path):
            continue
        arcname = Path("SwitchMap") / path.relative_to(ROOT)
        zf.write(path, arcname.as_posix())

print(f"DEPLOY_ZIP_OK {OUTPUT}")
