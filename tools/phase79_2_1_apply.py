from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / 'backups' / ('phase79_2_1_last_connected_layout_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
PAYLOAD = ROOT / 'payload'

FILES_TO_COPY = [
    Path('inventory/static/inventory/css/switchmap-phase79.css'),
]

BASE_FILE = ROOT / 'inventory/templates/inventory/base.html'
OLD_VERSIONS = [
    'phase79-2-port-history-popup',
    'phase79-2-1-last-connected-layout-fix',
]
NEW_VERSION = 'phase79-2-1-last-connected-layout-fix'


def backup_file(rel: Path) -> None:
    src = ROOT / rel
    if src.exists():
        dst = BACKUP_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_payload(rel: Path) -> None:
    src = PAYLOAD / rel
    dst = ROOT / rel
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def bump_base_version() -> None:
    if not BASE_FILE.exists():
        raise FileNotFoundError(BASE_FILE)
    rel = Path('inventory/templates/inventory/base.html')
    backup_file(rel)
    text = BASE_FILE.read_text(encoding='utf-8')
    if 'switchmap-phase79.css' not in text:
        raise RuntimeError('switchmap-phase79.css include not found in base.html')
    changed = False
    for old in OLD_VERSIONS:
        if old in text:
            text = text.replace(old, NEW_VERSION)
            changed = True
    if not changed:
        text = text.replace('switchmap-phase79.css" %}?v=', 'switchmap-phase79.css" %}?v=' + NEW_VERSION + '-')
    BASE_FILE.write_text(text, encoding='utf-8')


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for rel in FILES_TO_COPY:
        backup_file(rel)
        copy_payload(rel)
    bump_base_version()
    print(f'PHASE79_2_1_PATCH_OK backup_dir={BACKUP_ROOT}')


if __name__ == '__main__':
    main()
