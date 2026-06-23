from pathlib import Path

from switchmap_smoke import read_static_css

ROOT = Path(__file__).resolve().parent
html = (ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_list.html').read_text(encoding='utf-8')
css = read_static_css()

required_html = [
    'sfp-dash-tools',
    'sfp-dash-title',
    'data-sfp-message',
    'setScanState',
    'escapeHtml',
]
required_css = [
    'Phase 26.6 - Dashboard SFP Widget Responsive Cleanup',
    '.sfp-dash-tools',
    '.sfp-dash-message',
    '.sfp-mini-state',
    '@media(max-width:1120px)',
]
missing = [item for item in required_html if item not in html]
missing += [item for item in required_css if item not in css]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))

if css.count('{') != css.count('}'):
    raise SystemExit('CSS_BRACE_MISMATCH')

print('SMOKE_TEST_OK')
