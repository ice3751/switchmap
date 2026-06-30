@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
schtasks /Create /TN "SwitchMap Waitress" /SC ONSTART /DELAY 0001:00 /TR "cmd.exe /c \"\"%ROOT%\scripts\run_waitress.cmd\"\"" /F
endlocal
