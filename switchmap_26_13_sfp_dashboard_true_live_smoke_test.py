from pathlib import Path

from switchmap_smoke import read_static_css

checks = {
    Path('inventory/templates/inventory/switch_list.html'): [
        'data-sfp-start-live',
        'data-sfp-stop-live',
        'data-sfp-live-interval',
        'data-sfp-last-poll',
        'window.SFP_DASHBOARD_TRUE_LIVE_READY',
        'setInterval(function(){ pollNow',
        'document.hidden',
    ],
}

for path, required in checks.items():
    if not path.exists():
        raise SystemExit(f'SMOKE_TEST_FAILED missing file: {path}')
    text = path.read_text(encoding='utf-8')
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f'SMOKE_TEST_FAILED {path}: ' + ', '.join(missing))

css = read_static_css()
missing_css = [
    item for item in (
        'Phase 26.13 SFP dashboard true live',
        '.sfp-live-badge',
        '.sfp-dash-live-meta',
    )
    if item not in css
]
if missing_css:
    raise SystemExit('SMOKE_TEST_FAILED css: ' + ', '.join(missing_css))

print('SMOKE_TEST_OK')
