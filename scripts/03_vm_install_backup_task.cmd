@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo VENV_NOT_FOUND
  exit /b 1
)
schtasks /Create /TN "SwitchMap SQLite Backup" /SC DAILY /ST 23:30 /TR "\"%CD%\venv\Scripts\python.exe\" \"%CD%\manage.py\" backup_sqlite" /F
endlocal
