# Phase 78 - Operational Alarm Cleanup

Scope: additive only.

Added:
- `/alarms/cleanup/` Operational Alarm Cleanup page
- `/phase78/alarm-cleanup/status.json` read-only status JSON
- `Recheck` action that calls the existing alarm sync logic
- `Resolve Stale Candidates` action for alarms where the current DB condition no longer matches
- SNMP timeout device summary
- Active alarm grouping by category and device
- Read-only management report command
- Apply and verify scripts

Protected / unchanged:
- Dashboard rendering
- Quick Search
- SSH popup and SSH actions
- SFP Monitor page
- Topology page
- Backup Center
- Existing Alarm Center URLs and behavior

Notes:
- No migration.
- No new model.
- No network polling.
- Recheck only resyncs alarms based on existing DB state.
