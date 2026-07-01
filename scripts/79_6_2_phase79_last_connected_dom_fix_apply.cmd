@echo off
setlocal
cd /d C:\SwitchMap
python tools\phase79_6_2_last_connected_dom_fix.py
if errorlevel 1 (
  echo PHASE79_6_2_CMD_FAIL
  exit /b 1
)
echo PHASE79_6_2_CMD_OK
