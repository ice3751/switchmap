from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "project_snapshots"

DENY_DIR_NAMES = {
    ".git",
    "venv",
    "env",
    ".venv",
    "__pycache__",
    "project_snapshots",
    "media",
    "backups",
    "restore_candidates",
    "logs",
    "reports",
    "staticfiles",
    "secrets",
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

DENY_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".sqlite3",
    ".sqlite",
    ".db",
    ".cdb",
    ".log",
    ".bak",
    ".tmp",
    ".zip",
    ".rar",
    ".7z",
    ".dpapi",
    ".key",
    ".pem",
    ".crt",
    ".pfx",
    ".p12",
}

INCLUDE_EXT = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".json",
    ".txt",
    ".md",
    ".bat",
    ".cmd",
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
    parts = [p.lower() for p in rel.parts]
    if any(part in DENY_DIR_NAMES for part in parts):
        return True
    if any(part.startswith(prefix) for part in parts for prefix in DENY_PREFIX_DIRS):
        return True
    name = path.name.lower()
    if name in {x.lower() for x in DENY_FILE_NAMES}:
        return True
    if path.suffix.lower() in DENY_SUFFIXES:
        return True
    if "secret" in name or "credential" in name or "password" in name:
        return True
    return False


def is_allowed(path: Path) -> bool:
    return path.is_file() and not denied(path) and path.suffix.lower() in INCLUDE_EXT


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"READ ERROR: {exc}"


def run_cmd(args: list[str]) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        return (result.stdout or "") + (result.stderr or "")
    except Exception as exc:
        return f"ERROR: {exc}"


def scan() -> dict:
    included = []
    skipped = 0
    violations = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir():
            continue
        if is_allowed(path):
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


def write_snapshot() -> Path:
    result = scan()
    if result["violations"]:
        raise SystemExit("PROJECT_SOURCE_SNAPSHOT_REFUSED sensitive_path_violation")
    OUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"switchmap_project_source_{timestamp}.txt"
    with out_file.open("w", encoding="utf-8") as f:
        f.write("SwitchMap Project Source Snapshot\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"Root: {ROOT}\n")
        f.write("Sensitive files are excluded by Phase95 guard rules.\n\n")

        f.write("===== GIT STATUS =====\n")
        f.write(run_cmd(["git", "status", "--short"]))
        f.write("\n\n")

        f.write("===== DJANGO CHECK =====\n")
        f.write(run_cmd([sys.executable, "manage.py", "check"]))
        f.write("\n\n")

        f.write("===== INSTALLED PACKAGES =====\n")
        f.write(run_cmd([sys.executable, "-m", "pip", "freeze"]))
        f.write("\n\n")

        f.write("===== URL ROUTES =====\n")
        route_code = "from django.urls import get_resolver; [print(getattr(x,'name',None), x.pattern) for x in get_resolver().url_patterns]"
        f.write(run_cmd([sys.executable, "manage.py", "shell", "-c", route_code]))
        f.write("\n\n")

        f.write("===== APP FILE TREE =====\n")
        for path in sorted(ROOT.rglob("*")):
            if is_allowed(path):
                f.write(rel_text(path) + "\n")
        f.write("\n\n")

        f.write("===== FILE CONTENTS =====\n")
        for path in sorted(ROOT.rglob("*")):
            if is_allowed(path):
                rel = rel_text(path)
                f.write(f"\n\n----- FILE: {rel} -----\n")
                f.write(safe_read(path))
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a redacted SwitchMap project source snapshot.")
    parser.add_argument("--check-only", action="store_true", help="Scan only; do not write a snapshot.")
    parser.add_argument("--json", dest="json_path", default="", help="Optional JSON report path.")
    args = parser.parse_args()
    result = scan()
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["violations"]:
        print("PROJECT_SOURCE_SNAPSHOT_SCAN_FAIL")
        print("VIOLATIONS=" + ",".join(result["violations"]))
        return 2
    if args.check_only:
        print("PROJECT_SOURCE_SNAPSHOT_SCAN_OK=True")
        print(f"PROJECT_SOURCE_SNAPSHOT_INCLUDED={result['included_count']}")
        print(f"PROJECT_SOURCE_SNAPSHOT_SKIPPED={result['skipped_count']}")
        return 0
    out_file = write_snapshot()
    print(f"PROJECT_SOURCE_SNAPSHOT={out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
