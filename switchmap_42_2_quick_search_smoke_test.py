from pathlib import Path
checks = [
    (Path('inventory/static/inventory/switchmap.js'), ['search-active', 'data-search-empty-state', 'data-search-result-state', 'terms.every']),
    (Path('inventory/static/inventory/css/switchmap-phase42.css'), ['Phase 42.2', 'search-result-state', 'search-empty-state']),
]
missing=[]
for path, needles in checks:
    if not path.exists():
        missing.append(f'MISSING_FILE:{path}')
        continue
    text=path.read_text(encoding='utf-8', errors='ignore')
    for needle in needles:
        if needle not in text:
            missing.append(f'MISSING:{needle}:{path}')
if missing:
    raise SystemExit('PHASE42_2_SMOKE_FAIL ' + ' | '.join(missing))
print('PHASE42_2_QUICK_SEARCH_OK')
