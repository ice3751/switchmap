@echo off
setlocal
cd /d C:\SwitchMap
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check || exit /b 1
python scripts\phase86_2_backup_hash_repair.py || exit /b 1
python manage.py backup_storage_verify --strict || exit /b 1
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
echo PHASE86_2_BACKUP_HASH_REPAIR_OK
