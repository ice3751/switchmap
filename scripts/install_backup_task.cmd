@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
schtasks /Create /TN "SwitchMap SQLite Backup" /SC DAILY /ST 23:30 /TR "cmd.exe /c \"\"%ROOT%\switchmap_backup_sqlite.cmd\"\"" /F
endlocal
