from pathlib import Path

from switchmap_smoke import read_static_css

ROOT = Path(__file__).resolve().parent

checks = {
    "inventory/templates/inventory/switch_list.html": [
        "sfp-dash-control ui-mini-tool",
        "data-sfp-dashboard-form",
        "alarm-mini-dropdown",
    ],
    "inventory/templates/inventory/switch_ports_table.html": [
        "bulk-ssh-panel ui-collapsible",
        "ui-collapsible-summary",
        "data-bulk-ssh-form",
        "compact-title-row",
    ],
    "inventory/templates/inventory/alarm_center.html": [
        "alarm-filter-panel",
        "alarm-bulk-actions",
        "data-alarm-select-all",
    ],
    "inventory/templates/inventory/sfp_monitor.html": [
        "sfp-control-card ui-collapsible",
        "id=\"sfpPollForm\"",
        "id=\"sfpLiveState\"",
    ],
}

for rel_path, needles in checks.items():
    path = ROOT / rel_path
    assert path.exists(), f"missing file: {rel_path}"
    content = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in content, f"missing marker in {rel_path}: {needle}"

css = read_static_css()
for needle in [
    "Phase 31C - UI stabilization and compact layout cleanup",
    ".ui-collapsible-summary",
    ".dashboard-overview-grid",
    ".sfp-dash-control",
]:
    assert needle in css, f"missing css marker: {needle}"

print("PHASE31C_UI_CLEANUP_OK")
