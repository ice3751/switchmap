@echo off
setlocal EnableExtensions
cd /d C:\SwitchMap || exit /b 1
call venv\Scripts\activate || exit /b 1
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check || exit /b 1
python scripts\phase85_mikrotik_backup_center.py || exit /b 1
python manage.py check || exit /b 1
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress" || exit /b 1
exit /b 0
