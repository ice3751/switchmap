@echo off
setlocal
cd /d C:\SwitchMap

echo PHASE80_1_SFP_MODULE_ONLY_VERIFY_CMD_START
python manage.py check || exit /b 1
python -m py_compile inventory\views.py inventory\alarm_rules.py inventory\management\commands\sfp_background_monitor.py scripts\phase80_1_sfp_module_only_check.py || exit /b 1
python scripts\phase80_1_sfp_module_only_check.py || exit /b 1

echo PHASE80_1_SFP_MODULE_ONLY_VERIFY_OK
endlocal
