@echo off
setlocal
cd /d "%~dp0\.."

if not exist "venv\Scripts\python.exe" (
    echo PHASE79_0_FAIL missing venv\Scripts\python.exe
    exit /b 1
)
if not exist "manage.py" (
    echo PHASE79_0_FAIL missing manage.py
    exit /b 1
)
if not exist "tools\phase79_0_preflight_guard.py" (
    echo PHASE79_0_FAIL missing tools\phase79_0_preflight_guard.py
    exit /b 1
)

venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1

venv\Scripts\python.exe tools\phase79_0_preflight_guard.py
if errorlevel 1 exit /b 1

echo PHASE79_0_CMD_OK
