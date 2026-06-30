@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "NSSM=%ROOT%\tools\nssm\nssm.exe"
if not exist "%NSSM%" (
  echo NSSM_NOT_FOUND: %NSSM%
  exit /b 1
)
"%NSSM%" stop SwitchMap
"%NSSM%" remove SwitchMap confirm
endlocal
