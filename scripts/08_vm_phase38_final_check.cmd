@echo off
setlocal
cd /d C:\SwitchMap

if not exist logs mkdir logs

echo ===== SwitchMap Phase 38 Final Check =====
echo Project: C:\SwitchMap
echo Time: %DATE% %TIME%
echo.

echo [1/7] Django check
venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1

echo.
echo [2/7] Production check
venv\Scripts\python.exe manage.py production_check
if errorlevel 1 exit /b 1

echo.
echo [3/7] SQLite backup test
venv\Scripts\python.exe manage.py backup_sqlite --check-only
if errorlevel 1 exit /b 1

echo.
echo [4/7] Existing smoke tests
venv\Scripts\python.exe smoke_tests\run_smoke.py current
if errorlevel 1 exit /b 1

echo.
echo [5/7] Phase 38 VM production smoke test
venv\Scripts\python.exe smoke_tests\switchmap_38_vm_production_smoke_test.py
if errorlevel 1 exit /b 1

echo.
echo [6/7] Scheduled tasks
schtasks /Query /TN "SwitchMap Waitress" /V /FO LIST
if errorlevel 1 exit /b 1
schtasks /Query /TN "SwitchMap SQLite Backup" /V /FO LIST
if errorlevel 1 exit /b 1

echo.
echo [7/7] Port 8000 listener
netstat -ano | findstr ":8000"
if errorlevel 1 exit /b 1

echo.
echo PHASE38_FINAL_CHECK_OK
endlocal
