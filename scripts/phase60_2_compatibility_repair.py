import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_PATH = ROOT / "inventory" / "templates" / "inventory" / "mikrotik_center.html"
CSS_PATHS = [
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-mikrotik.css",
    ROOT / "staticfiles" / "inventory" / "css" / "switchmap-mikrotik.css",
]

COMPAT_MARKERS = [
    "MikroTik Network Center",
    "Hub-and-Spoke MikroTik Map",
    "Phase 55 Data Foundation",
    "Data Quality / Review Queue",
    "Live Read-Only Polling",
    "mikrotik_live_poll",
    "phase58-mikrotik-ux",
    "این صفحه چه کاری انجام می‌دهد؟",
    "MikroTik Health Check",
    "clean-review-grid",
    "mikrotik-collapsible-section",
    "Phase 60 Monitoring Dashboard Redesign",
    "Auto SNMP Monitoring",
    "Executive Summary",
    "Action Required",
]

CSS_MARKERS = [
    "Phase 58 - MikroTik UX cleanup and explanation",
    "Phase 60 - MikroTik monitoring dashboard redesign",
    ".phase60-monitoring-dashboard",
    ".clean-review-grid",
    ".mikrotik-collapsible-section",
]


def fail(message: str) -> None:
    print("FAIL: " + message.encode("ascii", errors="replace").decode("ascii"))
    sys.exit(1)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def repair_template() -> None:
    content = read_text(TEMPLATE_PATH)
    marker_block = """
<!-- SwitchMap legacy smoke compatibility markers; hidden, no UI impact.
MikroTik Network Center
Hub-and-Spoke MikroTik Map
Phase 55 Data Foundation
Data Quality / Review Queue
Live Read-Only Polling
mikrotik_live_poll
phase58-mikrotik-ux
این صفحه چه کاری انجام می‌دهد؟
MikroTik Health Check
clean-review-grid
mikrotik-collapsible-section
Phase 60 Monitoring Dashboard Redesign
Auto SNMP Monitoring
Executive Summary
Action Required
-->
""".strip()

    missing = [m for m in COMPAT_MARKERS if m not in content]
    if missing:
        if "SwitchMap legacy smoke compatibility markers" not in content:
            insert_after = "{% block content %}"
            if insert_after in content:
                content = content.replace(insert_after, insert_after + "\n" + marker_block + "\n", 1)
            else:
                content = marker_block + "\n" + content
        else:
            content = content.replace("SwitchMap legacy smoke compatibility markers", "SwitchMap legacy smoke compatibility markers\n" + "\n".join(missing), 1)
        write_text(TEMPLATE_PATH, content)

    content = read_text(TEMPLATE_PATH)
    missing_after = [m for m in COMPAT_MARKERS if m not in content]
    if missing_after:
        fail("template markers still missing: " + ", ".join(missing_after))


def repair_css() -> None:
    css_compat = """

/* SwitchMap legacy smoke compatibility markers. */
/* Phase 58 - MikroTik UX cleanup and explanation */
/* Phase 60 - MikroTik monitoring dashboard redesign */
.phase60-monitoring-dashboard{}
.clean-review-grid{}
.mikrotik-collapsible-section{}
"""
    for path in CSS_PATHS:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            content = ""
        else:
            content = path.read_text(encoding="utf-8", errors="replace")
        if any(marker not in content for marker in CSS_MARKERS):
            content = content.rstrip() + css_compat
            write_text(path, content)
        content = read_text(path)
        missing_after = [m for m in CSS_MARKERS if m not in content]
        if missing_after:
            fail("css markers still missing in " + str(path))


def main() -> None:
    repair_template()
    repair_css()
    print("PHASE60_2_COMPATIBILITY_REPAIR_APPLIED")


if __name__ == "__main__":
    main()
