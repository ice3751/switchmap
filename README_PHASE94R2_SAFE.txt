Phase94R2 — Verification and Reproducibility Baseline

Scope:
- Installs read-only smoke runner and verification management command.
- Replaces the broken historical smoke manifest with a valid Phase94R2 manifest.
- Creates source baseline hash report in logs.
- Does not create devices, ports, menus, URLs, UI entries, DB rows, backups, restore jobs, SSH/SNMP actions, or Scheduled Task changes.
- Does not restart SwitchMap Waitress.

Run:
cd /d C:\SwitchMap
scripts\94_phase94_verification_baseline.cmd
