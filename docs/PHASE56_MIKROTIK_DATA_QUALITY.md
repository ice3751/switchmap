# SwitchMap Phase 56 - MikroTik Data Quality

Scope:
- Adds `/mikrotik/data/` read-only JSON endpoint.
- Adds Data Quality / Review Queue to MikroTik Center.
- Filters SwitchMap smoke/test devices from MikroTik Center and JSON output.
- Keeps MikroTik Center model-backed after Phase 55.

No database, migration, environment, credential, SSH backend, SNMP polling, RouterOS command or operational change is included.

Validation:
```cmd
cd /d C:\SwitchMap
scripts\28_phase56_mikrotik_data_quality.cmd
```

Expected:
```text
SwitchMap phase 56 MikroTik data quality smoke test: OK
SUMMARY 5 pass 0 fail
System check identified no issues
PHASE39_WAITRESS_RESTART_OK
```

Rollback:
Restore these files from the previous project backup:
- `inventory/mikrotik_views.py`
- `inventory/urls.py`
- `inventory/templates/inventory/mikrotik_center.html`
- `inventory/static/inventory/css/switchmap-mikrotik.css`
- `smoke_tests/manifest.json`

Then remove:
- `smoke_tests/switchmap_56_mikrotik_data_quality_smoke_test.py`
- `scripts/28_phase56_mikrotik_data_quality.cmd`
- `docs/PHASE56_MIKROTIK_DATA_QUALITY.md`
- `README_PHASE56_APPLY.txt`
