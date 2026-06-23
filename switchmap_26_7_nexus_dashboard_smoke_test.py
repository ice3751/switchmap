from pathlib import Path

BASE = Path(__file__).resolve().parent
nexus_path = BASE / 'inventory' / 'templates' / 'inventory' / 'includes' / 'nexus_svg.html'
list_path = BASE / 'inventory' / 'templates' / 'inventory' / 'switch_list.html'
detail_path = BASE / 'inventory' / 'templates' / 'inventory' / 'switch_detail.html'
device_visual_path = BASE / 'inventory' / 'templates' / 'inventory' / 'includes' / 'device_visual.html'

for path in (nexus_path, list_path, detail_path):
    if not path.exists():
        raise SystemExit(f'MISSING: {path}')

nexus = nexus_path.read_text(encoding='utf-8')
list_html = list_path.read_text(encoding='utf-8')
detail_html = detail_path.read_text(encoding='utf-8')
device_visual = device_visual_path.read_text(encoding='utf-8') if device_visual_path.exists() else ''

required_nexus = [
    'nexus-map-dashboard',
    'nexus-row-top',
    'nexus-row-bottom',
    'nexus-uplink-zone',
    'forloop.counter <= 48',
    'forloop.counter > 48',
]
for item in required_nexus:
    if item not in nexus:
        raise SystemExit(f'NEXUS_TEMPLATE_CHECK_FAILED: {item}')

dashboard_has_direct_include = 'inventory/includes/nexus_svg.html' in list_html and 'map_mode="dashboard"' in list_html
dashboard_has_dynamic_include = 'inventory/includes/device_visual.html' in list_html and 'map_mode="dashboard"' in list_html and 'inventory/includes/nexus_svg.html' in device_visual
if not (dashboard_has_direct_include or dashboard_has_dynamic_include):
    raise SystemExit('DASHBOARD_NEXUS_INCLUDE_MISSING')

full_has_direct_include = 'inventory/includes/nexus_svg.html' in detail_html
full_has_dynamic_include = 'inventory/includes/device_visual.html' in detail_html and 'inventory/includes/nexus_svg.html' in device_visual
if not (full_has_direct_include or full_has_dynamic_include):
    raise SystemExit('DETAIL_NEXUS_INCLUDE_MISSING')

print('NEXUS_DASHBOARD_SMOKE_TEST_OK')
