@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE78_FAIL manage.py not found. Extract package into C:\SwitchMap first.
  exit /b 1
)
if exist venv\Scripts\activate call venv\Scripts\activate
python scripts\phase78_patch_urls_base.py
if errorlevel 1 exit /b 1
python -m py_compile inventory\phase78_views.py inventory\management\commands\phase78_alarm_cleanup_report.py scripts\phase78_patch_urls_base.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput --verbosity 0
if errorlevel 1 exit /b 1
python manage.py phase78_alarm_cleanup_report
if errorlevel 1 exit /b 1
echo PHASE78_APPLY_OK
