# SwitchMap Phase 39 - VM Operations Toolkit

Scope:
- Adds operational scripts for the production VM.
- Does not change UI, database, models, migrations, switch graphics, SSH, SFP, alarms, topology, or backups logic.

Scripts:
- scripts\10_vm_health_check.cmd
- scripts\11_vm_backup_now.cmd
- scripts\12_vm_restart_waitress_task.cmd
- scripts\13_vm_stop_waitress_task.cmd
- scripts\14_vm_start_waitress_task.cmd
- scripts\15_vm_show_status.cmd

Primary URL:
- http://it-tools.winac-co.com:8000/

Rollback:
- Delete the six Phase 39 script files and this document.
