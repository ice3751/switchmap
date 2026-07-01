# SwitchMap Phase 73 - Safe Cleanup and Dashboard Header Cleanup

Scope:
- Remove only the dashboard manual `Refresh View` button; keep automatic dashboard polling and `آخرین بروزرسانی`.
- Delete only known generated test switch records: `Smoke`, `Phase41-*`, or `10.41.2.1`.
- Archive clutter files to `backups/phase73_safe_cleanup_*/archived_files` instead of destroying them.
- Keep scheduled task runner files required for production.

Not changed:
- Credentials
- Scheduled Task definitions
- SFP/CRC monitor code
- SNMP/CDP/LLDP pollers
- Topology logic
- Search
- Switch map layout

Rollback:
- Restore `db.sqlite3` from the printed Phase73 backup path.
- Restore `inventory/templates/inventory/switch_list.html` from the printed Phase73 backup path.
- Move archived files back from `archived_files` if needed.
