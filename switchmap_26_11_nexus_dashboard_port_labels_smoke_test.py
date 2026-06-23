from pathlib import Path

p = Path('inventory/templates/inventory/includes/nexus_svg.html')
text = p.read_text(encoding='utf-8')
required = [
    '--nexus-main-w:30px',
    '.nexus-map-dashboard .nexus-port-no{display:block;font-size:7px',
    '.nexus-map-dashboard .nexus-port-vlan{display:none;}',
    '.nexus-map-dashboard .nexus-uplink-port .nexus-port-no{font-size:6px',
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit('SMOKE_TEST_FAILED missing: ' + ', '.join(missing))
print('SMOKE_TEST_OK')
