@echo off
setlocal
cd /d C:\SwitchMap
echo PHASE73_2_VERIFY_REFRESH_VIEW
echo PROJECT=%CD%
if not exist venv\Scripts\python.exe (
  echo FAIL: venv python not found
  exit /b 1
)
venv\Scripts\python.exe tools\phase73_2_force_hide_refresh_view.py --verify
if errorlevel 1 exit /b 1
echo RUN=python manage.py check
venv\Scripts\python.exe manage.py check
if errorlevel 1 exit /b 1
echo PHASE73_2_VERIFY_REFRESH_VIEW_DONE
endlocal
