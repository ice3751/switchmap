@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ============================================================
rem PHASE114 FINAL UI/SEARCH REPAIR - VERIFY (read-only)
rem   Writes reports\phase114_final_ui_search_repair_verify.json
rem   * no DB write   * no SNMP / SSH / discovery   * no restart
rem ============================================================

set "SCRIPTS=%~dp0"
set "PROJECT_ROOT=C:\SwitchMap"
set "REPORTS=%PROJECT_ROOT%\reports"
set "VERIFYJSON=%REPORTS%\phase114_final_ui_search_repair_verify.json"

set "PY=python"
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%REPORTS%" md "%REPORTS%"

echo [PHASE114] Verify project: %PROJECT_ROOT%

rem ---- manage.py check ----
pushd "%PROJECT_ROOT%"
"%PY%" manage.py check
set "CHECKRC=!errorlevel!"

rem ---- compile changed python ----
"%PY%" -m py_compile "%PROJECT_ROOT%\inventory\endpoint_display_policy.py" "%PROJECT_ROOT%\inventory\views.py" "%PROJECT_ROOT%\inventory\templatetags\switchmap_extras.py"
if errorlevel 1 ( echo [FAIL] python compile failed & popd & exit /b 1 )

rem ---- node --check changed JS (if node exists) ----
where node >nul 2>nul
if %errorlevel%==0 (
    node --check "%PROJECT_ROOT%\inventory\static\inventory\switchmap-phase79-lc-override.js" || ( echo [FAIL] node check override.js & popd & exit /b 1 )
    node --check "%PROJECT_ROOT%\inventory\static\inventory\js\endpoint_search_bridge_r8_5_4.js" || ( echo [FAIL] node check bridge.js & popd & exit /b 1 )
    echo [OK] node --check passed
) else (
    echo [SKIP] node not found; JS syntax check skipped
)
popd

rem ---- full read-only verifier (templates/payload/targets/urls/isolation) ----
"%PY%" "%SCRIPTS%_verify_phase114.py" "%PROJECT_ROOT%" "%VERIFYJSON%"
set "VRC=!errorlevel!"

echo.
echo [PHASE114] manage.py check rc = %CHECKRC%
echo [PHASE114] verifier rc        = %VRC%
echo [PHASE114] verify report      = %VERIFYJSON%

if not "%CHECKRC%"=="0" exit /b 1
if not "%VRC%"=="0" exit /b 1
echo [DONE] verify PASS
exit /b 0
