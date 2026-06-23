from pathlib import Path

checks = [
    (Path('inventory/templates/inventory/base.html'), ['app-topbar', 'switch-menu-panel', 'topbar-nav', 'swmap_switch_menu_groups']),
    (Path('inventory/templates/inventory/switch_list.html'), ['phase42-dashboard-grid', 'modern-kpi-card', 'device-browser-shell']),
    (Path('inventory/static/inventory/css/switchmap-phase42.css'), ['Phase 42', 'app-topbar', 'modern-dashboard-grid']),
    (Path('inventory/context_processors.py'), ['swmap_switch_menu_groups', '_switch_menu_groups']),
]

missing = []
for path, needles in checks:
    if not path.exists():
        missing.append(f'MISSING_FILE:{path}')
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for needle in needles:
        if needle not in text:
            missing.append(f'MISSING:{needle}:{path}')

if missing:
    raise SystemExit('PHASE42_SMOKE_FAIL ' + ' | '.join(missing))

print('PHASE42_TOP_NAV_DASHBOARD_OK')
