@echo off
setlocal EnableExtensions
cd /d C:\SwitchMap
if not exist logs mkdir logs
if not exist backups mkdir backups
echo PHASE76_FULL_VERIFY_SAFE_CLEANUP_START
venv\Scripts\python.exe tools\phase76_full_verify_safe_cleanup.py
set RC=%ERRORLEVEL%
echo PHASE76_FULL_VERIFY_SAFE_CLEANUP_EXIT=%RC%
exit /b %RC%
