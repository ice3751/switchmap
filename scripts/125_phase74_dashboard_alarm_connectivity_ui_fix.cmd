@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe tools\phase74_dashboard_alarm_connectivity_ui_fix.py
exit /b %ERRORLEVEL%
