@echo off
setlocal
cd /d "%~dp0\.."
if not exist manage.py (
  echo PHASE77_FAIL manage.py not found
  exit /b 1
)
python scripts\phase77_make_safe_source_zip.py
endlocal
