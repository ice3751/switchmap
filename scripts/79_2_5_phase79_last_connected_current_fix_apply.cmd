@echo off
setlocal
cd /d "%~dp0.."
python tools\phase79_2_5_apply.py
if errorlevel 1 exit /b 1
python tools\phase79_2_5_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_2_5_APPLY_OK
