# SwitchMap Phase 55 - MikroTik Data Model Foundation

## Scope

Adds read-only data models for MikroTik architecture:

- Site
- WanLink
- RouterTunnel
- RoutingPolicy
- RouterHealthSnapshot

Updates MikroTik Center to prefer model-backed Site / WAN / Tunnel / Routing data when available, while preserving the previous inferred fallback.

## Operational safety

No RouterOS command is executed.
No SSH / Winbox / API credential is stored.
No live device configuration is changed.

## Database change

This phase includes migration:

- `inventory/migrations/0017_phase55_mikrotik_data_foundation.py`

## Apply

```cmd
cd /d C:\SwitchMap
scripts\26_phase55_mikrotik_data_foundation.cmd
```

## Manual validation

```cmd
cd /d C:\SwitchMap
venv\Scripts\activate
python smoke_tests\switchmap_55_mikrotik_data_foundation_smoke_test.py
python smoke_tests\run_smoke.py current
python manage.py check
call scripts\12_vm_restart_waitress_task.cmd
```

Then open:

```text
http://192.168.0.11:8000/mikrotik/
```

## Rollback

Preferred rollback is restoring the pre-phase project backup and SQLite backup.

If only code rollback is required, restore previous versions of:

- `inventory/models.py`
- `inventory/admin.py`
- `inventory/mikrotik_views.py`
- `inventory/templates/inventory/mikrotik_center.html`
- `inventory/static/inventory/css/switchmap-mikrotik.css`
- `smoke_tests/manifest.json`

Then remove added files:

- `inventory/migrations/0017_phase55_mikrotik_data_foundation.py`
- `inventory/management/commands/seed_mikrotik_foundation.py`
- `smoke_tests/switchmap_55_mikrotik_data_foundation_smoke_test.py`
- `scripts/26_phase55_mikrotik_data_foundation.cmd`
- `docs/PHASE55_MIKROTIK_DATA_FOUNDATION.md`

If the migration was already applied, database rollback must be done from SQLite backup unless you intentionally drop the new phase 55 tables.
