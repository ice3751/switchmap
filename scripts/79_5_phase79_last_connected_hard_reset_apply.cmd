@echo off
setlocal
cd /d %~dp0\..
python tools\phase79_5_last_connected_hard_reset_apply.py
if errorlevel 1 exit /b 1
python tools\phase79_5_last_connected_hard_reset_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_5_APPLY_OK
