@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE87_1_SCHEDULED_BACKUP_RUNNER_FIX_START

if not exist C:\SwitchMap\venv\Scripts\python.exe (
  echo FAIL missing python venv: C:\SwitchMap\venv\Scripts\python.exe
  exit /b 1
)

if not exist C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py (
  echo FAIL missing runner: C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py
  exit /b 1
)

mkdir C:\SwitchMap\logs 2>nul

echo.
echo ===== PY COMPILE =====
C:\SwitchMap\venv\Scripts\python.exe -m py_compile C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py
if errorlevel 1 (
  echo PHASE87_1_FAIL py_compile
  exit /b 1
)

echo.
echo ===== DIRECT RUNNER TEST =====
del C:\SwitchMap\logs\scheduled_backup_daily.log 2>nul
C:\SwitchMap\venv\Scripts\python.exe C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py
set DIRECT_EXIT=%ERRORLEVEL%
type C:\SwitchMap\logs\scheduled_backup_daily.log
if not "%DIRECT_EXIT%"=="0" (
  echo PHASE87_1_FAIL direct_runner_exit=%DIRECT_EXIT%
  exit /b %DIRECT_EXIT%
)

echo.
echo ===== CREATE SCHEDULED TASK =====
schtasks /Delete /TN "SwitchMap Scheduled Backup Daily" /F >nul 2>nul
schtasks /Create /F /TN "SwitchMap Scheduled Backup Daily" /SC DAILY /ST 23:30 /RL HIGHEST /TR "cmd.exe /d /c C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.cmd"
if errorlevel 1 (
  echo PHASE87_1_FAIL schtasks_create
  exit /b 1
)

echo.
echo ===== RUN TASK TEST =====
del C:\SwitchMap\logs\scheduled_backup_daily.log 2>nul
schtasks /Run /TN "SwitchMap Scheduled Backup Daily"
if errorlevel 1 (
  echo PHASE87_1_FAIL schtasks_run
  exit /b 1
)

ping 127.0.0.1 -n 90 >nul

echo.
echo ===== TASK LOG =====
type C:\SwitchMap\logs\scheduled_backup_daily.log

echo.
echo ===== TASK STATUS =====
schtasks /Query /TN "SwitchMap Scheduled Backup Daily" /V /FO LIST

findstr /C:"FINAL_EXIT=0" C:\SwitchMap\logs\scheduled_backup_daily.log >nul
if errorlevel 1 (
  echo PHASE87_1_FAIL missing_FINAL_EXIT_0
  exit /b 1
)

echo PHASE87_1_SCHEDULED_BACKUP_RUNNER_FIX_OK
endlocal
