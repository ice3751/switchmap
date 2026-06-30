@echo off
setlocal
schtasks /End /TN "SwitchMap Waitress" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>&1
schtasks /Run /TN "SwitchMap Waitress"
timeout /t 5
netstat -ano | findstr ":8000"
if errorlevel 1 goto fail

echo PHASE39_WAITRESS_RESTART_OK
exit /b 0

:fail
echo PHASE39_WAITRESS_RESTART_FAILED
exit /b 1
