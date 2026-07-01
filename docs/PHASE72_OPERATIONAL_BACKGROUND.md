# Phase 72 Operational Background Stabilization

Scope:
- Windows DPAPI protected SSH monitor credential.
- Permanent SFP monitor via SSH read-only show commands.
- Cisco CRC/Input/Output error delta monitor and AlarmNotification creation.
- Scheduled Task registration for dashboard SNMP/CDP/LLDP refresh and SFP/CRC monitor.
- Read-only status report.

No password is stored in SQLite. The SSH credential is encrypted with Windows DPAPI and can be decrypted only by the same Windows user that created it.

Rollback:
- Disable SFP task: `scripts\103_phase72_disable_sfp_background_monitor.cmd`
- Delete credential: `python manage.py set_ssh_monitor_credentials --delete`
- Restore backed up files from `backups\phase72_operational_background_*` if needed.
