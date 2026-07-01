Phase93 — Performance Safe Refine

Scope:
- Safe optimization of inventory/context_processors.py alarm counts.
- Adds management command phase93_performance_safe_refine_check.
- No UI layout change.
- No URL/role/backup/alarm/SSH behavior change.
- No DB schema migration.
- No restore enablement.

Changed by apply script after backup:
- inventory/context_processors.py
- inventory/management/commands/phase93_performance_safe_refine_check.py

Verify:
- py_compile changed files
- python manage.py check
- phase93_performance_safe_refine_check --strict
- phase77_stabilization_check
- phase80_alarm_normalization_check
- scheduled_backup_credential_check --profile all --strict
- backup_storage_verify --strict
- backup_health_report --strict
- Scheduled Backup task query

Restart:
- SwitchMap Waitress restarts only after all verify steps succeed.

Rollback:
- Automatic rollback on apply/verify failure.
- File backup path: C:\SwitchMap\backups\phase93_performance_safe_refine_<timestamp>
