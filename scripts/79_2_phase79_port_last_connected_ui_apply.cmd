@echo off
setlocal
cd /d C:\SwitchMap
if exist venv\Scripts\activate call venv\Scripts\activate
python tools\phase79_2_apply.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
python tools\phase79_2_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_2_APPLY_OK
