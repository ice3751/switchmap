@echo off
setlocal
cd /d "%~dp0\.."
python tools\phase79_2_6_history_import_fix_verify.py
