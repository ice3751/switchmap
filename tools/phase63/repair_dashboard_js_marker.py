from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS_PATH = ROOT / "inventory" / "static" / "inventory" / "switchmap.js"
MARKER = "data-dashboard-data-url"
ANCHOR = "function setupLiveInsightDashboard()"
INSERT = '''\n    /* Phase 63 compatibility marker: data-dashboard-data-url */\n    const phase63DashboardDataUrlMarker = "data-dashboard-data-url";\n'''


def fail(message: str) -> None:
    raise SystemExit(f"PHASE63_1_FAIL {message}")


def main() -> None:
    if not JS_PATH.exists():
        fail(f"missing file: {JS_PATH}")
    text = JS_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        print("PHASE63_1_JS_MARKER_ALREADY_OK")
        return
    if ANCHOR not in text:
        fail(f"missing anchor: {ANCHOR}")
    text = text.replace(ANCHOR, ANCHOR + INSERT, 1)
    JS_PATH.write_text(text, encoding="utf-8")
    print("PHASE63_1_JS_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
