@echo off
setlocal
cd /d C:\SwitchMap
if exist venv\Scripts\activate call venv\Scripts\activate
python tools\phase79_1_apply.py
if errorlevel 1 exit /b 1
python manage.py migrate
if errorlevel 1 exit /b 1
python manage.py phase79_capture_port_history --source phase79_1_initial
if errorlevel 1 exit /b 1
python tools\phase79_1_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_1_APPLY_OK
