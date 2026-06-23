@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE41_5_APPLY_START

if not exist venv\Scripts\python.exe (
  echo ERROR: venv python not found
  exit /b 1
)

venv\Scripts\python.exe patches\phase41_5_admin_large_form_final_fix.py
if errorlevel 1 exit /b 1

venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1

venv\Scripts\python.exe -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import django; django.setup(); from django.conf import settings; print('DATA_UPLOAD_MAX_NUMBER_FIELDS=' + str(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS)); assert settings.DATA_UPLOAD_MAX_NUMBER_FIELDS >= 20000"
if errorlevel 1 exit /b 1

venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 exit /b 1

schtasks /End /TN "SwitchMap Waitress" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>nul
schtasks /Run /TN "SwitchMap Waitress"
timeout /t 5 /nobreak >nul
netstat -ano | findstr ":8000"

echo PHASE41_5_APPLY_OK
endlocal
