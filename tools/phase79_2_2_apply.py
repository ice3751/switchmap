from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / 'backups' / ('phase79_2_2_verify_namespace_fix_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
PAYLOAD = ROOT / 'payload'
TARGET = Path('tools/phase79_2_1_verify.py')


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    src = ROOT / TARGET
    if src.exists():
        dst = BACKUP_ROOT / TARGET
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    payload = PAYLOAD / TARGET
    if not payload.exists():
        raise FileNotFoundError(payload)
    (ROOT / TARGET).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload, ROOT / TARGET)
    print(f'PHASE79_2_2_PATCH_OK backup_dir={BACKUP_ROOT}')

if __name__ == '__main__':
    main()
