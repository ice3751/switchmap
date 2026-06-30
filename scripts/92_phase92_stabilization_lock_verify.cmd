@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE92_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE92_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase92_stabilization_lock_verify.py (
  echo PHASE92_FAIL missing_phase92_python_tool
  exit /b 12
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE92_TS=%%I
set PHASE92_LOG=logs\phase92r2_stabilization_lock_verify_%PHASE92_TS%.log

echo PHASE92_LOG=%PHASE92_LOG%
call :PHASE92_MAIN > "%PHASE92_LOG%" 2>&1
set PHASE92_RC=%ERRORLEVEL%

type "%PHASE92_LOG%"
echo PHASE92_LOG=%PHASE92_LOG%
echo PHASE92_EXIT=%PHASE92_RC%
exit /b %PHASE92_RC%

:PHASE92_MAIN
echo PHASE92R2_STABILIZATION_LOCK_VERIFY_START
echo ROOT=C:\SwitchMap
echo MODE=read_only_no_restart_no_restore_no_ssh
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase92_stabilization_lock_verify.py
set RC=%ERRORLEVEL%
echo PHASE92_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE92R2_STABILIZATION_LOCK_VERIFY_OK
exit /b 0
