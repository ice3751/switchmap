@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE93_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE93_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase93_performance_safe_refine_apply.py (
  echo PHASE93_FAIL missing_phase93_apply_tool
  exit /b 12
)
if not exist payload_phase93_performance_safe_refine\inventory\context_processors.py (
  echo PHASE93_FAIL missing_phase93_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE93_TS=%%I
set PHASE93_LOG=logs\phase93_performance_safe_refine_%PHASE93_TS%.log

echo PHASE93_LOG=%PHASE93_LOG%
call :PHASE93_MAIN > "%PHASE93_LOG%" 2>&1
set PHASE93_RC=%ERRORLEVEL%

type "%PHASE93_LOG%"
echo PHASE93_LOG=%PHASE93_LOG%
echo PHASE93_EXIT=%PHASE93_RC%
exit /b %PHASE93_RC%

:PHASE93_MAIN
echo PHASE93_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase93_performance_safe_refine_apply.py
set RC=%ERRORLEVEL%
echo PHASE93_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE93_CMD_OK
exit /b 0
