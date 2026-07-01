@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE95_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE95_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase95_packaging_dependency_safety_apply.py (
  echo PHASE95_FAIL missing_phase95_apply_tool
  exit /b 12
)
if not exist payload_phase95_packaging_dependency_safety\requirements.txt (
  echo PHASE95_FAIL missing_phase95_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE95_TS=%%I
set PHASE95_LOG=logs\phase95_packaging_dependency_safety_%PHASE95_TS%.log

echo PHASE95_LOG=%PHASE95_LOG%
call :PHASE95_MAIN > "%PHASE95_LOG%" 2>&1
set PHASE95_RC=%ERRORLEVEL%

type "%PHASE95_LOG%"
echo PHASE95_LOG=%PHASE95_LOG%
echo PHASE95_EXIT=%PHASE95_RC%
exit /b %PHASE95_RC%

:PHASE95_MAIN
echo PHASE95_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase95_packaging_dependency_safety_apply.py
set RC=%ERRORLEVEL%
echo PHASE95_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE95_CMD_OK
exit /b 0
