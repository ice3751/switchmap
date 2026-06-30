@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE102_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE102_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase102_brand_icons_apply.py (
  echo PHASE102_FAIL missing_phase102_apply_tool
  exit /b 12
)
if not exist payload_phase102_brand_icons\inventory\static\inventory\brand\phase102\switchmap-app-icon.svg (
  echo PHASE102_FAIL missing_phase102_brand_assets
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE102_TS=%%I
set PHASE102_LOG=logs\phase102_brand_icons_%PHASE102_TS%.log

echo PHASE102_LOG=%PHASE102_LOG%
call :PHASE102_MAIN > "%PHASE102_LOG%" 2>&1
set PHASE102_RC=%ERRORLEVEL%

type "%PHASE102_LOG%"
echo PHASE102_LOG=%PHASE102_LOG%
echo PHASE102_EXIT=%PHASE102_RC%
exit /b %PHASE102_RC%

:PHASE102_MAIN
echo PHASE102_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase102_brand_icons_apply.py
set RC=%ERRORLEVEL%
echo PHASE102_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE102_CMD_OK
exit /b 0
