from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import django

django.setup()

from django.test import Client
from inventory.cisco_backup_tools import (
    INDEX_PATH,
    audit_backup_security_metadata,
    audit_existing_backup_index,
    list_backups,
    read_backup_content,
    mask_sensitive_config,
)

print("PHASE84_3_CISCO_BACKUP_SECURITY_HARDENING_START")

backup_dir = PROJECT_ROOT / "backups" / ("phase84_3_cisco_backup_security_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)
if INDEX_PATH.exists():
    shutil.copy2(INDEX_PATH, backup_dir / "cisco_backup_index.json")
print("BACKUP_DIR=", backup_dir)

validation_audit = audit_existing_backup_index()
security_audit = audit_backup_security_metadata()
print("VALIDATION_AUDIT=", validation_audit)
print("SECURITY_AUDIT=", security_audit)

bad_preview = 0
for row in list_backups(limit=50):
    if not row.get("success"):
        continue
    content = read_backup_content(row)
    masked, count = mask_sensitive_config(content)
    low = masked.lower()
    residual_sensitive = (
        " secret 5 $",
        " password 7 ",
        "snmp-server community ro ",
        "snmp-server community rw ",
        "308203",
        "certificate ca 01",
        "certificate self-signed 01",
        "private-key",
        "begin private key",
    )
    if any(token in low for token in residual_sensitive):
        bad_preview += 1
print("BAD_MASKED_PREVIEW_COUNT=", bad_preview)
if bad_preview:
    raise SystemExit(3)

client = Client(HTTP_HOST="it-tools.winac-co.com:8000")
for path in ["/", "/cisco-backups/", "/backups/", "/alarms/"]:
    code = client.get(path).status_code
    print(f"URL {path} {code}")
    if code not in (200, 302, 403):
        raise SystemExit(4)

print("PHASE84_3_CISCO_BACKUP_SECURITY_HARDENING_OK")
