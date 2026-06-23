SwitchMap Phase 37 - Production package

Apply:
1. Extract this ZIP.
2. Copy all extracted files into:
   C:\Users\a-mortazavi.WINAC-CO\SwitchMap
3. Replace existing files.

Changed scope:
- Production settings
- Waitress runner
- Windows Task Scheduler scripts
- Optional NSSM service scripts
- Scheduled SQLite backup scripts
- Production check command
- Production install/recovery documentation

Not changed:
- Cisco 3850 / Nexus UI
- Dashboard templates
- switchmap.css / switchmap.js
- Models / migrations
- db.sqlite3

After replace:
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
venv\Scripts\activate
python manage.py check
python manage.py backup_sqlite --check-only

For real production:
1. Edit switchmap.env based on switchmap.production.env.example.
2. Run:
   scripts\phase37_prepare_production.cmd
3. Test Waitress:
   scripts\run_waitress.cmd
4. Optional startup task:
   scripts\install_waitress_startup_task.cmd
5. Scheduled backup:
   scripts\install_backup_task.cmd
