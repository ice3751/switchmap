@echo off
setlocal
cd /d C:\SwitchMap
python manage.py check
if errorlevel 1 exit /b 1
python tools\phase79_6_1_last_connected_actual_reset.py
exit /b %errorlevel%
