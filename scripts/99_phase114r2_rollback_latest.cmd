@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe tools\phase114r2_rollback_latest.py
exit /b %ERRORLEVEL%
