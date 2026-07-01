@echo off
setlocal
cd /d "%~dp0.."
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python tools\phase79_2_2_apply.py
if errorlevel 1 exit /b 1
python tools\phase79_2_1_verify.py
if errorlevel 1 exit /b 1
echo PHASE79_2_2_APPLY_OK
