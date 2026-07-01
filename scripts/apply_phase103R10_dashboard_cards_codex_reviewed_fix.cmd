@echo off
setlocal EnableExtensions
set "PROJECT=C:\SwitchMap"
set "PY=%PROJECT%\venv\Scripts\python.exe"
set "PATCH_ROOT=%~dp0.."

if not exist "%PROJECT%\manage.py" (
  echo PROJECT_NOT_FOUND=%PROJECT%
  exit /b 1
)

if not exist "%PY%" (
  echo VENV_PYTHON_NOT_FOUND=%PY%
  exit /b 1
)

cd /d "%PROJECT%" || exit /b 1
"%PY%" "%PATCH_ROOT%\scripts\apply_phase103R10_dashboard_cards_codex_reviewed_fix.py"
exit /b %ERRORLEVEL%
