@echo off
setlocal EnableExtensions
cd /d C:\SwitchMap
if errorlevel 1 exit /b 2

if not exist reports mkdir reports
if not exist logs mkdir logs
if not exist reports\_archive mkdir reports\_archive
if not exist reports\_archive\endpoint_live_tracking mkdir reports\_archive\endpoint_live_tracking

for /f %%i in ('venv\Scripts\python.exe -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'))"') do set "STAMP=%%i"
set "REPORT_FILE=C:\SwitchMap\reports\endpoint_live_tracking_latest.txt"
set "RUN_REPORT=C:\SwitchMap\reports\_archive\endpoint_live_tracking\endpoint_live_tracking_r8_2_run_%STAMP%.txt"
set "LOCK_DIR=C:\SwitchMap\logs\endpoint_tracking_r8.lock"

move /Y C:\SwitchMap\reports\endpoint_live_tracking_r8_apply_*.csv C:\SwitchMap\reports\_archive\endpoint_live_tracking\ >nul 2>nul
move /Y C:\SwitchMap\reports\endpoint_live_tracking_r8_2_run_*.txt C:\SwitchMap\reports\_archive\endpoint_live_tracking\ >nul 2>nul

echo PHASE112R8_2_ENDPOINT_TRACKING_RUN>"%RUN_REPORT%"
echo START_DATE=%DATE% START_TIME=%TIME%>>"%RUN_REPORT%"
echo DB_MUTATION=YES>>"%RUN_REPORT%"
echo SERVICE_RESTART=NO>>"%RUN_REPORT%"
echo SSH_EXECUTION=NO>>"%RUN_REPORT%"
echo SCHEDULED_RUNNER=YES>>"%RUN_REPORT%"
echo OVERLAP_GUARD=LOCK_DIR>>"%RUN_REPORT%"
echo LOCK_DIR=%LOCK_DIR%>>"%RUN_REPORT%"
echo OBSERVATION_WRITE=NO_FOR_SCHEDULED_RUN>>"%RUN_REPORT%"
echo COMMAND=venv\Scripts\python.exe manage.py endpoint_live_tracking --quiet --no-observation-write>>"%RUN_REPORT%"
echo.>>"%RUN_REPORT%"

mkdir "%LOCK_DIR%" >nul 2>nul
if errorlevel 1 (
  echo SKIPPED_ALREADY_RUNNING=YES>>"%RUN_REPORT%"
  echo END_DATE=%DATE% END_TIME=%TIME%>>"%RUN_REPORT%"
  echo PHASE112R8_2_ENDPOINT_TRACKING_RUN_DONE=SKIPPED>>"%RUN_REPORT%"
  copy /Y "%RUN_REPORT%" "%REPORT_FILE%" >nul
  echo REPORT_FILE=%REPORT_FILE%
  exit /b 0
)

venv\Scripts\python.exe manage.py endpoint_live_tracking --quiet --no-observation-write >>"%RUN_REPORT%" 2>&1
set "RUN_RC=%ERRORLEVEL%"

echo.>>"%RUN_REPORT%"
echo ENDPOINT_TRACKING_EXIT_CODE=%RUN_RC%>>"%RUN_REPORT%"
echo VERIFY_AFTER_RUN=START>>"%RUN_REPORT%"
venv\Scripts\python.exe manage.py shell -c "from inventory.models import NetworkEndpoint,EndpointObservation; from collections import Counter; print('NETWORK_ENDPOINTS=',NetworkEndpoint.objects.count()); print('ENDPOINT_OBSERVATIONS=',EndpointObservation.objects.count()); print('BY_VLAN=',dict(Counter(str(e.vlan) for e in NetworkEndpoint.objects.all()))); print('BY_CONNECTION_TYPE=',dict(Counter(e.connection_type for e in NetworkEndpoint.objects.all())))" >>"%RUN_REPORT%" 2>&1
set "VERIFY_RC=%ERRORLEVEL%"
echo VERIFY_EXIT_CODE=%VERIFY_RC%>>"%RUN_REPORT%"
echo END_DATE=%DATE% END_TIME=%TIME%>>"%RUN_REPORT%"
if "%RUN_RC%"=="0" if "%VERIFY_RC%"=="0" echo PHASE112R8_2_ENDPOINT_TRACKING_RUN_DONE=YES>>"%RUN_REPORT%"
if not "%RUN_RC%"=="0" echo PHASE112R8_2_ENDPOINT_TRACKING_RUN_DONE=NO>>"%RUN_REPORT%"
if not "%VERIFY_RC%"=="0" echo PHASE112R8_2_ENDPOINT_TRACKING_RUN_DONE=NO>>"%RUN_REPORT%"

rmdir "%LOCK_DIR%" >nul 2>nul
copy /Y "%RUN_REPORT%" "%REPORT_FILE%" >nul
move /Y C:\SwitchMap\reports\endpoint_live_tracking_r8_apply_*.csv C:\SwitchMap\reports\_archive\endpoint_live_tracking\ >nul 2>nul
echo REPORT_FILE=%REPORT_FILE%
exit /b %RUN_RC%
