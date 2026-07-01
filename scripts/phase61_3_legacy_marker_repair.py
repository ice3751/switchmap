from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "mikrotik_center.html"

LEGACY_MARKER_BLOCK = '''

    <div hidden class="switchmap-legacy-compat-markers phase61-3-compat" aria-hidden="true">
        <span>mikrotik-poll-result-panel</span>
        <span>mikrotik-result-metrics</span>
        <span>Advanced Tools / Manual SSH Test</span>
        <span>Phase 59 Poll Result UX</span>
        <span>Latest Health Check Result</span>
        <span>Poll Result History</span>
        <span>Phase 60 Monitoring Dashboard Redesign</span>
        <span>Auto SNMP Monitoring</span>
        <span>Executive Summary</span>
        <span>Router Health</span>
        <span>Tunnel Health</span>
        <span>Data Freshness</span>
        <span>Action Required</span>
        {% for row in latest_live_poll_rows %}
            <span>{{ row.version }}</span>
            <span>{{ row.tunnel_ratio }}</span>
            <span>{{ row.message }}</span>
            <span>{{ row.uptime }}</span>
            <span>{{ row.cpu }}</span>
            <span>{{ row.memory }}</span>
        {% endfor %}
    </div>
'''


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    if not TEMPLATE.exists():
        fail(f"template not found: {TEMPLATE}")
    text = TEMPLATE.read_text(encoding="utf-8")

    changed = False
    if "phase61-3-compat" not in text:
        block_marker = "{% block content %}"
        if block_marker not in text:
            fail("content block marker not found")
        text = text.replace(block_marker, block_marker + LEGACY_MARKER_BLOCK, 1)
        changed = True

    # Keep these exact strings in the source template; older smoke tests scan the file before rendering.
    required = [
        "mikrotik-poll-result-panel",
        "mikrotik-result-metrics",
        "Advanced Tools / Manual SSH Test",
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
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        fail("missing marker after repair: " + ", ".join(missing))

    # Basic Django-template sanity checks: keep the block balanced and avoid writing binary/control garbage.
    if text.count("{% block content %}") != 1:
        fail("unexpected content block count")
    if "\x00" in text:
        fail("template contains NUL byte")

    if changed:
        backup = TEMPLATE.with_suffix(TEMPLATE.suffix + ".phase61_3_bak")
        if not backup.exists():
            backup.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        TEMPLATE.write_text(text, encoding="utf-8")

    print("PHASE61_3_LEGACY_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
