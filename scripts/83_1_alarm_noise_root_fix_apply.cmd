@echo off
setlocal
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python scripts\phase83_1_alarm_noise_apply.py
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
endlocal
