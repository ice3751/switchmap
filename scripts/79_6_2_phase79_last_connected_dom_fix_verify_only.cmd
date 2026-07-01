@echo off
setlocal
cd /d C:\SwitchMap
python -c "import re, pathlib; root=pathlib.Path('.'); files=['inventory/templates/inventory/switch_list.html','inventory/templates/inventory/switch_detail.html']; fail=[]; ok=[]; [ok.append('file:'+f) if (root/f).exists() else fail.append('missing:'+f) for f in map(pathlib.Path,files)]; css=(root/'inventory/static/inventory/css/switchmap-phase79.css').read_text(encoding='utf-8',errors='ignore'); js=(root/'inventory/static/inventory/switchmap.js').read_text(encoding='utf-8',errors='ignore'); base=(root/'inventory/templates/inventory/base.html').read_text(encoding='utf-8',errors='ignore'); ok.append('css_marker') if 'PHASE79_6_2_LAST_CONNECTED_DOM_FIX' in css else fail.append('css_marker_missing'); ok.append('js_marker') if 'PHASE79_6_2_LAST_CONNECTED_DOM_FIX' in js else fail.append('js_marker_missing'); ok.append('base_version') if 'phase79-6-2-dom-fix' in base else fail.append('base_version_missing'); print('PHASE79_6_2_VERIFY_REPORT'); print('OK_COUNT='+str(len(ok))); print('FAIL_COUNT='+str(len(fail))); print('[OK]'); [print('OK '+x) for x in ok]; print('[FAIL]'); [print('FAIL '+x) for x in fail] or print('- none'); raise SystemExit(1 if fail else 0)"
if errorlevel 1 (
  echo PHASE79_6_2_VERIFY_FAIL
  exit /b 1
)
echo PHASE79_6_2_VERIFY_OK
