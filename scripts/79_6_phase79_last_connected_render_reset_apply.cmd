@echo off
setlocal
cd /d C:\SwitchMap
python tools\phase79_6_last_connected_render_reset.py
if errorlevel 1 goto fail
python manage.py collectstatic --noinput >nul
python tools\phase79_6_verify.py
if errorlevel 1 goto fail
echo PHASE79_6_APPLY_OK
exit /b 0
:fail
echo PHASE79_6_APPLY_FAIL
exit /b 1
