@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE89_BACKUP_HEALTH_RETENTION_AUTOSCHEDULE_START

if not exist C:\SwitchMap\venv\Scripts\python.exe (
  echo FAIL missing python venv
  exit /b 1
)

mkdir C:\SwitchMap\logs 2>nul

echo.
echo ===== DJANGO CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py check
if errorlevel 1 (
  echo PHASE89_FAIL django_check
  exit /b 1
)

echo.
echo ===== PY COMPILE =====
C:\SwitchMap\venv\Scripts\python.exe -m py_compile ^
 inventory\backup_schedule_policy.py ^
 inventory\management\commands\backup_schedule_policy.py ^
 inventory\management\commands\scheduled_backup_dynamic.py ^
 inventory\management\commands\backup_health_report.py ^
 inventory\management\commands\backup_retention_cleanup.py ^
 scripts\switchmap_scheduled_backup_daily.py
if errorlevel 1 (
  echo PHASE89_FAIL py_compile
  exit /b 1
)

echo.
echo ===== INIT POLICY =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_schedule_policy --init-defaults --show
if errorlevel 1 (
  echo PHASE89_FAIL policy_init
  exit /b 1
)

echo.
echo ===== DYNAMIC SCHEDULE DRY RUN =====
C:\SwitchMap\venv\Scripts\python.exe manage.py scheduled_backup_dynamic --dry-run
if errorlevel 1 (
  echo PHASE89_FAIL dynamic_dry_run
  exit /b 1
)

echo.
echo ===== HEALTH REPORT =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_health_report
if errorlevel 1 (
  echo PHASE89_WARNING health_report_has_issue
)

echo.
echo ===== RETENTION DRY RUN =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_retention_cleanup --keep 30 --sample 15
if errorlevel 1 (
  echo PHASE89_FAIL retention_dry_run
  exit /b 1
)

echo.
echo ===== STORAGE VERIFY =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_storage_verify --strict
if errorlevel 1 (
  echo PHASE89_FAIL storage_verify
  exit /b 1
)

echo.
echo ===== CREATE DAILY TASK =====
schtasks /Delete /TN "SwitchMap Scheduled Backup Daily" /F >nul 2>nul
schtasks /Create /F /TN "SwitchMap Scheduled Backup Daily" /SC DAILY /ST 23:30 /RL HIGHEST /TR "cmd.exe /d /c C:\SwitchMap\scripts\switchmap_scheduled_backup_daily.cmd"
if errorlevel 1 (
  echo PHASE89_FAIL schtasks_create
  exit /b 1
)

echo.
echo ===== TASK STATUS =====
schtasks /Query /TN "SwitchMap Scheduled Backup Daily" /V /FO LIST

echo.
echo PHASE89_BACKUP_HEALTH_RETENTION_AUTOSCHEDULE_OK
echo Dynamic auto-include is enabled via C:\SwitchMapData\backups\metadata\backup_schedule_policy.json
echo New Cisco devices: auto included for running-config/startup-config unless policy excluded.
echo New MikroTik devices: auto included for export unless policy excluded.
echo MikroTik full-backup: only IDs listed in policy full_backup_ids.
endlocal
