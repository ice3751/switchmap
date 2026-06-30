@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE103_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE103_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase103_dashboard_cards_refine_apply.py (
  echo PHASE103_FAIL missing_phase103_apply_tool
  exit /b 12
)
if not exist payload_phase103_dashboard_cards_refine\inventory\static\inventory\css\switchmap-phase103-dashboard-cards.css (
  echo PHASE103_FAIL missing_phase103_payload_css
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE103_TS=%%I
set PHASE103_LOG=logs\phase103_dashboard_cards_refine_%PHASE103_TS%.log

echo PHASE103_LOG=%PHASE103_LOG%
call :PHASE103_MAIN > "%PHASE103_LOG%" 2>&1
set PHASE103_RC=%ERRORLEVEL%

type "%PHASE103_LOG%"
echo PHASE103_LOG=%PHASE103_LOG%
echo PHASE103_EXIT=%PHASE103_RC%
exit /b %PHASE103_RC%

:PHASE103_MAIN
echo PHASE103R8_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase103_dashboard_cards_refine_apply.py
set RC=%ERRORLEVEL%
echo PHASE103_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE103_CMD_OK
exit /b 0
