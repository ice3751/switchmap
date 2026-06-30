@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "NSSM=%ROOT%\tools\nssm\nssm.exe"
if not exist "%NSSM%" (
  echo NSSM_NOT_FOUND: %NSSM%
  echo Put nssm.exe in tools\nssm\nssm.exe or use scripts\install_waitress_startup_task.cmd
  exit /b 1
)
"%NSSM%" install SwitchMap "%ROOT%\venv\Scripts\python.exe" "%ROOT%\run_waitress.py"
if errorlevel 1 exit /b 1
"%NSSM%" set SwitchMap AppDirectory "%ROOT%"
"%NSSM%" set SwitchMap AppStdout "%ROOT%\logs\waitress-service.log"
"%NSSM%" set SwitchMap AppStderr "%ROOT%\logs\waitress-service-error.log"
"%NSSM%" set SwitchMap Start SERVICE_AUTO_START
"%NSSM%" start SwitchMap
endlocal
