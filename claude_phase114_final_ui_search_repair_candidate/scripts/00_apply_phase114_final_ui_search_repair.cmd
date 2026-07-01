@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ============================================================
rem PHASE114 FINAL UI/SEARCH REPAIR - APPLY (report-only + file copy)
rem   * no service restart   * no migration   * no collectstatic
rem   * no SNMP / SSH / discovery   * no DB write
rem ============================================================

set "SCRIPTS=%~dp0"
for %%I in ("%SCRIPTS%..") do set "CAND=%%~fI"
set "FILES=%CAND%\files"
set "PROJECT_ROOT=C:\SwitchMap"
set "REPORTS=%PROJECT_ROOT%\reports"
set "BACKUPS_ROOT=%PROJECT_ROOT%\backups"

echo [PHASE114] Candidate : %CAND%
echo [PHASE114] Project    : %PROJECT_ROOT%

rem ---- pick python interpreter ----
set "PY=python"
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv\Scripts\python.exe"

rem ---- validate candidate structure ----
if not exist "%FILES%" ( echo [FAIL] missing files\ folder & exit /b 1 )
if not exist "%SCRIPTS%_verify_phase114.py" ( echo [FAIL] missing _verify_phase114.py & exit /b 1 )

rem ---- required replacement files ----
set "APPLIST=inventory\endpoint_display_policy.py inventory\views.py inventory\templatetags\switchmap_extras.py inventory\templates\inventory\includes\generic_port_button.html inventory\templates\inventory\includes\cisco_3850_svg.html inventory\templates\inventory\includes\nexus_svg.html inventory\templates\inventory\includes\dashboard_device_browser.html inventory\templates\inventory\base.html inventory\static\inventory\switchmap-phase79-lc-override.js inventory\static\inventory\js\endpoint_search_bridge_r8_5_4.js"
for %%F in (%APPLIST%) do (
    if not exist "%FILES%\%%F" ( echo [FAIL] missing replacement file: %%F & exit /b 1 )
)
echo [OK] all required replacement files present

rem ---- compile changed python (candidate copies) before copy ----
"%PY%" -m py_compile "%FILES%\inventory\endpoint_display_policy.py" "%FILES%\inventory\views.py" "%FILES%\inventory\templatetags\switchmap_extras.py"
if errorlevel 1 ( echo [FAIL] python compile failed & exit /b 1 )
echo [OK] python compile passed

rem ---- node --check changed JS (if node exists) ----
where node >nul 2>nul
if %errorlevel%==0 (
    node --check "%FILES%\inventory\static\inventory\switchmap-phase79-lc-override.js" || ( echo [FAIL] node check override.js & exit /b 1 )
    node --check "%FILES%\inventory\static\inventory\js\endpoint_search_bridge_r8_5_4.js" || ( echo [FAIL] node check bridge.js & exit /b 1 )
    echo [OK] node --check passed
) else (
    echo [SKIP] node not found; JS syntax check skipped
)

rem ---- timestamp ----
set "LDT="
for /f "skip=1 tokens=1" %%A in ('wmic os get localdatetime 2^>nul') do if not defined LDT set "LDT=%%A"
if not defined LDT set "LDT=00000000000000"
set "TS=%LDT:~0,8%_%LDT:~8,6%"
set "BACKUP=%BACKUPS_ROOT%\phase114_final_ui_search_repair_%TS%"

if not exist "%REPORTS%" md "%REPORTS%"
if not exist "%BACKUP%" md "%BACKUP%"
echo [OK] backup dir: %BACKUP%

rem ---- backup existing target files ----
for %%F in (%APPLIST%) do call :backup "%%F"
if exist "%PROJECT_ROOT%\staticfiles" (
    call :backup "staticfiles\inventory\switchmap-phase79-lc-override.js"
    call :backup "staticfiles\inventory\js\endpoint_search_bridge_r8_5_4.js"
)
> "%REPORTS%\phase114_final_ui_search_repair_last_backup.txt" echo %BACKUP%
echo [OK] backup recorded

rem ---- copy approved replacement files ----
for %%F in (%APPLIST%) do call :apply "%%F"
if exist "%PROJECT_ROOT%\staticfiles" (
    call :apply "staticfiles\inventory\switchmap-phase79-lc-override.js"
    call :apply "staticfiles\inventory\js\endpoint_search_bridge_r8_5_4.js"
    echo [OK] staticfiles production copies updated ^(no collectstatic^)
) else (
    echo [SKIP] no staticfiles\ folder; production static copy step skipped
)
echo [OK] replacement files copied

rem ---- manage.py check after copy ----
pushd "%PROJECT_ROOT%"
"%PY%" manage.py check
set "CHECKRC=!errorlevel!"
popd

rem ---- write apply json ----
set "APPLYJSON=%REPORTS%\phase114_final_ui_search_repair_apply.json"
> "%APPLYJSON%" echo {
>> "%APPLYJSON%" echo   "phase": "phase114_final_ui_search_repair",
>> "%APPLYJSON%" echo   "timestamp": "%TS%",
>> "%APPLYJSON%" echo   "candidate": "%CAND:\=/%",
>> "%APPLYJSON%" echo   "project_root": "%PROJECT_ROOT:\=/%",
>> "%APPLYJSON%" echo   "backup": "%BACKUP:\=/%",
>> "%APPLYJSON%" echo   "manage_check_rc": %CHECKRC%,
>> "%APPLYJSON%" echo   "service_restart": false,
>> "%APPLYJSON%" echo   "migration": false,
>> "%APPLYJSON%" echo   "collectstatic": false,
>> "%APPLYJSON%" echo   "snmp": false,
>> "%APPLYJSON%" echo   "ssh": false,
>> "%APPLYJSON%" echo   "discovery": false,
>> "%APPLYJSON%" echo   "db_write": false
>> "%APPLYJSON%" echo }

if not "%CHECKRC%"=="0" (
    echo [FAIL] manage.py check returned %CHECKRC% - consider rollback
    exit /b 1
)
echo [DONE] apply complete. manage.py check OK.
echo [DONE] apply report: %APPLYJSON%
exit /b 0

:backup
set "REL=%~1"
if exist "%PROJECT_ROOT%\%REL%" (
    for %%A in ("%BACKUP%\%REL%") do if not exist "%%~dpA" md "%%~dpA"
    copy /Y "%PROJECT_ROOT%\%REL%" "%BACKUP%\%REL%" >nul
)
exit /b 0

:apply
set "REL=%~1"
for %%A in ("%PROJECT_ROOT%\%REL%") do if not exist "%%~dpA" md "%%~dpA"
copy /Y "%FILES%\%REL%" "%PROJECT_ROOT%\%REL%" >nul
exit /b 0
