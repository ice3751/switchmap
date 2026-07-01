@echo off
schtasks /Create /F /SC MINUTE /MO 5 /TN "SwitchMap Dashboard Background Refresh" /TR "\"C:\SwitchMap\scripts\54_dashboard_background_refresh_runner.cmd\""
if errorlevel 1 (
    echo PHASE63_DASHBOARD_BACKGROUND_TASK_WARNING
    exit /b 0
)
echo PHASE63_DASHBOARD_BACKGROUND_TASK_OK
