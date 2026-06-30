@echo off
setlocal EnableExtensions
cd /d C:\SwitchMap || exit /b 1
call venv\Scripts\activate || exit /b 1
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check || exit /b 1
python scripts\phase86_secure_backup_storage.py || exit /b 1
python manage.py backup_storage_verify --strict || exit /b 1
python manage.py check || exit /b 1
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress" || exit /b 1
exit /b 0
