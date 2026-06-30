from pathlib import Path
fail=[]
checks=[]
base=Path('inventory/templates/inventory/base.html')
js=Path('inventory/static/inventory/switchmap-phase79-lc-override.js')
css=Path('inventory/static/inventory/css/switchmap-phase79.css')
static_js=Path('staticfiles/inventory/switchmap-phase79-lc-override.js')
for p in (base,js,css):
    if not p.exists():
        fail.append(f'missing:{p}')
base_s=base.read_text(encoding='utf-8', errors='ignore') if base.exists() else ''
js_s=js.read_text(encoding='utf-8', errors='ignore') if js.exists() else ''
css_s=css.read_text(encoding='utf-8', errors='ignore') if css.exists() else ''
checks.append(('base_include', 'switchmap-phase79-lc-override.js' in base_s))
checks.append(('js_marker', 'PHASE79_6_5_LAST_CONNECTED_OVERRIDE' in js_s))
checks.append(('js_fetch_payload', '/payload/' in js_s))
checks.append(('js_current_title', 'Current Connected Device' in js_s))
checks.append(('js_preview_fix', 'fixPreview' in js_s and 'interface ' in js_s))
checks.append(('css_marker', 'PHASE79_6_5_LAST_CONNECTED_OVERRIDE_CSS' in css_s))
for name, ok in checks:
    print(('OK ' if ok else 'FAIL ') + name)
    if not ok: fail.append(name)
if static_js.exists():
    ss=static_js.read_text(encoding='utf-8', errors='ignore')
    ok='PHASE79_6_5_LAST_CONNECTED_OVERRIDE' in ss
    print(('OK ' if ok else 'FAIL ') + 'staticfiles_override_marker')
    if not ok: fail.append('staticfiles_override_marker')
else:
    print('WARN staticfiles override missing; run collectstatic before restart')
if fail:
    raise SystemExit('PHASE79_6_5_VERIFY_FAIL ' + ','.join(fail))
print('PHASE79_6_5_VERIFY_OK')
