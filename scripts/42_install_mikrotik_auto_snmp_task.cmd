@echo off
setlocal
set "ROOT=%~dp0.."
set "RUNNER=%ROOT%\scripts\41_mikrotik_auto_snmp_poll_runner.cmd"
schtasks /Create /TN "SwitchMap MikroTik Auto SNMP Poll" /SC MINUTE /MO 5 /TR "\"%RUNNER%\"" /F
if errorlevel 1 exit /b 1
echo PHASE62_AUTO_SNMP_TASK_OK
endlocal
