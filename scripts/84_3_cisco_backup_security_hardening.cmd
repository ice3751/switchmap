@echo off
setlocal
cd /d C:\SwitchMap
if errorlevel 1 exit /b 1
call venv\Scriptsctivate
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check
if errorlevel 1 exit /b 1
python scripts\phase84_3_cisco_backup_security_hardening.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
if errorlevel 1 exit /b 1
endlocal
