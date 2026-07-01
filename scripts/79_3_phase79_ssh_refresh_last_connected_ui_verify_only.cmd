@echo off
setlocal
cd /d "%~dp0.."
python manage.py check
if errorlevel 1 exit /b 1
python tools\phase79_3_ssh_refresh_last_connected_ui_verify.py
endlocal
