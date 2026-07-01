@echo off
setlocal
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python scripts\phase83R5_single_alarm_writer_and_port_error_fix.py
python manage.py check
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress"
endlocal
