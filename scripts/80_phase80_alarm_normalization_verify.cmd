@echo off
setlocal
cd /d "%~dp0\.."

if not exist "venv\Scripts\python.exe" (
    echo PHASE80_FAIL missing venv\Scripts\python.exe
    exit /b 1
)
if not exist "manage.py" (
    echo PHASE80_FAIL missing manage.py
    exit /b 1
)

venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1

venv\Scripts\python.exe manage.py phase80_alarm_normalization_check
if errorlevel 1 exit /b 1

echo PHASE80_ALARM_NORMALIZATION_VERIFY_OK
