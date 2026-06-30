@echo off
cd /d C:\SwitchMap
if not exist C:\SwitchMap\logs mkdir C:\SwitchMap\logs
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\manage.py dashboard_background_refresh --quiet >> C:\SwitchMap\logs\dashboard-background-refresh-task.log 2>&1
