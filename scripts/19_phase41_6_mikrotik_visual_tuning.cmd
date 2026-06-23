@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1
venv\Scripts\python.exe switchmap_41_6_mikrotik_visual_smoke_test.py
if errorlevel 1 exit /b 1
venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 exit /b 1
schtasks /End /TN "SwitchMap Waitress" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>nul
schtasks /Run /TN "SwitchMap Waitress"
timeout /t 5 /nobreak >nul
netstat -ano | findstr ":8000"
echo PHASE41_6_APPLY_OK
