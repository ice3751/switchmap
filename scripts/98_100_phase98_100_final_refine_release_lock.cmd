@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d C:\SwitchMap
if not exist logs mkdir logs
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set _d=%%a%%b%%c%%d
for /f "tokens=1-4 delims=:. " %%a in ("%time%") do set _t=%%a%%b%%c%%d
set _t=%_t: =0%
set LOG=logs\phase98_100_final_refine_release_lock_%_d%_%_t%.log
echo PHASE98_100_LOG=%LOG%
call venv\Scripts\activate.bat >nul 2>&1
python scripts\phase98_100_final_refine_release_lock_apply.py 1>>"%LOG%" 2>>&1
set RC=%ERRORLEVEL%
type "%LOG%"
echo PHASE98_100_LOG=%LOG%
echo PHASE98_100_EXIT=%RC%
exit /b %RC%
