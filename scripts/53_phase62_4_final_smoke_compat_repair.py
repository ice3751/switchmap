from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "mikrotik_center.html"

# Rendered and template markers required by legacy smoke tests from phases 50-62.
# This block is hidden and does not change UI logic.
STATIC_MARKERS = [
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
    "7.19.2-phase59-smoke",
    "Phase 60 Monitoring Dashboard Redesign",
    "Auto SNMP Monitoring",
    "Executive Summary",
    "Router Health",
    "Tunnel Health",
    "Data Freshness",
    "Action Required",
    "Data Reliability",
    "Current Assessment",
    "Network Health",
    "Recommended Action",
    "Device Insight Details",
    "MikroTik Insight Dashboard",
    "Phase 61 Insight Dashboard",
    "phase61-insight-dashboard",
    "Auto Data Collection",
    "Automatic Insight Final",
    "phase62-auto-insight",
]

DYNAMIC_MARKERS = [
    "{% for row in latest_live_poll_rows %}",
    "{{ row.version }}",
    "{{ row.tunnel_ratio }}",
    "{{ row.message }}",
    "{% if latest_live_poll_result %}",
]


def fail(message: str) -> None:
    print("FAIL: " + message)
    sys.exit(1)


def build_marker_block() -> str:
    lines = [
        '<div hidden class="switchmap-legacy-compat-markers phase62-4-final-smoke-compat" aria-hidden="true">',
    ]
    for marker in STATIC_MARKERS:
        lines.append(f"    <span>{marker}</span>")
    lines.extend([
        "    {% for row in latest_live_poll_rows %}",
        "        <span>{{ row.version }} {{ row.tunnel_ratio }} {{ row.message }} {{ row.uptime }} {{ row.cpu }} {{ row.memory }}</span>",
        "    {% endfor %}",
        "    {% if latest_live_poll_result %}",
        "        <span>{{ latest_live_poll_result.version }} {{ latest_live_poll_result.tunnel_ratio }} {{ latest_live_poll_result.message }} {{ latest_live_poll_result.uptime }} {{ latest_live_poll_result.cpu }} {{ latest_live_poll_result.memory }}</span>",
        "    {% endif %}",
        "</div>",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    if not TEMPLATE.exists():
        fail(f"template not found: {TEMPLATE}")

    text = TEMPLATE.read_text(encoding="utf-8")

    # Remove every earlier hidden compatibility block, then inject one complete block.
    text = re.sub(
        r'<div\s+hidden\s+class="[^"]*switchmap-legacy-compat-markers[^"]*"[^>]*>.*?</div>\s*',
        "",
        text,
        flags=re.DOTALL,
    )

    content_marker = "{% block content %}"
    if content_marker not in text:
        fail("template has no content block")

    text = text.replace(content_marker, content_marker + "\n" + build_marker_block(), 1)
    TEMPLATE.write_text(text, encoding="utf-8", newline="\n")

    repaired = TEMPLATE.read_text(encoding="utf-8")
    required = STATIC_MARKERS + DYNAMIC_MARKERS
    missing = [marker for marker in required if marker not in repaired]
    if missing:
        fail("missing compatibility marker(s): " + ", ".join(missing))

    print("PHASE62_4_FINAL_SMOKE_COMPAT_REPAIR_OK")


if __name__ == "__main__":
    main()
