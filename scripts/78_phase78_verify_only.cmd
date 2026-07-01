@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE78_FAIL manage.py not found.
  exit /b 1
)
if exist venv\Scripts\activate call venv\Scripts\activate
python manage.py check
if errorlevel 1 exit /b 1
python manage.py phase78_alarm_cleanup_report --verify
if errorlevel 1 exit /b 1
echo PHASE78_VERIFY_OK
