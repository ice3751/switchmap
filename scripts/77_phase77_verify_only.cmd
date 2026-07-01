@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE77_FAIL manage.py not found
  exit /b 1
)
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python manage.py check
if errorlevel 1 exit /b 1
python manage.py phase77_stabilization_check
if errorlevel 1 exit /b 1
echo PHASE77_VERIFY_OK
endlocal
