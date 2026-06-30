@echo off
setlocal
cd /d C:\SwitchMap
if not exist logs mkdir logs
set REPORT=C:\SwitchMap\logs\phase38-final-report.txt

echo SwitchMap Phase 38 Final Report > "%REPORT%"
echo Time: %DATE% %TIME% >> "%REPORT%"
echo. >> "%REPORT%"

echo ===== hostname ===== >> "%REPORT%"
hostname >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== ipconfig IPv4 ===== >> "%REPORT%"
ipconfig | findstr /i "IPv4" >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== timezone ===== >> "%REPORT%"
tzutil /g >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== django check ===== >> "%REPORT%"
venv\Scripts\python.exe manage.py check >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== production check ===== >> "%REPORT%"
venv\Scripts\python.exe manage.py production_check >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== smoke current ===== >> "%REPORT%"
venv\Scripts\python.exe smoke_tests\run_smoke.py current >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== phase38 smoke ===== >> "%REPORT%"
venv\Scripts\python.exe smoke_tests\switchmap_38_vm_production_smoke_test.py >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== tasks ===== >> "%REPORT%"
schtasks /Query /TN "SwitchMap Waitress" /V /FO LIST >> "%REPORT%" 2>&1
schtasks /Query /TN "SwitchMap SQLite Backup" /V /FO LIST >> "%REPORT%" 2>&1

echo. >> "%REPORT%"
echo ===== port 8000 ===== >> "%REPORT%"
netstat -ano | findstr ":8000" >> "%REPORT%" 2>&1

echo REPORT_OK %REPORT%
endlocal
