@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE90_4_BACKUP_UI_SAFE_REFINE_COMPREHENSIVE_START

echo.
echo ===== INSTALL / SAFE URL REPAIR =====
C:\SwitchMap\venv\Scripts\python.exe scripts\phase90_install.py
if errorlevel 1 (
  echo PHASE90_4_FAIL install_rolled_back
  exit /b 1
)

echo.
echo ===== DJANGO CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py check
if errorlevel 1 (
  echo PHASE90_4_FAIL django_check
  exit /b 1
)

echo.
echo ===== URL RESOLVE CHECK =====
C:\SwitchMap\venv\Scripts\python.exe manage.py shell -c "from django.urls import resolve, reverse; m=resolve('/backup-health/'); print('URL_RESOLVE', m.url_name, m.func.__module__); print('URL_REVERSE', reverse('inventory:backup_health_dashboard')); assert m.url_name == 'backup_health_dashboard'"
if errorlevel 1 (
  echo PHASE90_4_FAIL url_resolve_check
  exit /b 1
)

echo.
echo ===== VIEW HTTP CHECK WITH VALID HOST =====
C:\SwitchMap\venv\Scripts\python.exe manage.py shell -c "from django.test import Client; c=Client(HTTP_HOST='it-tools.winac-co.com'); r=c.get('/backup-health/'); print('URL /backup-health/', r.status_code); assert r.status_code in (200,302,403)"
if errorlevel 1 (
  echo PHASE90_4_FAIL url_http_check
  exit /b 1
)

echo.
echo ===== HEALTH REPORT =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_health_report
if errorlevel 1 (
  echo PHASE90_4_FAIL health_report
  exit /b 1
)

echo.
echo ===== RETENTION DRY RUN =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_retention_cleanup --keep 30
if errorlevel 1 (
  echo PHASE90_4_FAIL retention_dry_run
  exit /b 1
)

echo.
echo ===== PROJECT REFINE AUDIT + SAFE QUARANTINE =====
C:\SwitchMap\venv\Scripts\python.exe manage.py project_refine_audit --safe-cleanup --quarantine
if errorlevel 1 (
  echo PHASE90_4_FAIL project_refine_audit
  exit /b 1
)

echo.
echo ===== STORAGE VERIFY =====
C:\SwitchMap\venv\Scripts\python.exe manage.py backup_storage_verify --strict
if errorlevel 1 (
  echo PHASE90_4_FAIL storage_verify
  exit /b 1
)

echo.
echo ===== SCHEDULED BACKUP TASK STATUS =====
schtasks /Query /TN "SwitchMap Scheduled Backup Daily" /V /FO LIST

echo.
echo ===== RESTART WAITRESS =====
schtasks /End /TN "SwitchMap Waitress" >nul 2>nul
timeout /t 2 >nul
schtasks /Run /TN "SwitchMap Waitress"

echo PHASE90_4_BACKUP_UI_SAFE_REFINE_COMPREHENSIVE_OK
endlocal
