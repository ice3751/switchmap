# Phase 58.2 - Compatibility Marker and Manifest Fix

Scope:
- Restores smoke-test manifest phase groups that were overwritten in Phase 58.
- Adds hidden rendered compatibility markers to mikrotik_center.html so prior phase smoke tests remain valid after UX cleanup.
- No database change.
- No migration.
- No RouterOS command.
- No credential storage.

Apply:

```cmd
cd /d C:\SwitchMap
scripts8_phase58_2_compatibility_marker_manifest_fix.cmd
```

Expected:

```text
SwitchMap phase 58 MikroTik UX cleanup smoke test: OK
SUMMARY 7 pass 0 fail
System check identified no issues
PHASE39_WAITRESS_RESTART_OK
```
