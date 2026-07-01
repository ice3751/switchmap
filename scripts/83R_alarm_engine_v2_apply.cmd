@echo off
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python manage.py migrate
python scripts\phase83R_alarm_engine_v2_apply.py
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
