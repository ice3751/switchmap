@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%" || exit /b 0
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs" >nul 2>nul
"%ROOT%\venv\Scripts\python.exe" manage.py poll_mikrotik_auto_snmp --quiet >> "%ROOT%\logs\mikrotik-auto-snmp.log" 2>&1
exit /b 0
