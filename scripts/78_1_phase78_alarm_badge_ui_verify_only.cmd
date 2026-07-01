@echo off
setlocal
cd /d "%~dp0\.."
if not exist "venv\Scripts\activate.bat" (
  echo PHASE78_1_FAIL missing venv\Scripts\activate.bat
  exit /b 1
)
call "venv\Scripts\activate.bat"
python manage.py check
if errorlevel 1 exit /b 1
python scripts\phase78_1_verify_alarm_badge_ui.py
if errorlevel 1 exit /b 1
echo PHASE78_1_VERIFY_ONLY_OK
