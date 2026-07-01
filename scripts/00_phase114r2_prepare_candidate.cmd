@echo off
setlocal
cd /d C:\SwitchMap
venv\Scripts\python.exe tools\phase114r2_prepare_neighbor_endpoint_candidate.py
exit /b %ERRORLEVEL%
