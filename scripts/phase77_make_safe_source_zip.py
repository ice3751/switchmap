from __future__ import annotations

import argparse
import fnmatch
import json
import tempfile
import time
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist"

# Phase95 safety guard: deny sensitive/runtime/generated/archive roots by default.
DENY_DIR_NAMES = {
    ".git",
    "venv",
    "env",
    ".venv",
    "__pycache__",
    "backups",
    "logs",
    "reports",
    "deploy",
    "staticfiles",
    "media",
    "secrets",
    "restore_candidates",
    "project_snapshots",
    "_phase91_backup",
    "_phase91_quarantine",
    ".pytest_cache",
    "dist",
    "patches",
}

DENY_PREFIX_DIRS = (
    "payload_phase",
)

DENY_FILE_NAMES = {
    "db.sqlite3",
    "switchmap.env",
    ".env",
    "switchmap.log",
}

DENY_PATTERNS = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.sqlite3",
    "*.sqlite",
    "*.db",
    "*.cdb",
    "*.log",
    "*.bak",
    "*.bak*",
    "*.tmp",
    "*.zip",
    "*.rar",
    "*.7z",
    "*.dpapi",
    "*.key",
    "*.pem",
    "*.crt",
    "*.pfx",
    "*.p12",
    "*secret*",
    "*credential*",
    "*password*",
]

ALLOW_EXTENSIONS = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".json",
    ".txt",
    ".md",
    ".cmd",
    ".bat",
    ".csv",
    ".yml",
    ".yaml",
}


def rel_text(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def denied(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    parts = rel.parts
    lower_parts = [p.lower() for p in parts]
    if any(part in DENY_DIR_NAMES for part in lower_parts):
        return True
    if any(part.startswith(prefix) for part in lower_parts for prefix in DENY_PREFIX_DIRS):
        return True
    name = path.name.lower()
    if name in {x.lower() for x in DENY_FILE_NAMES}:
        return True
    if any(fnmatch.fnmatch(name, pattern.lower()) for pattern in DENY_PATTERNS):
        return True
    return False


def source_file_allowed(path: Path) -> bool:
    if not path.is_file():
        return False
    if denied(path):
        return False
    if path.suffix.lower() not in ALLOW_EXTENSIONS:
        return False
    return True


def scan() -> dict:
    included = []
    skipped = 0
    violations = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir():
            continue
        if source_file_allowed(path):
            rel = rel_text(path)
            included.append(rel)
            if denied(path):
                violations.append(rel)
        else:
            skipped += 1
    return {
        "root": str(ROOT),
        "included_count": len(included),
        "skipped_count": skipped,
        "violations": violations,
        "sample": included[:20],
    }


def build_zip() -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"SwitchMap_SAFE_SOURCE_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    scan_result = scan()
    if scan_result["violations"]:
        raise SystemExit("SAFE_SOURCE_ZIP_REFUSED sensitive_path_violation")
    with tempfile.NamedTemporaryFile(prefix="switchmap_safe_source_", suffix=".zip", delete=False, dir=str(OUT_DIR)) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with ZipFile(tmp_path, "w", ZIP_DEFLATED) as zf:
            for path in sorted(ROOT.rglob("*")):
                if source_file_allowed(path):
                    arcname = Path("SwitchMap") / path.relative_to(ROOT)
                    zf.write(path, arcname)
        tmp_path.replace(out)
    finally:
        if tmp_path.exists() and tmp_path != out:
            tmp_path.unlink(missing_ok=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a safe SwitchMap source ZIP without sensitive/runtime artifacts.")
    parser.add_argument("--check-only", action="store_true", help="Scan only; do not create a ZIP file.")
    parser.add_argument("--json", dest="json_path", default="", help="Optional JSON report path for check-only output.")
    args = parser.parse_args()
    result = scan()
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["violations"]:
        print("SAFE_SOURCE_SCAN_FAIL")
        print("VIOLATIONS=" + ",".join(result["violations"]))
        return 2
    if args.check_only:
        print("SAFE_SOURCE_SCAN_OK=True")
        print(f"SAFE_SOURCE_INCLUDED={result['included_count']}")
        print(f"SAFE_SOURCE_SKIPPED={result['skipped_count']}")
        return 0
    out = build_zip()
    print(f"PHASE77_SAFE_SOURCE_ZIP={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
