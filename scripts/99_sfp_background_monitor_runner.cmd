@echo off
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs
call venv\Scripts\activate.bat
python manage.py sfp_background_monitor --quiet >> logs\sfp-background-monitor-run.log 2>&1
endlocal
