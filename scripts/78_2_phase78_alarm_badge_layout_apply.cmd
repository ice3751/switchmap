@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE78_2_FAIL manage.py not found. Extract package into C:\SwitchMap first.
  exit /b 1
)
if exist venv\Scripts\activate call venv\Scripts\activate
python scripts\phase78_2_patch_alarm_badge_layout.py
if errorlevel 1 exit /b 1
python -m py_compile scripts\phase78_2_patch_alarm_badge_layout.py scripts\phase78_2_verify_alarm_badge_layout.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput --verbosity 0
if errorlevel 1 exit /b 1
python scripts\phase78_2_verify_alarm_badge_layout.py
if errorlevel 1 exit /b 1
echo PHASE78_2_APPLY_OK
