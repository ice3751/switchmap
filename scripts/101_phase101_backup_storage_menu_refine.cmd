@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE101_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE101_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase101_backup_storage_menu_refine_apply.py (
  echo PHASE101_FAIL missing_phase101_apply_tool
  exit /b 12
)
if not exist payload_phase101_backup_storage_menu_refine\inventory\templates\inventory\backup_storage_status.html (
  echo PHASE101_FAIL missing_phase101_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE101_TS=%%I
set PHASE101_LOG=logs\phase101_backup_storage_menu_refine_%PHASE101_TS%.log

echo PHASE101_LOG=%PHASE101_LOG%
call :PHASE101_MAIN > "%PHASE101_LOG%" 2>&1
set PHASE101_RC=%ERRORLEVEL%

type "%PHASE101_LOG%"
echo PHASE101_LOG=%PHASE101_LOG%
echo PHASE101_EXIT=%PHASE101_RC%
exit /b %PHASE101_RC%

:PHASE101_MAIN
echo PHASE101_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase101_backup_storage_menu_refine_apply.py
set RC=%ERRORLEVEL%
echo PHASE101_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE101_CMD_OK
exit /b 0
