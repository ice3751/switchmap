@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo VENV_NOT_FOUND
  exit /b 1
)
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py production_check
if errorlevel 1 exit /b 1
echo STATIC_WAITRESS_FIX_OK
endlocal
