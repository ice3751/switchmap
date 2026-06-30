@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE94_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE94_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase94_verification_baseline_apply.py (
  echo PHASE94_FAIL missing_phase94_apply_tool
  exit /b 12
)
if not exist payload_phase94_verification_baseline\smoke_tests\run_smoke.py (
  echo PHASE94_FAIL missing_phase94_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE94_TS=%%I
set PHASE94_LOG=logs\phase94_verification_baseline_%PHASE94_TS%.log

echo PHASE94_LOG=%PHASE94_LOG%
call :PHASE94_MAIN > "%PHASE94_LOG%" 2>&1
set PHASE94_RC=%ERRORLEVEL%

type "%PHASE94_LOG%"
echo PHASE94_LOG=%PHASE94_LOG%
echo PHASE94_EXIT=%PHASE94_RC%
exit /b %PHASE94_RC%

:PHASE94_MAIN
echo PHASE94_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase94_verification_baseline_apply.py
set RC=%ERRORLEVEL%
echo PHASE94_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE94_CMD_OK
exit /b 0
