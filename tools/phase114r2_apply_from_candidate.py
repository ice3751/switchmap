
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import datetime as dt
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
PHASE = "PHASE114R2_APPLY_FROM_CANDIDATE"
TS = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_DIR = ROOT / "reports"
BACKUP_DIR = ROOT / "backups" / f"phase114r2_apply_{TS}"
TARGET_RELS = [
    "inventory/endpoint_display_policy.py",
    "inventory/views.py",
    "inventory/urls.py",
]
CANDIDATE_GLOB = "SwitchMap_Phase114R2_Neighbor_Endpoint_UI_Guard_CANDIDATE_*"

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")

def run_cmd(args, timeout=90):
    try:
        p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"cmd": args, "rc": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}
    except Exception as e:
        return {"cmd": args, "rc": "ERR", "error": repr(e)}

def latest_candidate() -> Path | None:
    items = [p for p in ROOT.glob(CANDIDATE_GLOB) if p.is_dir() and (p / "files").exists()]
    if not items:
        return None
    return sorted(items, key=lambda p: p.stat().st_mtime, reverse=True)[0]

def py_syntax(path: Path):
    try:
        ast.parse(read_text(path), filename=str(path))
        return "OK"
    except SyntaxError as e:
        return f"SYNTAX_ERROR line={e.lineno} {e.msg}"

def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "phase": PHASE,
        "timestamp": TS,
        "root": str(ROOT),
        "candidate": None,
        "backup_dir": str(BACKUP_DIR),
        "applied": [],
        "errors": [],
        "checks": {},
        "DB_MUTATION": "NO",
        "SERVICE_RESTART": "NO",
        "MIGRATION_WRITE": "NO",
        "SSH_EXECUTION": "NO",
    }

    cand = latest_candidate()
    if not cand:
        result["errors"].append("CANDIDATE_NOT_FOUND")
        report = REPORT_DIR / f"phase114r2_apply_{TS}.json"
        write_text(report, json.dumps(result, ensure_ascii=False, indent=2))
        print(f"ERROR=CANDIDATE_NOT_FOUND")
        print(f"REPORT={report}")
        return 2

    result["candidate"] = str(cand)

    for rel in TARGET_RELS:
        src = cand / "files" / rel
        if not src.exists():
            result["errors"].append(f"MISSING_CANDIDATE_FILE:{rel}")
        elif rel.endswith(".py"):
            status = py_syntax(src)
            result["checks"][f"candidate_syntax:{rel}"] = status
            if status != "OK":
                result["errors"].append(f"SYNTAX_FAIL:{rel}:{status}")

    if result["errors"]:
        report = REPORT_DIR / f"phase114r2_apply_{TS}.json"
        write_text(report, json.dumps(result, ensure_ascii=False, indent=2))
        print("APPLY_ABORTED=YES")
        print(f"REPORT={report}")
        return 3

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for rel in TARGET_RELS:
        src = cand / "files" / rel
        dst = ROOT / rel
        bkp = BACKUP_DIR / rel
        bkp.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.copy2(dst, bkp)
        else:
            write_text(bkp.with_suffix(bkp.suffix + ".missing"), "MISSING_BEFORE_APPLY\n")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        result["applied"].append(rel)

    pyexe = ROOT / "venv" / "Scripts" / "python.exe"
    result["checks"]["manage_check"] = run_cmd([str(pyexe), "manage.py", "check"], 90)
    result["checks"]["makemigrations_check_dry_run"] = run_cmd([str(pyexe), "manage.py", "makemigrations", "--check", "--dry-run"], 90)

    failed = False
    if result["checks"]["manage_check"]["rc"] != 0:
        failed = True
    if result["checks"]["makemigrations_check_dry_run"]["rc"] != 0:
        failed = True

    report_json = REPORT_DIR / f"phase114r2_apply_{TS}.json"
    report_txt = REPORT_DIR / f"phase114r2_apply_{TS}.txt"
    write_text(report_json, json.dumps(result, ensure_ascii=False, indent=2))
    write_text(report_txt, "\n".join([
        PHASE,
        f"CANDIDATE={cand}",
        f"BACKUP_DIR={BACKUP_DIR}",
        f"APPLIED={','.join(result['applied'])}",
        f"MANAGE_CHECK_RC={result['checks']['manage_check']['rc']}",
        f"MAKEMIGRATIONS_CHECK_RC={result['checks']['makemigrations_check_dry_run']['rc']}",
        "DB_MUTATION=NO",
        "SERVICE_RESTART=NO",
        "MIGRATION_WRITE=NO",
        "SSH_EXECUTION=NO",
        f"REPORT_JSON={report_json}",
    ]))

    print(PHASE)
    print(f"CANDIDATE={cand}")
    print(f"BACKUP_DIR={BACKUP_DIR}")
    print(f"REPORT_JSON={report_json}")
    print(f"REPORT_TXT={report_txt}")
    print(f"MANAGE_CHECK_RC={result['checks']['manage_check']['rc']}")
    print(f"MAKEMIGRATIONS_CHECK_RC={result['checks']['makemigrations_check_dry_run']['rc']}")
    print("SERVICE_RESTART=NO")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
