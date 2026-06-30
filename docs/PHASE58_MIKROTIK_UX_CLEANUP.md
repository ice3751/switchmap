# SwitchMap Phase 58 - MikroTik UX Cleanup

Scope:
- Clean up MikroTik Center layout.
- Explain what the page does and does not do.
- Rename Live Read-Only Polling to MikroTik Health Check in the UI.
- Compact Data Quality / Review Queue.
- Move detailed Tunnel / WAN / Routing tables into collapsible sections.

No changes:
- No migration.
- No database change.
- No RouterOS write action.
- No credential storage.
- No SSH backend behavior change.

Validation:
```cmd
cd /d C:\SwitchMap
scripts\36_phase58_mikrotik_ux_cleanup.cmd
```

Expected:
```text
SwitchMap phase 58 MikroTik UX cleanup smoke test: OK
SUMMARY 7 pass 0 fail
System check identified no issues
PHASE39_WAITRESS_RESTART_OK
```
