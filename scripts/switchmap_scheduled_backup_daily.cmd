@echo off
cd /d C:\SwitchMap
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py
exit /b %ERRORLEVEL%
