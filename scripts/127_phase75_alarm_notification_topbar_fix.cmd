@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe tools\phase75_alarm_notification_topbar_fix.py
exit /b %ERRORLEVEL%
