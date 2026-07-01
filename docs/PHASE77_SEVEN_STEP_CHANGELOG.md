# SwitchMap Phase 77 - Seven Step Execution

Scope: additive and low-risk. Existing Dashboard, Login/Roles, SSH Actions, Popup, Refresh, Alarm Center, SFP Monitor, Topology, Backup and Quick Search are not replaced.

## 1. Stabilization Lock
- Added management command: `python manage.py phase77_stabilization_check`
- Added CMD wrappers under `scripts\`.
- Checks URL names, critical UI/JS markers, DB counts and role boundary.

## 2. Performance
- Added short cache for topbar alarm count and switch dropdown menu.
- Added DB indexes for common Search/Asset fields.
- Added safe source ZIP generator excluding DB, secrets, backups, logs, venv and git data.

## 3. Asset Documentation
- Added `/assets/completion/` page.
- Shows documentation completion per switch.
- Lists target ports for documentation cleanup.

## 4. Controlled Refactor
- New code is isolated in `inventory/phase77_views.py` and scoped templates/CSS.
- Existing `inventory/views.py`, dashboard rendering, popup and quick search are not refactored or replaced.

## 5. Automation / Job Template
- Added `SSHJobTemplate` model.
- Added `/automation/templates/` pages.
- Supports Preview of commands only; actual SSH execution remains in the existing stable SSH path.

## 6. Config Backup / Diff
- Added `ConfigBackupSnapshot` model.
- Added `/config-backups/` page.
- Manual paste/import of config with SHA256 hash and unified diff against previous snapshot.
- No automatic SSH pull is enabled in this phase.

## 7. NOC Dashboard
- Added `/noc/` page.
- Aggregates active alarms, SNMP stale/fail count, SFP issues, documentation status, router health and recent operations.

## Apply

```cmd
cd /d C:\SwitchMap
scripts\77_phase77_seven_step_apply.cmd
```

## Verify only

```cmd
cd /d C:\SwitchMap
scripts\77_phase77_verify_only.cmd
```

## Rollback

Restore the project folder from the backup taken before applying this package, or revert these files and migration:

- `inventory/models.py`
- `inventory/admin.py`
- `inventory/context_processors.py`
- `inventory/urls.py`
- `inventory/phase77_views.py`
- `inventory/migrations/0018_phase77_indexes_and_operational_models.py`
- `inventory/templates/inventory/base.html`
- `inventory/templates/inventory/phase77/*`
- `inventory/static/inventory/css/switchmap-phase77.css`
- `inventory/management/commands/phase77_stabilization_check.py`
- `scripts/77_phase77_*`
- `scripts/phase77_make_safe_source_zip.py`

For database rollback after migration, restore the SQLite backup taken before applying. Do not reverse migrations on production without a DB backup.
