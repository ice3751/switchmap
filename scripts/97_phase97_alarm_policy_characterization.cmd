@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE97_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE97_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase97_alarm_policy_characterization_apply.py (
  echo PHASE97_FAIL missing_phase97_apply_tool
  exit /b 12
)
if not exist payload_phase97_alarm_policy_characterization\inventory\management\commands\phase97_alarm_policy_characterization_check.py (
  echo PHASE97_FAIL missing_phase97_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE97_TS=%%I
set PHASE97_LOG=logs\phase97_alarm_policy_characterization_%PHASE97_TS%.log

echo PHASE97_LOG=%PHASE97_LOG%
call :PHASE97_MAIN > "%PHASE97_LOG%" 2>&1
set PHASE97_RC=%ERRORLEVEL%

type "%PHASE97_LOG%"
echo PHASE97_LOG=%PHASE97_LOG%
echo PHASE97_EXIT=%PHASE97_RC%
exit /b %PHASE97_RC%

:PHASE97_MAIN
echo PHASE97_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase97_alarm_policy_characterization_apply.py
set RC=%ERRORLEVEL%
echo PHASE97_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE97_CMD_OK
exit /b 0
