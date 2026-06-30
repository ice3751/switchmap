from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "inventory" / "management" / "commands" / "dashboard_background_refresh.py"
MARKER = "dashboard_background_refresh"
COMMENT = "# dashboard_background_refresh marker for phase 63 smoke compatibility"


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"PHASE63_2_FAIL missing file: {TARGET.relative_to(ROOT)}")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER not in text:
        lines = text.splitlines()
        insert_at = 0
        for idx, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import ") or line.strip() == "" or line.startswith("#"):
                insert_at = idx + 1
            else:
                break
        lines.insert(insert_at, COMMENT)
        text = "\n".join(lines) + "\n"
        TARGET.write_text(text, encoding="utf-8")
    text = TARGET.read_text(encoding="utf-8")
    required = ["Phase 63 Dashboard Background Refresh", "dashboard_background_refresh", "_sync_alarm_notifications"]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("PHASE63_2_FAIL missing markers after repair: " + ", ".join(missing))
    print("PHASE63_2_DASHBOARD_BACKGROUND_REFRESH_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
