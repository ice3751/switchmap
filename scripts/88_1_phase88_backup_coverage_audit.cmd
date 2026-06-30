@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE88_1_BACKUP_COVERAGE_AUDIT_REVIEWED_START

if not exist C:\SwitchMap\venv\Scripts\python.exe (
  echo PHASE88_1_FAIL missing venv python
  exit /b 1
)

mkdir C:\SwitchMap\logs 2>nul

echo.
echo ===== DJANGO CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py check
if errorlevel 1 (
  echo PHASE88_1_FAIL django_check
  exit /b 1
)

echo.
echo ===== PY COMPILE =====
C:\SwitchMap\venv\Scripts\python.exe -m py_compile inventory\management\commands\backup_coverage_audit.py
if errorlevel 1 (
  echo PHASE88_1_FAIL py_compile
  exit /b 1
)

echo.
echo ===== CREDENTIAL CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py scheduled_backup_credential_check --profile all --strict
if errorlevel 1 (
  echo PHASE88_1_FAIL credential_check
  exit /b 1
)

echo.
echo ===== CANDIDATE INVENTORY =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_coverage_audit --profile all --candidate-only
if errorlevel 1 (
  echo PHASE88_1_FAIL candidate_inventory
  exit /b 1
)

echo.
echo ===== COVERAGE AUDIT =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_coverage_audit --profile all
if errorlevel 1 (
  echo PHASE88_1_FAIL coverage_audit
  exit /b 1
)

echo.
echo ===== STORAGE VERIFY =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_storage_verify --strict
if errorlevel 1 (
  echo PHASE88_1_FAIL storage_verify
  exit /b 1
)

echo PHASE88_1_BACKUP_COVERAGE_AUDIT_REVIEWED_OK
endlocal
