@echo off
setlocal
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python scripts\phase83R3_alarm_engine_v2_stabilize.py
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
endlocal
