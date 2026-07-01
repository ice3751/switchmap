@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ============================================================
rem PHASE114 FINAL UI/SEARCH REPAIR - ROLLBACK
rem   Restores files from the last recorded backup only.
rem   * no DB touch   * no service restart
rem ============================================================

set "PROJECT_ROOT=C:\SwitchMap"
set "REPORTS=%PROJECT_ROOT%\reports"
set "LASTFILE=%REPORTS%\phase114_final_ui_search_repair_last_backup.txt"
set "EXPECT=%PROJECT_ROOT%\backups\phase114_final_ui_search_repair_"

set "PY=python"
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%LASTFILE%" ( echo [FAIL] no last-backup file: %LASTFILE% & exit /b 1 )
set "BACKUP="
for /f "usebackq delims=" %%A in ("%LASTFILE%") do set "BACKUP=%%A"
if not defined BACKUP ( echo [FAIL] last-backup file empty & exit /b 1 )

echo [PHASE114] restore from: %BACKUP%

rem ---- validate backup path prefix (safety) ----
set "PREFIX=!BACKUP:%EXPECT%=!"
if "!PREFIX!"=="!BACKUP!" ( echo [FAIL] backup path not under expected phase114 backup root & exit /b 1 )
if not exist "%BACKUP%" ( echo [FAIL] backup folder missing: %BACKUP% & exit /b 1 )

rem ---- restore only files present in that backup ----
pushd "%BACKUP%"
for /r %%F in (*) do (
    set "SRC=%%F"
    set "REL=!SRC:%BACKUP%\=!"
    for %%A in ("%PROJECT_ROOT%\!REL!") do if not exist "%%~dpA" md "%%~dpA"
    copy /Y "%%F" "%PROJECT_ROOT%\!REL!" >nul
    echo   restored !REL!
)
popd

rem ---- manage.py check ----
pushd "%PROJECT_ROOT%"
"%PY%" manage.py check
set "CHECKRC=!errorlevel!"
popd

rem ---- timestamp + rollback json ----
set "LDT="
for /f "skip=1 tokens=1" %%A in ('wmic os get localdatetime 2^>nul') do if not defined LDT set "LDT=%%A"
if not defined LDT set "LDT=00000000000000"
set "TS=%LDT:~0,8%_%LDT:~8,6%"
set "RJSON=%REPORTS%\phase114_final_ui_search_repair_rollback.json"
> "%RJSON%" echo {
>> "%RJSON%" echo   "phase": "phase114_final_ui_search_repair",
>> "%RJSON%" echo   "timestamp": "%TS%",
>> "%RJSON%" echo   "restored_from": "%BACKUP:\=/%",
>> "%RJSON%" echo   "manage_check_rc": %CHECKRC%,
>> "%RJSON%" echo   "db_touch": false,
>> "%RJSON%" echo   "service_restart": false
>> "%RJSON%" echo }

echo [PHASE114] rollback report: %RJSON%
if not "%CHECKRC%"=="0" ( echo [FAIL] manage.py check rc=%CHECKRC% & exit /b 1 )
echo [DONE] rollback complete. manage.py check OK.
exit /b 0
