# Phase79.2 - Port Last Connected UI

Scope:
- Read-only display of PortConnectionHistory in Dashboard popup and Full Map detail panel.
- Uses existing port payload endpoint.
- Adds switchmap-phase79.css.
- No migration.
- No SSH logic change.
- No alarm/topology/search logic change.

Expected UI:
- Click a port.
- See "Last Connected Device" section.
- If no history exists, it shows "سابقه‌ای ثبت نشده".
