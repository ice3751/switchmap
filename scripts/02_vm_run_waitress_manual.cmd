@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo VENV_NOT_FOUND
  exit /b 1
)
call venv\Scripts\activate.bat
python run_waitress.py
endlocal
