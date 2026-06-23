from pathlib import Path

p = Path('inventory/templates/inventory/includes/nexus_svg.html')
text = p.read_text(encoding='utf-8')
required = [
    '.nexus-map-dashboard .nexus-row{display:flex;',
    'justify-content:space-between',
    'grid-template-columns:minmax(0,1fr) 58px',
    'NEXUS_DASHBOARD_LAYOUT_FIX_READY',
]
missing = [x for x in required[:-1] if x not in text]
if missing:
    raise SystemExit('SMOKE_TEST_FAILED missing: ' + ', '.join(missing))
print('SMOKE_TEST_OK')
