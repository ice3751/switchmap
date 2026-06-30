@echo off
setlocal
set ROOT=C:\SwitchMap
cd /d "%ROOT%" || exit /b 1

echo PROJECT=%ROOT%
if exist "%ROOT%\backups\phase70_limited_quick_search_fix_*" (echo PHASE70_BACKUP_EXISTS=YES) else (echo PHASE70_BACKUP_EXISTS=NO)

findstr /N /C:"data-port-label" inventory\templates\inventory\includes\cisco_3850_svg.html >nul && echo CISCO3850_DATA_PORT_LABEL=YES || echo CISCO3850_DATA_PORT_LABEL=NO
findstr /N /C:"data-port-description" inventory\templates\inventory\includes\cisco_3850_svg.html >nul && echo CISCO3850_DATA_PORT_DESCRIPTION=YES || echo CISCO3850_DATA_PORT_DESCRIPTION=NO
findstr /N /C:"PHASE70_LIMITED_QUICK_SEARCH_FIX" inventory\static\inventory\switchmap.js >nul && echo JS_PHASE70_MARKER=YES || echo JS_PHASE70_MARKER=NO
findstr /N /C:"PHASE70_LIMITED_QUICK_SEARCH_FIX" inventory\static\inventory\css\switchmap-dashboard-stable-main.css >nul && echo CSS_PHASE70_MARKER=YES || echo CSS_PHASE70_MARKER=NO
findstr /N /C:"portText = function" inventory\static\inventory\switchmap.js
findstr /N /C:"browserInitialOpen" inventory\static\inventory\switchmap.js
findstr /N /C:"search-port-highlight" inventory\static\inventory\css\switchmap-dashboard-stable-main.css

if exist staticfiles\inventory\switchmap.js (
  fc /b staticfiles\inventory\switchmap.js inventory\static\inventory\switchmap.js >nul && echo STATIC_MATCH_APP::switchmap.js=OK || echo STATIC_MATCH_APP::switchmap.js=FAIL
) else (
  echo STATIC_MATCH_APP::switchmap.js=MISSING
)
if exist staticfiles\inventory\css\switchmap-dashboard-stable-main.css (
  fc /b staticfiles\inventory\css\switchmap-dashboard-stable-main.css inventory\static\inventory\css\switchmap-dashboard-stable-main.css >nul && echo STATIC_MATCH_APP::switchmap-dashboard-stable-main.css=OK || echo STATIC_MATCH_APP::switchmap-dashboard-stable-main.css=FAIL
) else (
  echo STATIC_MATCH_APP::switchmap-dashboard-stable-main.css=MISSING
)
endlocal
