@echo off
setlocal
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python scripts\phase81_83_verify.py
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
endlocal
