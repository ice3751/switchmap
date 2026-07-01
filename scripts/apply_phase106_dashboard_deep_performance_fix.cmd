@echo off
setlocal EnableExtensions
set "PROJECT_ROOT=C:\SwitchMap"
set "PATCH_ROOT=%~dp0.."
if not exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
  echo PHASE106_FAIL python_not_found:%PROJECT_ROOT%\venv\Scripts\python.exe
  exit /b 1
)
"%PROJECT_ROOT%\venv\Scripts\python.exe" "%PATCH_ROOT%\scripts\apply_phase106_dashboard_deep_performance_fix.py" --project-root "%PROJECT_ROOT%" --patch-root "%PATCH_ROOT%"
exit /b %ERRORLEVEL%
