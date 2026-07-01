@echo off
setlocal EnableExtensions

cd /d C:\SwitchMap
if errorlevel 1 (
  echo PHASE96_FAIL cannot_cd_to_C:\SwitchMap
  exit /b 10
)

if not exist logs mkdir logs
if not exist venv\Scripts\python.exe (
  echo PHASE96_FAIL missing_venv_python
  exit /b 11
)
if not exist scripts\phase96_model_index_metadata_alignment_apply.py (
  echo PHASE96_FAIL missing_phase96_apply_tool
  exit /b 12
)
if not exist payload_phase96_model_index_metadata_alignment\inventory\models.py (
  echo PHASE96_FAIL missing_phase96_payload
  exit /b 13
)

for /f %%I in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set PHASE96_TS=%%I
set PHASE96_LOG=logs\phase96_model_index_metadata_alignment_%PHASE96_TS%.log

echo PHASE96_LOG=%PHASE96_LOG%
call :PHASE96_MAIN > "%PHASE96_LOG%" 2>&1
set PHASE96_RC=%ERRORLEVEL%

type "%PHASE96_LOG%"
echo PHASE96_LOG=%PHASE96_LOG%
echo PHASE96_EXIT=%PHASE96_RC%
exit /b %PHASE96_RC%

:PHASE96_MAIN
echo PHASE96_CMD_START
set PYTHONDONTWRITEBYTECODE=1
venv\Scripts\python.exe scripts\phase96_model_index_metadata_alignment_apply.py
set RC=%ERRORLEVEL%
echo PHASE96_PYTHON_TOOL_EXIT=%RC%
if not "%RC%"=="0" exit /b %RC%
echo PHASE96_CMD_OK
exit /b 0
