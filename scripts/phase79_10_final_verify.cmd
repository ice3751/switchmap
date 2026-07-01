@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\SwitchMap
call venv\Scripts\activate
python manage.py check
if errorlevel 1 exit /b 1
python manage.py collectstatic --noinput -v 0
if errorlevel 1 exit /b 1
python tools\phase79_10_final_verify.py > phase79_10_final_verify_report.txt 2>&1
set VERIFY_RC=%ERRORLEVEL%
type phase79_10_final_verify_report.txt
exit /b %VERIFY_RC%
