from pathlib import Path
import hashlib
import sys

PROJECT = Path(__file__).resolve().parent.parent
BASELINE = PROJECT / "backups" / "phase68_quick_search_port_labels_20260626_153030"
TARGETS = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
]
STATIC_MAP = {
    Path("inventory/static/inventory/switchmap.js"): Path("staticfiles/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"): Path("staticfiles/inventory/css/switchmap-dashboard-stable-main.css"),
}

def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def status(label, ok):
    print(f"{label}={'OK' if ok else 'FAIL'}")

def main():
    print(f"PROJECT={PROJECT}")
    status("BASELINE_EXISTS", BASELINE.exists())
    if not BASELINE.exists():
        print(f"MISSING_BASELINE={BASELINE}")
        return 2
    fail = False
    for rel in TARGETS:
        cur = PROJECT / rel
        bak = BASELINE / rel
        ok = cur.exists() and bak.exists() and md5(cur) == md5(bak)
        status(f"APP_MATCH_PHASE68::{rel}", ok)
        if not ok:
            fail = True
    for app_rel, static_rel in STATIC_MAP.items():
        app = PROJECT / app_rel
        st = PROJECT / static_rel
        ok = app.exists() and st.exists() and md5(app) == md5(st)
        status(f"STATIC_MATCH_APP::{static_rel}", ok)
        if not ok and st.exists():
            print(f"STATIC_MD5::{static_rel}={md5(st)}")
            print(f"APP_MD5::{app_rel}={md5(app)}")
    env = PROJECT / "switchmap.env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("SWITCHMAP_DEBUG="):
                print(line)
    include = PROJECT / "inventory" / "templates" / "inventory" / "includes" / "cisco_3850_svg.html"
    if include.exists():
        txt = include.read_text(encoding="utf-8", errors="replace")
        print("CISCO3850_HAS_DATA_DESCRIPTION=" + ("YES" if "data-description" in txt else "NO"))
        print("CISCO3850_HAS_DATA_SEARCH_CODE=" + ("YES" if "data-search-code" in txt else "NO"))
    return 1 if fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
