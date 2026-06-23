@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv" (
  py -3 -m venv venv
  if errorlevel 1 exit /b 1
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python scripts\make_vm_env.py
if errorlevel 1 exit /b 1
python manage.py migrate
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py backup_sqlite --check-only
if errorlevel 1 exit /b 1
python manage.py production_check
if errorlevel 1 exit /b 1
endlocal
