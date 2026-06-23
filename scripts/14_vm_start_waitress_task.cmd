@echo off
setlocal
schtasks /Run /TN "SwitchMap Waitress"
timeout /t 5
netstat -ano | findstr ":8000"
if errorlevel 1 goto fail

echo PHASE39_WAITRESS_START_OK
exit /b 0

:fail
echo PHASE39_WAITRESS_START_FAILED
exit /b 1
