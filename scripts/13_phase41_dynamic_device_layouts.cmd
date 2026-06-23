@echo off
setlocal
cd /d C:\SwitchMap
if not exist venv\Scripts\python.exe (
  echo PYTHON_VENV_NOT_FOUND
  exit /b 1
)
venv\Scripts\python.exe manage.py seed_mikrotik_devices
if errorlevel 1 exit /b 1
venv\Scripts\python.exe manage.py apply_dynamic_device_layouts
if errorlevel 1 exit /b 1
venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1
venv\Scripts\python.exe smoke_tests\run_smoke.py current
if errorlevel 1 exit /b 1
venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
schtasks /End /TN "SwitchMap Waitress" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>nul
schtasks /Run /TN "SwitchMap Waitress" >nul 2>nul
timeout /t 5 >nul
netstat -ano | findstr ":8000"
echo PHASE41_APPLY_OK
