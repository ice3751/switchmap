@echo off
setlocal
echo ===== Tasks =====
schtasks /Query /TN "SwitchMap Waitress" /FO LIST | findstr /i "TaskName Status Last Result Next Run Time"
schtasks /Query /TN "SwitchMap SQLite Backup" /FO LIST | findstr /i "TaskName Status Last Result Next Run Time"
echo.
echo ===== Port 8000 =====
netstat -ano | findstr ":8000"
echo.
echo ===== Latest backups =====
dir /O-D /B C:\SwitchMap\backups\sqlite 2>nul | more +0
