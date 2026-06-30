@echo off
setlocal
cd /d %~dp0\..
python tools\phase79_4_last_connected_final_apply.py
if errorlevel 1 exit /b 1
python tools\phase79_4_last_connected_final_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_4_APPLY_OK
