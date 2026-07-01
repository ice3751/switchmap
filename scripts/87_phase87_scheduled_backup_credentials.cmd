@echo off
setlocal
cd /d C:\SwitchMap
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check || goto :fail
python scripts\phase87_scheduled_backup_credentials.py || goto :fail
python manage.py check || goto :fail
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress" || goto :fail
echo PHASE87_SCHEDULED_BACKUP_CREDENTIALS_OK
exit /b 0
:fail
echo PHASE87_SCHEDULED_BACKUP_CREDENTIALS_FAIL
exit /b 1
