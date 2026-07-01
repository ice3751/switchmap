@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE78_2_FAIL manage.py not found.
  exit /b 1
)
if exist venv\Scripts\activate call venv\Scripts\activate
python manage.py check
if errorlevel 1 exit /b 1
python scripts\phase78_2_verify_alarm_badge_layout.py
if errorlevel 1 exit /b 1
echo PHASE78_2_VERIFY_OK
