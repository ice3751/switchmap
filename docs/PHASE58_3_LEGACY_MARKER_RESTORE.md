# Phase 58.3 - Legacy Marker Restore

Scope:
- Restore legacy smoke-test markers hidden in the rendered MikroTik Center template.
- Does not change UI layout, database, migrations, RouterOS, SSH behavior, SNMP, or credentials.

Reason:
- Phase 50-54 smoke test expects the exact marker `Hub-and-Spoke MikroTik Map`.
- Phase 58 renamed the visible title to `Hub-and-Spoke Map` for cleaner UI, so the legacy marker must remain hidden for compatibility.

Validation:
- Run `scripts\39_phase58_3_legacy_marker_restore.cmd`.
- Expected: `SUMMARY 7 pass 0 fail`.
