@echo off
setlocal
cd /d C:\SwitchMap
python tools\phase79_6_1_last_connected_actual_reset.py
if errorlevel 1 (
  echo PHASE79_6_1_APPLY_FAIL
  exit /b 1
)
python manage.py check
if errorlevel 1 (
  echo PHASE79_6_1_DJANGO_CHECK_FAIL
  exit /b 1
)
python manage.py collectstatic --noinput >nul
if errorlevel 1 (
  echo PHASE79_6_1_COLLECTSTATIC_FAIL
  exit /b 1
)
echo PHASE79_6_1_APPLY_OK
exit /b 0
