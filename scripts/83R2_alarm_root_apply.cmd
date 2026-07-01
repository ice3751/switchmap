@echo off
setlocal
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
python scripts\phase83R2_alarm_root_apply.py
endlocal
