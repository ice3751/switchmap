@echo off
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check || exit /b 1
python manage.py shell -c "from django.test import Client; c=Client(HTTP_HOST='it-tools.winac-co.com:8000'); paths=['/','/alarms/','/alarms/rules/','/topology/']; [print(p, c.get(p).status_code) for p in paths]" || exit /b 1
