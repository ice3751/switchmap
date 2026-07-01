@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_ROOT=C:\SwitchMap"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PATCH_ROOT=%%~fI"
set "PAYLOAD_ROOT=%PATCH_ROOT%\payload"
set "PY=%PROJECT_ROOT%\venv\Scripts\python.exe"
set "TASK_NAME=SwitchMap Waitress"

if not exist "%PROJECT_ROOT%\manage.py" (
  echo PHASE104R1_FAIL project_root_not_found:%PROJECT_ROOT%
  exit /b 10
)
if not exist "%PAYLOAD_ROOT%\inventory\views.py" (
  echo PHASE104R1_FAIL payload_missing:%PAYLOAD_ROOT%
  exit /b 11
)
if not exist "%PY%" (
  echo PHASE104R1_FAIL python_not_found:%PY%
  exit /b 12
)

for /f %%T in ('"%PY%" -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set "TS=%%T"
set "BACKUP_DIR=%PROJECT_ROOT%\backups\phase104R1_dashboard_performance_stabilization_reviewed_fix_%TS%"
set "LOG=%PROJECT_ROOT%\logs\phase104R1_dashboard_performance_stabilization_reviewed_fix_apply_%TS%.log"

if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs" >nul 2>nul
call :main > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
exit /b %RC%

:main
echo PHASE104R1_DASHBOARD_PERFORMANCE_STABILIZATION_APPLY_START
echo PROJECT_ROOT=%PROJECT_ROOT%
echo PATCH_ROOT=%PATCH_ROOT%
echo BACKUP_DIR=%BACKUP_DIR%
echo LOG=%LOG%
echo RUN_CMD=schtasks /Query /TN "%TASK_NAME%"
schtasks /Query /TN "%TASK_NAME%" >nul 2>nul
if errorlevel 1 (
  echo PHASE104R1_FAIL scheduled_task_missing:%TASK_NAME%
  exit /b 13
)

mkdir "%BACKUP_DIR%" || exit /b 14
call :backup_one "inventory\views.py" || exit /b 15
call :backup_one "inventory\management\commands\phase104R1_dashboard_performance_stabilization_reviewed_fix_check.py" || exit /b 16

call :apply_one "inventory\views.py" || goto rollback_fail
call :apply_one "inventory\management\commands\phase104R1_dashboard_performance_stabilization_reviewed_fix_check.py" || goto rollback_fail

echo RUN=%PY% -m py_compile inventory/views.py inventory/management/commands/phase104R1_dashboard_performance_stabilization_reviewed_fix_check.py
cd /d "%PROJECT_ROOT%" && "%PY%" -m py_compile inventory/views.py inventory/management/commands/phase104R1_dashboard_performance_stabilization_reviewed_fix_check.py || goto rollback_fail

echo RUN=%PY% manage.py check
cd /d "%PROJECT_ROOT%" && "%PY%" manage.py check || goto rollback_fail

echo RUN=%PY% manage.py makemigrations --check --dry-run
cd /d "%PROJECT_ROOT%" && "%PY%" manage.py makemigrations --check --dry-run || goto rollback_fail

echo RUN=%PY% manage.py phase104R1_dashboard_performance_stabilization_reviewed_fix_check --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_check_%TS%.json
cd /d "%PROJECT_ROOT%" && "%PY%" manage.py phase104R1_dashboard_performance_stabilization_reviewed_fix_check --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_check_%TS%.json || goto rollback_fail

echo RUN=%PY% smoke_tests/run_smoke.py --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_smoke_%TS%.json
cd /d "%PROJECT_ROOT%" && "%PY%" smoke_tests/run_smoke.py --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_smoke_%TS%.json || goto rollback_fail

echo RUN=%PY% manage.py phase98_100_final_release_lock_check --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_release_lock_%TS%.json
cd /d "%PROJECT_ROOT%" && "%PY%" manage.py phase98_100_final_release_lock_check --strict --output logs/phase104R1_dashboard_performance_stabilization_reviewed_fix_release_lock_%TS%.json || goto rollback_fail

echo SERVICE_RESTART_START_AFTER_VERIFY_OK
echo RUN_CMD=schtasks /End /TN "%TASK_NAME%"
schtasks /End /TN "%TASK_NAME%" >nul 2>nul
echo RUN_CMD=cmd /c ping -n 3 127.0.0.1 ^>nul
cmd /c ping -n 3 127.0.0.1 >nul
echo RUN_CMD=schtasks /Run /TN "%TASK_NAME%"
schtasks /Run /TN "%TASK_NAME%" || goto rollback_fail
echo SERVICE_RESTART_DONE

echo FINAL_FAIL_COUNT=0
echo FINAL_WARNING_COUNT=0
echo DB_MUTATION=NO
echo MIGRATION_WRITE=NO
echo RESTORE_ENABLE_CHANGE=NO
echo SSH_EXECUTION=NO
echo OPERATIONAL_BACKUP_WRITE=NO
echo VISIBLE_TEST_DATA_CREATED=NO
echo PHASE104R1_APPLY_OK
echo APPLY_LOG=%LOG%
exit /b 0

:rollback_fail
echo PHASE104R1_VERIFY_OR_APPLY_FAILED_ROLLBACK_START
call :rollback_one "inventory\views.py"
call :rollback_one "inventory\management\commands\phase104R1_dashboard_performance_stabilization_reviewed_fix_check.py"
echo RUN=%PY% manage.py check AFTER_ROLLBACK
cd /d "%PROJECT_ROOT%" && "%PY%" manage.py check
if errorlevel 1 echo PHASE104R1_ROLLBACK_CHECK_WARNING
if errorlevel 1 exit /b 90
echo ROLLBACK_DONE
exit /b 80

:backup_one
set "REL=%~1"
set "SRC=%PROJECT_ROOT%\%REL%"
set "DST=%BACKUP_DIR%\%REL%"
for %%D in ("%DST%") do if not exist "%%~dpD" mkdir "%%~dpD" >nul 2>nul
if exist "%SRC%" (
  copy /Y "%SRC%" "%DST%" >nul || exit /b 1
  echo BACKUP_FILE=%REL%
) else (
  echo MISSING_BEFORE_APPLY>%DST%.missing
  echo BACKUP_FILE_MISSING=%REL%
)
exit /b 0

:apply_one
set "REL=%~1"
set "SRC=%PAYLOAD_ROOT%\%REL%"
set "DST=%PROJECT_ROOT%\%REL%"
if not exist "%SRC%" (
  echo PHASE104R1_FAIL payload_file_missing:%REL%
  exit /b 1
)
for %%D in ("%DST%") do if not exist "%%~dpD" mkdir "%%~dpD" >nul 2>nul
copy /Y "%SRC%" "%DST%" >nul || exit /b 1
echo APPLIED_FILE=%REL%
exit /b 0

:rollback_one
set "REL=%~1"
set "SRC=%BACKUP_DIR%\%REL%"
set "DST=%PROJECT_ROOT%\%REL%"
if exist "%SRC%.missing" (
  if exist "%DST%" del /F /Q "%DST%" >nul 2>nul
  echo ROLLBACK_REMOVED_NEW_FILE=%REL%
  exit /b 0
)
if exist "%SRC%" (
  copy /Y "%SRC%" "%DST%" >nul
  echo ROLLBACK_FILE=%REL%
)
exit /b 0
