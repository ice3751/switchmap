@echo off
setlocal
cd /d C:\SwitchMap
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\manage.py backup_sqlite
if errorlevel 1 goto fail

echo.
echo Latest backups:
dir /O-D /B C:\SwitchMap\backups\sqlite | more +0

echo.
echo PHASE39_BACKUP_NOW_OK
exit /b 0

:fail
echo PHASE39_BACKUP_NOW_FAILED
exit /b 1
