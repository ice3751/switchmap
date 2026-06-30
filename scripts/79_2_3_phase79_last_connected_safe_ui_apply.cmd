@echo off
setlocal
cd /d "%~dp0.."
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python tools\phase79_2_3_apply.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
python tools\phase79_2_3_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_2_3_APPLY_OK
