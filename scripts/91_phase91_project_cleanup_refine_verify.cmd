@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE91_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE91_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase91_project_cleanup_refine_verify.py (
  echo PHASE91_FAIL missing_phase91_python_tool
  exit /b 12
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE91_TS=%%I
set PHASE91_LOG=logs\phase91_project_cleanup_refine_verify_%PHASE91_TS%.log

echo PHASE91_LOG=%PHASE91_LOG%
call :PHASE91_MAIN > "%PHASE91_LOG%" 2>&1
set PHASE91_RC=%ERRORLEVEL%

type "%PHASE91_LOG%"
echo PHASE91_LOG=%PHASE91_LOG%
echo PHASE91_EXIT=%PHASE91_RC%
exit /b %PHASE91_RC%

:PHASE91_MAIN
echo PHASE91_PROJECT_CLEANUP_REFINE_FINAL_VERIFY_START
echo ROOT=C:\SwitchMap
echo TASK_WAITRESS=SwitchMap Waitress
echo TASK_BACKUP=SwitchMap Scheduled Backup Daily
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase91_project_cleanup_refine_verify.py
set RC=%ERRORLEVEL%
echo PHASE91_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE91_PROJECT_CLEANUP_REFINE_FINAL_VERIFY_OK
exit /b 0
