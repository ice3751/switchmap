@echo off
setlocal
cd /d C:\SwitchMap
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python tools\phase73_1_header_refresh_button_finalize.py
