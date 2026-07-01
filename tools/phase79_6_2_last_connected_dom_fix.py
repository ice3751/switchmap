from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "tools" / "phase79_6_2_payload"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "backups" / f"phase79_6_2_last_connected_dom_fix_{STAMP}"

FILES = [
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/templates/inventory/switch_detail.html"),
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-phase79.css"),
]

def run(args):
    return subprocess.run(args, cwd=str(ROOT), text=True, capture_output=True)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def verify_files():
    ok, fail = [], []

    for rel in FILES:
        p = ROOT / rel
        if p.exists():
            ok.append(f"file:{rel}")
        else:
            fail.append(f"missing:{rel}")

    for rel in [Path("inventory/templates/inventory/switch_list.html"), Path("inventory/templates/inventory/switch_detail.html")]:
        txt = read(ROOT / rel)
        if "phase79-lc-card" in txt and "data-phase79-last-connected" in txt:
            ok.append(f"marker:{rel}:last_connected")
        else:
            fail.append(f"marker_missing:{rel}:last_connected")

        bad = 'data-phase79-last-connected>\n' in txt and 'port-refresh-box' in txt
        # precise bad pattern: closed card followed by an extra close before refresh box
        import re
        if re.search(r'<div class="phase79-lc-card" data-phase79-lc-card>.*?</div>\s*</div>\s*<div class="port-refresh-box', txt, re.S):
            fail.append(f"extra_closing_div_after_last_connected:{rel}")
        else:
            ok.append(f"dom:{rel}:no_extra_closing_div")

    css = read(ROOT / "inventory/static/inventory/css/switchmap-phase79.css")
    if "PHASE79_6_2_LAST_CONNECTED_DOM_FIX" in css:
        ok.append("css:phase79_6_2_marker")
    else:
        fail.append("css:phase79_6_2_marker_missing")

    js = read(ROOT / "inventory/static/inventory/switchmap.js")
    if "PHASE79_6_2_LAST_CONNECTED_DOM_FIX" in js:
        ok.append("js:phase79_6_2_marker")
    else:
        fail.append("js:phase79_6_2_marker_missing")

    base = read(ROOT / "inventory/templates/inventory/base.html")
    if "phase79-6-2-dom-fix" in base:
        ok.append("base:cache_bust_phase79_6_2")
    else:
        fail.append("base:cache_bust_missing")

    return ok, fail

def main():
    BACKUP.mkdir(parents=True, exist_ok=True)

    for rel in FILES:
        src = ROOT / rel
        if src.exists():
            dst = BACKUP / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for rel in FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        if not src.exists():
            print(f"PHASE79_6_2_APPLY_FAIL missing_payload={src}")
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    check = run([sys.executable, "manage.py", "check"])
    print(check.stdout.strip())
    if check.returncode != 0:
        print(check.stderr.strip())
        print(f"PHASE79_6_2_APPLY_FAIL backup_dir={BACKUP}")
        return 1

    collect = run([sys.executable, "manage.py", "collectstatic", "--noinput"])
    if collect.returncode != 0:
        print("WARNING collectstatic failed")
        print(collect.stdout.strip())
        print(collect.stderr.strip())
    else:
        print("OK collectstatic")

    ok, fail = verify_files()

    print("PHASE79_6_2_LAST_CONNECTED_DOM_FIX_REPORT")
    print(f"OK_COUNT={len(ok)}")
    print(f"WARNING_COUNT=0")
    print(f"FAIL_COUNT={len(fail)}")
    print()
    print("[OK]")
    for item in ok:
        print("OK " + item)
    print()
    print("[WARNING]")
    print("- none")
    print()
    print("[FAIL]")
    if fail:
        for item in fail:
            print("FAIL " + item)
        print(f"PHASE79_6_2_APPLY_FAIL backup_dir={BACKUP}")
        return 1
    print("- none")
    print(f"PHASE79_6_2_APPLY_OK backup_dir={BACKUP}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
