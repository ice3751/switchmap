from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client
from inventory.cisco_backup_tools import audit_existing_backup_index, list_backups

print("PHASE84_2_CISCO_BACKUP_VALIDATION_FIX_START")
result = audit_existing_backup_index()
print("INDEX_AUDIT=", result)
backups = list_backups(limit=20)
active_ok = sum(1 for row in backups if row.get("success"))
active_fail = sum(1 for row in backups if not row.get("success"))
print("RECENT_BACKUPS=", len(backups), "SUCCESS=", active_ok, "FAILED=", active_fail)
for row in backups[:8]:
    print(
        "ROW=",
        row.get("device"),
        row.get("backup_type"),
        "success=", row.get("success"),
        "size=", row.get("size"),
        "error=", (row.get("error") or "")[:120],
    )
client = Client(HTTP_HOST="it-tools.winac-co.com:8000")
for path in ["/", "/cisco-backups/", "/backups/"]:
    code = client.get(path).status_code
    print("URL", path, code)
    if code not in (200, 302):
        raise SystemExit(f"URL_FAIL {path} {code}")
print("PHASE84_2_CISCO_BACKUP_VALIDATION_FIX_OK")
