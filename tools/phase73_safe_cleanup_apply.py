from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_DIR = BASE_DIR / 'backups' / f'phase73_safe_cleanup_{STAMP}'
ARCHIVE_DIR = BACKUP_DIR / 'archived_files'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

print('PHASE73_SAFE_CLEANUP_APPLY')
print(f'PROJECT={BASE_DIR}')
print(f'PHASE73_BACKUP={BACKUP_DIR}')

# Database backup first.
db = BASE_DIR / 'db.sqlite3'
if db.exists():
    shutil.copy2(db, BACKUP_DIR / 'db.sqlite3')
    print(f'DB_BACKUP=OK::{BACKUP_DIR / "db.sqlite3"}')
else:
    print('DB_BACKUP=SKIPPED_MISSING')

manifest: list[str] = []

def archive_path(p: Path, reason: str) -> None:
    if not p.exists():
        return
    rel = p.relative_to(BASE_DIR)
    dest = ARCHIVE_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(p), str(dest))
    else:
        if dest.exists():
            dest.unlink()
        shutil.move(str(p), str(dest))
    line = f'{reason}|{rel}'
    manifest.append(line)
    print(f'ARCHIVED::{line}')

# Patch dashboard header: remove manual Refresh View button, keep last update only.
switch_list = BASE_DIR / 'inventory' / 'templates' / 'inventory' / 'switch_list.html'
if switch_list.exists():
    template_backup_dir = BACKUP_DIR / 'templates'
    template_backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(switch_list, template_backup_dir / 'switch_list.html')
    text = switch_list.read_text(encoding='utf-8', errors='replace')
    original = text
    # Remove only the toolbar manual refresh button. Last update stays.
    pattern = re.compile(
        r'\n\s*<button\s+class="sm-main-refresh-btn btn btn-primary"\s+type="button"\s+data-dashboard-manual-refresh[^>]*>.*?</button>',
        re.IGNORECASE | re.DOTALL,
    )
    text, count = pattern.subn('', text, count=1)
    if count:
        switch_list.write_text(text, encoding='utf-8', newline='')
        print('REFRESH_VIEW_BUTTON_REMOVED=YES')
    else:
        print('REFRESH_VIEW_BUTTON_REMOVED=NO_ALREADY_ABSENT_OR_CHANGED')
    print(f'TEMPLATE_BACKUP=OK::{template_backup_dir / "switch_list.html"}')
else:
    print('REFRESH_VIEW_BUTTON_REMOVED=NO_TEMPLATE_MISSING')

# Delete known test switches only, after DB backup.
try:
    import django
    django.setup()
    from inventory.models import Switch
    qs = Switch.objects.filter(name__icontains='Smoke') | Switch.objects.filter(name__startswith='Phase41-') | Switch.objects.filter(management_ip='10.41.2.1')
    qs = qs.distinct()
    test_switches = list(qs.order_by('name'))
    print(f'TEST_SWITCH_DELETE_CANDIDATES={len(test_switches)}')
    for sw in test_switches:
        print(f'TEST_SWITCH_DELETE={sw.id}|{sw.name}|{sw.management_ip}')
    deleted_count = 0
    deleted_detail = {}
    if test_switches:
        deleted_count, deleted_detail = qs.delete()
    print(f'TEST_SWITCH_DELETE_DONE={deleted_count}')
    if deleted_detail:
        print(f'TEST_SWITCH_DELETE_DETAIL={deleted_detail}')
except Exception as exc:
    print(f'TEST_SWITCH_DELETE_ERROR={type(exc).__name__}: {exc}')

# Archive generated clutter, never scheduled runners.
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

seen = set()
for p in candidates:
    if not p.exists():
        continue
    rp = p.resolve()
    if rp in seen:
        continue
    seen.add(rp)
    # Never archive the currently required phase73 scripts/tools.
    try:
        rel = p.relative_to(BASE_DIR)
    except ValueError:
        continue
    if str(rel).replace('\\', '/').startswith('tools/phase73_'):
        continue
    archive_path(p, 'cleanup')

# Remove bytecode/cache directories safely.
cache_removed = 0
for p in list(BASE_DIR.rglob('__pycache__')) + [BASE_DIR / '.pytest_cache']:
    if p.exists() and p.is_dir():
        rel = p.relative_to(BASE_DIR)
        shutil.rmtree(p)
        cache_removed += 1
        print(f'CACHE_REMOVED::{rel}')
print(f'CACHE_REMOVED_COUNT={cache_removed}')

manifest_path = BACKUP_DIR / 'manifest.txt'
manifest_path.write_text('\n'.join(manifest) + ('\n' if manifest else ''), encoding='utf-8')
print(f'MANIFEST={manifest_path}')
print('PHASE73_SAFE_CLEANUP_APPLY_DONE')
