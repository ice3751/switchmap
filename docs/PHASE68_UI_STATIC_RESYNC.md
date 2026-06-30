# Phase 68 UI Static Resync Recovery

Scope:
- Restore only these four UI files from `backups/phase68_quick_search_port_labels_20260626_153030` baseline:
  - `inventory/templates/inventory/base.html`
  - `inventory/templates/inventory/switch_list.html`
  - `inventory/static/inventory/switchmap.js`
  - `inventory/static/inventory/css/switchmap-dashboard-stable-main.css`
- Do not touch SQLite database.
- Clear/rebuild `staticfiles` so `WhiteNoise` stops serving stale Phase 69 JS/CSS.
- Restart Waitress task if the existing restart script is present.

Run read-only check first:

```cmd
cd /d C:\SwitchMap
scripts\91_readonly_phase68_ui_status.cmd
```

Apply recovery:

```cmd
cd /d C:\SwitchMap
scripts\92_recovery_phase68_ui_static_resync.cmd
```

Rollback example is printed by the script if a step fails.
