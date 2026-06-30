# Phase79.1 - Port Connection History Foundation

Scope:
- Adds PortConnectionHistory model and migration.
- Adds safe capture helper for current Port identity data.
- Hooks SNMP status changes and discovery identity snapshots with try/except guard.
- Does not change Dashboard, Popup UI, SSH UI, Quick Search, Topology or Alarm logic.

Operational note:
- Existing down ports cannot show last connected device unless current Port table already has neighbor/MAC/device data.
- From this phase onward, discovery/status polling can preserve last connected history for future disconnects.
