from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path.cwd()
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = BASE / "backups" / f"phase86_secure_backup_storage_{STAMP}"


def backup_file(path: Path):
    if path.exists():
        target = BACKUP_DIR / path.relative_to(BASE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def patch_urls():
    path = BASE / "inventory" / "urls.py"
    backup_file(path)
    text = path.read_text(encoding="utf-8")
    original = text
    if "backup_storage_views" not in text:
        # Prefer adding into the multiline inventory view import block.
        if "    mikrotik_backup_views," in text:
            text = text.replace("    mikrotik_backup_views,\n", "    mikrotik_backup_views,\n    backup_storage_views,\n", 1)
        elif "    cisco_backup_views," in text:
            text = text.replace("    cisco_backup_views,\n", "    cisco_backup_views,\n    backup_storage_views,\n", 1)
        elif "from . import" in text:
            text = text.replace("from . import", "from . import backup_storage_views,", 1)
        else:
            raise SystemExit("PHASE86_URL_IMPORT_ANCHOR_NOT_FOUND")
    route = '    path("backup-storage/", backup_management_required(backup_storage_views.backup_storage_status_view), name="backup_storage_status"),\n'
    if 'path("backup-storage/"' not in text:
        if 'path("mikrotik-backups/"' in text:
            text = text.replace('    path("mikrotik-backups/",', route + '    path("mikrotik-backups/",', 1)
        elif 'path("cisco-backups/"' in text:
            text = text.replace('    path("cisco-backups/",', route + '    path("cisco-backups/",', 1)
        elif 'path("backups/"' in text:
            text = text.replace('    path("backups/",', route + '    path("backups/",', 1)
        else:
            raise SystemExit("PHASE86_URL_ROUTE_ANCHOR_NOT_FOUND")
    if "backup_storage_views" not in text or 'path("backup-storage/"' not in text:
        raise SystemExit("PHASE86_URL_PATCH_FAILED")
    path.write_text(text, encoding="utf-8")
    return "patched" if text != original else "already-present"


def patch_base():
    path = BASE / "inventory" / "templates" / "inventory" / "base.html"
    if not path.exists():
        return "missing"
    backup_file(path)
    text = path.read_text(encoding="utf-8")
    original = text
    link = '''                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'backup_storage_status' %}active{% endif %}" href="{% url 'inventory:backup_storage_status' %}">Secure Backup Storage</a>{% endif %}'''
    if "backup_storage_status" not in text:
        anchors = [
            "mikrotik_backup_center",
            "cisco_backup_center",
            "backup_center",
            "config_backups",
        ]
        inserted = False
        for token in anchors:
            idx = text.find(token)
            if idx == -1:
                continue
            # Insert after the full anchor line containing this token.
            line_start = text.rfind("\n", 0, idx) + 1
            line_end = text.find("\n", idx)
            if line_end == -1:
                line_end = len(text)
            text = text[:line_end + 1] + link + "\n" + text[line_end + 1:]
            inserted = True
            break
        if not inserted:
            raise SystemExit("PHASE86_BASE_MENU_ANCHOR_NOT_FOUND")
    # Extend dropdown active condition when the old phase uses a summary expression.
    if "current == 'backup_storage_status'" not in original and "backup_storage_status" not in text:
        raise SystemExit("PHASE86_BASE_PATCH_FAILED")
    path.write_text(text, encoding="utf-8")
    return "patched" if text != original else "already-present"


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print("PHASE86_SECURE_BACKUP_STORAGE_START")
    print("BACKUP_DIR=", BACKUP_DIR)
    print("URLS_PATCH=", patch_urls())
    print("BASE_MENU_PATCH=", patch_base())

    import django
    django.setup()

    from django.urls import reverse
    from django.test import Client
    from inventory.backup_storage_tools import verify_secure_backup_storage

    report = verify_secure_backup_storage()
    stats = report.get("stats", {})
    print("STORAGE_ROOT=", report.get("root"))
    print("STORAGE_OK=", report.get("ok"))
    print("TOTAL_ROWS=", stats.get("total_rows"))
    print("VERIFIED_FILES=", stats.get("verified_files"))
    print("HASH_MISMATCH=", stats.get("hash_mismatch"))
    print("MISSING_FILES=", stats.get("missing_files"))
    print("OUTSIDE_ROOT=", stats.get("outside_root"))
    print("INSIDE_PROJECT=", stats.get("inside_project"))
    print("RETENTION_KEEP=", report.get("retention", {}).get("keep_count"))
    print("RETENTION_DELETE_CANDIDATES=", report.get("retention", {}).get("delete_candidates"))
    print("REVERSE", reverse("inventory:backup_storage_status"))

    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    ok = 0
    for p in ["/backup-storage/", "/cisco-backups/", "/mikrotik-backups/"]:
        code = c.get(p).status_code
        print("URL", p, code)
        if code in (200, 302, 403):
            ok += 1
    print("URL_CHECK_OK=", ok)
    if ok != 3:
        raise SystemExit(2)
    if not report.get("ok"):
        raise SystemExit("PHASE86_STORAGE_VERIFY_FAILED")
    print("PHASE86_SECURE_BACKUP_STORAGE_OK")


if __name__ == "__main__":
    main()
