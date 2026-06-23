@echo off
setlocal
schtasks /End /TN "SwitchMap Waitress" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>&1
netstat -ano | findstr ":8000"
if not errorlevel 1 goto fail

echo PHASE39_WAITRESS_STOP_OK
exit /b 0

:fail
echo PHASE39_WAITRESS_STOP_FAILED
exit /b 1
