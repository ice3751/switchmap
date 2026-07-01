from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

print('PHASE73_CLEANUP_AUDIT')
print(f'PROJECT={BASE_DIR}')

# File audit targets. Apply script archives these, it does not destroy them.
ROOT_ARCHIVE_PATTERNS = [
    'cd',
    'findstr',
    'logs_acl_backup.txt',
    'switchmap_*_smoke_test.py',
    'switchmap.env.bak-*',
]
SOURCE_BACKUP_SUFFIX_RE = re.compile(r'.*(\.phase\d+.*_bak|\.bak|\.orig|\.old)$', re.IGNORECASE)
LOG_ARCHIVE_RE = re.compile(r'^(phase\d+.*|.*audit.*|.*report.*)\.(txt|log)$', re.IGNORECASE)
SCRIPT_PHASE_RE = re.compile(r'^(\d{2,3})_phase\d+.*\.(cmd|bat)$', re.IGNORECASE)
PROTECTED_SCRIPTS = {
    '41_mikrotik_auto_snmp_poll_runner.cmd',
    '54_dashboard_background_refresh_runner.cmd',
    '99_sfp_background_monitor_runner.cmd',
    'switchmap_service_runner.cmd',
}

candidates: list[Path] = []
for pat in ROOT_ARCHIVE_PATTERNS:
    candidates.extend(BASE_DIR.glob(pat))

for parent in [BASE_DIR / 'inventory', BASE_DIR / 'config']:
    if parent.exists():
        for p in parent.rglob('*'):
            if p.is_file() and SOURCE_BACKUP_SUFFIX_RE.match(p.name):
                candidates.append(p)

logs_dir = BASE_DIR / 'logs'
if logs_dir.exists():
    for p in logs_dir.iterdir():
        if p.is_file() and LOG_ARCHIVE_RE.match(p.name) and not p.name.endswith('.json'):
            candidates.append(p)

scripts_dir = BASE_DIR / 'scripts'
if scripts_dir.exists():
    for p in scripts_dir.iterdir():
        if p.is_file() and SCRIPT_PHASE_RE.match(p.name) and p.name not in PROTECTED_SCRIPTS:
            candidates.append(p)

cache_dirs = []
for p in BASE_DIR.rglob('__pycache__'):
    if p.is_dir():
        cache_dirs.append(p)
for name in ['.pytest_cache']:
    p = BASE_DIR / name
    if p.exists():
        cache_dirs.append(p)

seen = set()
clean_candidates = []
for p in candidates:
    try:
        rp = p.resolve()
    except FileNotFoundError:
        continue
    if not p.exists() or rp in seen:
        continue
    seen.add(rp)
    clean_candidates.append(p)

print(f'ARCHIVE_FILE_CANDIDATES={len(clean_candidates)}')
for p in clean_candidates[:200]:
    print(f'ARCHIVE_CANDIDATE={p.relative_to(BASE_DIR)}')
if len(clean_candidates) > 200:
    print(f'ARCHIVE_CANDIDATE_MORE={len(clean_candidates)-200}')

print(f'CACHE_DIR_CANDIDATES={len(cache_dirs)}')
for p in cache_dirs[:100]:
    print(f'CACHE_CANDIDATE={p.relative_to(BASE_DIR)}')

try:
    import django
    django.setup()
    from inventory.models import Switch
    qs = Switch.objects.filter(name__icontains='Smoke') | Switch.objects.filter(name__startswith='Phase41-') | Switch.objects.filter(management_ip='10.41.2.1')
    qs = qs.distinct()
    print(f'TEST_SWITCH_CANDIDATES={qs.count()}')
    for sw in qs.order_by('name'):
        print(f'TEST_SWITCH={sw.id}|{sw.name}|{sw.management_ip}|active={getattr(sw, "is_active", "?")}')
except Exception as exc:
    print(f'DB_AUDIT_ERROR={type(exc).__name__}: {exc}')

switch_list = BASE_DIR / 'inventory' / 'templates' / 'inventory' / 'switch_list.html'
if switch_list.exists():
    text = switch_list.read_text(encoding='utf-8', errors='replace')
    print(f'REFRESH_BUTTON_PRESENT={"YES" if "data-dashboard-manual-refresh" in text else "NO"}')
    print(f'LAST_UPDATE_PRESENT={"YES" if "data-field=\"generated_at\"" in text else "NO"}')
else:
    print('REFRESH_BUTTON_PRESENT=UNKNOWN_TEMPLATE_MISSING')

print('PHASE73_CLEANUP_AUDIT_DONE')
