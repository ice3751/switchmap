@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE80_2_ALARM_POLICY_APPLY_START
python manage.py check || exit /b 1
python -m py_compile inventory\alarm_policy.py inventory\alarm_rules.py inventory\views.py inventory\alarm_views.py inventory\management\commands\sfp_background_monitor.py inventory\management\commands\phase80_alarm_policy_audit.py || exit /b 1
python manage.py phase80_alarm_policy_audit --sync --apply || exit /b 1
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress" || exit /b 1

echo PHASE80_2_ALARM_POLICY_APPLY_OK
endlocal
