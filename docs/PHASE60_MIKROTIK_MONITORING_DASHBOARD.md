# SwitchMap Phase 60 - MikroTik Monitoring Dashboard

Purpose: replace the manual, noisy MikroTik page with a concise monitoring dashboard.

## Scope

- Read-only monitoring dashboard.
- SNMP-based automatic baseline collector.
- Manual SSH health check moved to Advanced Tools.
- Executive summary, router health chart, tunnel health chart, freshness ring and action list.
- JSON endpoint extended with monitoring summary and auto SNMP metadata.

## Safety

- No RouterOS configuration change.
- No SSH credential storage.
- No database migration.
- No destructive operation.
- Windows scheduled task only runs a read-only Django management command.

## Auto collector

Command:

```cmd
python manage.py poll_mikrotik_auto_snmp
```

Scheduled task name:

```text
SwitchMap MikroTik Auto SNMP Poll
```

Runner:

```cmd
scripts\41_mikrotik_auto_snmp_poll_runner.cmd
```

Rollback for the scheduled task:

```cmd
schtasks /Delete /TN "SwitchMap MikroTik Auto SNMP Poll" /F
```
