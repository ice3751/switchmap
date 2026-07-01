@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe tools\phase114r2_apply_from_candidate.py
exit /b %ERRORLEVEL%
