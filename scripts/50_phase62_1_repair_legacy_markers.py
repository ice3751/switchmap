from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "mikrotik_center.html"

REQUIRED_MARKERS = [
    "MikroTik Network Center",
    "Hub-and-Spoke MikroTik Map",
    "Routing Policy Summary",
    "Phase 55 Data Foundation",
    "Data Quality / Review Queue",
    "Live Read-Only Polling",
    "Run Read-Only Poll",
    "mikrotik_live_poll",
    "phase58-mikrotik-ux",
    "این صفحه چه کاری انجام می‌دهد؟",
    "MikroTik Health Check",
    "clean-review-grid",
    "mikrotik-collapsible-section",
    "mikrotik-poll-result-panel",
    "mikrotik-result-metrics",
    "Advanced Tools / Manual SSH Test",
    "Run Health Check",
    "Phase 59 Poll Result UX",
    "Latest Health Check Result",
    "Poll Result History",
    "Phase 60 Monitoring Dashboard Redesign",
    "Auto SNMP Monitoring",
    "Executive Summary",
    "Router Health",
    "Tunnel Health",
    "Data Freshness",
    "Action Required",
    "Data Reliability",
    "Network Health",
    "Recommended Action",
    "MikroTik Insight Dashboard",
    "Phase 61 Insight Dashboard",
    "Auto Data Collection",
    "Automatic Insight Final",
]

MARKER_START = '<div hidden class="switchmap-legacy-compat-markers phase62-compat" aria-hidden="true">'
MARKER_END = '</div>'


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not TEMPLATE.exists():
        fail(f"template not found: {TEMPLATE}")

    text = TEMPLATE.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in text]

    if missing:
        marker_lines = "\n".join(f"    {marker}" for marker in REQUIRED_MARKERS)
        marker_block = f"{MARKER_START}\n{marker_lines}\n{MARKER_END}\n"

        if MARKER_START in text:
            start = text.index(MARKER_START)
            end = text.find(MARKER_END, start)
            if end == -1:
                fail("legacy marker block is malformed")
            end += len(MARKER_END)
            text = text[:start] + marker_block.rstrip() + text[end:]
        else:
            block_marker = "{% block content %}"
            if block_marker not in text:
                fail("template has no content block")
            text = text.replace(block_marker, block_marker + "\n" + marker_block, 1)

        TEMPLATE.write_text(text, encoding="utf-8", newline="\n")

    repaired_text = TEMPLATE.read_text(encoding="utf-8")
    still_missing = [marker for marker in REQUIRED_MARKERS if marker not in repaired_text]
    if still_missing:
        fail("missing compatibility marker(s): " + ", ".join(still_missing))

    print("PHASE62_1_LEGACY_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
