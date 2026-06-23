@echo off
setlocal
cd /d C:\SwitchMap

if not exist logs mkdir logs
if not exist backups mkdir backups
copy switchmap.env backups\switchmap.env.bak-phase41-4 >nul
copy inventory\views.py backups\views.py.bak-phase41-4 >nul

venv\Scripts\python.exe scripts\phase41_4_patch_views.py
if errorlevel 1 goto fail

findstr /V /B /C:"SWITCHMAP_ALLOWED_HOSTS=" /C:"SWITCHMAP_CSRF_TRUSTED_ORIGINS=" switchmap.env > switchmap.env.tmp
if errorlevel 2 goto fail
echo SWITCHMAP_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.0.11,it-tools,IT-TOOLS,it-tools.winac-co.com,IT-TOOLS.winac-co.com>> switchmap.env.tmp
echo SWITCHMAP_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://192.168.0.11:8000,http://it-tools:8000,http://it-tools.winac-co.com:8000>> switchmap.env.tmp
move /Y switchmap.env.tmp switchmap.env >nul

takeown /F logs /R /D Y >nul 2>nul
icacls logs /grant "%USERDOMAIN%\%USERNAME%:(OI)(CI)F" /T >nul 2>nul

venv\Scripts\python.exe manage.py check
if errorlevel 1 goto fail

venv\Scripts\python.exe switchmap_41_4_admin_host_and_edit_smoke_test.py
if errorlevel 1 goto fail

venv\Scripts\python.exe manage.py cleanup_test_switches
if errorlevel 1 goto fail

schtasks /End /TN "SwitchMap Waitress" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >nul 2>nul
schtasks /Run /TN "SwitchMap Waitress"
timeout /t 5 >nul
netstat -ano | findstr ":8000"

echo PHASE41_4_APPLY_OK
exit /b 0

:fail
echo PHASE41_4_APPLY_FAILED
exit /b 1
