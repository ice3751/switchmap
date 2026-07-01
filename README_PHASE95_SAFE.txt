SwitchMap Phase95 — Packaging / Dependency / Safety Guards

Scope:
- requirements.txt: pin WhiteNoise used by current deployment.
- .gitignore: add explicit sensitive/generated patterns.
- scripts/phase77_make_safe_source_zip.py: harden safe source ZIP exclusions and add --check-only.
- smoke_tests/switchmap_project_source_snapshot.py: harden snapshot exclusions, remove shell=True, add --check-only.
- inventory/management/commands/phase95_packaging_safety_check.py: read-only guard.

No DB mutation.
No service restart.
No restore enablement.
No SSH/SNMP execution.
No backup write.
No UI/menu/device/test-data creation.

Run:
cd /d C:\SwitchMap
scripts\95_phase95_packaging_dependency_safety.cmd
