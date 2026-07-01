@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE88_3_RB5009_FULL_BACKUP_SCHEDULE_UPDATE_START

if not exist C:\SwitchMap\venv\Scripts\python.exe (
  echo FAIL missing python venv
  exit /b 1
)

if not exist C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py (
  echo FAIL missing scheduled runner
  exit /b 1
)

mkdir C:\SwitchMap\logs 2>nul

echo.
echo ===== DJANGO CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py check
if errorlevel 1 (
  echo PHASE88_3_FAIL django_check
  exit /b 1
)

echo.
echo ===== PY COMPILE =====
C:\SwitchMap\venv\Scripts\python.exe -m py_compile C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.py
if errorlevel 1 (
  echo PHASE88_3_FAIL py_compile
  exit /b 1
)

echo.
echo ===== STORAGE VERIFY BEFORE =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_storage_verify --strict
if errorlevel 1 (
  echo PHASE88_3_FAIL storage_verify_before
  exit /b 1
)

echo.
echo ===== CREATE SCHEDULED TASK =====
schtasks /Delete /TN "SwitchMap Scheduled Backup Daily" /F >nul 2>nul
schtasks /Create /F /TN "SwitchMap Scheduled Backup Daily" /SC DAILY /ST 23:30 /RL HIGHEST /TR "cmd.exe /d /c C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.cmd"
if errorlevel 1 (
  echo PHASE88_3_FAIL schtasks_create
  exit /b 1
)

echo.
echo ===== TASK STATUS =====
schtasks /Query /TN "SwitchMap Scheduled Backup Daily" /V /FO LIST

echo.
echo PHASE88_3_RB5009_FULL_BACKUP_SCHEDULE_UPDATE_OK
echo Coverage now configured:
echo Cisco IDs: 7,1,2,3,4,5,6 running-config + startup-config
echo MikroTik export IDs: 18,19
echo MikroTik full-backup IDs: 18,19
endlocal
