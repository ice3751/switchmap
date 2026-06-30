@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo VENV_NOT_FOUND
  exit /b 1
)
venv\Scripts\python.exe scripts\create_vm_deploy_zip.py
endlocal
