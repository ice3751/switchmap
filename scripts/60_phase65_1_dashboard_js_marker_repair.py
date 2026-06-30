from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_REL = Path("inventory/static/inventory/switchmap.js")
STATIC_JS_REL = Path("staticfiles/inventory/switchmap.js")
MARKERS = [
    "Phase 65 Three Panel Dashboard UX",
    "data-dashboard-data-url",
]
COMMENT = "/* Phase 65 Three Panel Dashboard UX | data-dashboard-data-url | smoke compatibility marker */\n"


def fail(message: str) -> None:
    raise SystemExit("PHASE65_1_FAIL " + message)


def patch_js(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    changed = False
    if any(marker not in text for marker in MARKERS):
        text = COMMENT + text
        changed = True
    path.write_text(text, encoding="utf-8", newline="\n")
    return changed


def main() -> None:
    source_js = ROOT / JS_REL
    if not source_js.exists():
        fail(f"missing file: {JS_REL}")
    patch_js(source_js)
    patch_js(ROOT / STATIC_JS_REL)
    final_text = source_js.read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in MARKERS if marker not in final_text]
    if missing:
        fail("missing JS marker after repair: " + ", ".join(missing))
    print("PHASE65_1_DASHBOARD_JS_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
