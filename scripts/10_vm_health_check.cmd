@echo off
setlocal
cd /d C:\SwitchMap

echo ===== SwitchMap VM Health Check =====
echo.
echo [1/7] Hostname
hostname

echo.
echo [2/7] IPv4
ipconfig | findstr /i "IPv4"

echo.
echo [3/7] Timezone
tzutil /g

echo.
echo [4/7] Django check
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\manage.py check
if errorlevel 1 goto fail

echo.
echo [5/7] Production check
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\manage.py production_check
if errorlevel 1 goto fail

echo.
echo [6/7] Scheduled tasks
schtasks /Query /TN "SwitchMap Waitress" /FO LIST | findstr /i "TaskName Status Last Result"
schtasks /Query /TN "SwitchMap SQLite Backup" /FO LIST | findstr /i "TaskName Status Last Result"

echo.
echo [7/7] Port 8000
netstat -ano | findstr ":8000"
if errorlevel 1 goto fail

echo.
echo PHASE39_HEALTH_OK
exit /b 0

:fail
echo.
echo PHASE39_HEALTH_FAILED
exit /b 1
