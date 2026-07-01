from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

URLS = ROOT / "inventory" / "urls.py"
BASE_TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "base.html"


def patch_urls():
    text = URLS.read_text(encoding="utf-8")
    changed = False
    if "cisco_backup_views" not in text:
        if "    backup_views,\n" in text:
            text = text.replace("    backup_views,\n", "    backup_views,\n    cisco_backup_views,\n")
        elif "from . import (" in text:
            text = text.replace("from . import (\n", "from . import (\n    cisco_backup_views,\n")
        else:
            raise RuntimeError("inventory.urls import block not found")
        changed = True

    if 'name="cisco_backup_center"' not in text:
        block = '''    path("cisco-backups/", backup_management_required(cisco_backup_views.cisco_backup_center_view), name="cisco_backup_center"),
    path("cisco-backups/run/", backup_management_required(cisco_backup_views.cisco_backup_run_view), name="cisco_backup_run"),
    path("cisco-backups/batch/", backup_management_required(cisco_backup_views.cisco_backup_batch_view), name="cisco_backup_batch"),
    path("cisco-backups/<str:backup_id>/", backup_management_required(cisco_backup_views.cisco_backup_detail_view), name="cisco_backup_detail"),
    path("cisco-backups/<str:backup_id>/download/", backup_management_required(cisco_backup_views.cisco_backup_download_view), name="cisco_backup_download"),
    path("cisco-backups/<str:backup_id>/validate-restore/", admin_required(cisco_backup_views.cisco_backup_validate_restore_view), name="cisco_backup_validate_restore"),
'''
        needle = '    path("backups/", backup_management_required(backup_views.backup_center_view), name="backup_center"),\n'
        if needle not in text:
            raise RuntimeError("backup_center URL anchor not found; no URL patch applied")
        text = text.replace(needle, block + needle)
        changed = True

    if changed:
        URLS.write_text(text, encoding="utf-8")
    return changed


def patch_base_template():
    if not BASE_TEMPLATE.exists():
        return False
    text = BASE_TEMPLATE.read_text(encoding="utf-8")
    changed = False

    if "cisco_backup_center" not in text:
        needle = "{% if swmap_can_manage_backups %}<a class=\"command-dropdown-item {% if current == 'backup_center' %}active{% endif %}\" href=\"{% url 'inventory:backup_center' %}\">Backup / Restore</a>{% endif %}"
        insert = needle + "\n                        {% if swmap_can_manage_backups %}<a class=\"command-dropdown-item {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}\" href=\"{% url 'inventory:cisco_backup_center' %}\">Cisco Backup Center</a>{% endif %}"
        if needle not in text:
            raise RuntimeError("base.html backup menu anchor not found; nav patch not applied")
        text = text.replace(needle, insert)
        changed = True

    summary_old = "current == 'backup_center' or current == 'config_backups'"
    summary_new = "current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'config_backups'"
    if summary_old in text and summary_new not in text:
        text = text.replace(summary_old, summary_new)
        changed = True

    if changed:
        BASE_TEMPLATE.write_text(text, encoding="utf-8")
    return changed


def main():
    print("PHASE84_CISCO_BACKUP_CENTER_APPLY_START")
    print("PATCH_URLS=", "patched" if patch_urls() else "already_ok")
    print("PATCH_BASE_NAV=", "patched" if patch_base_template() else "already_ok_or_skipped")
    import django
    django.setup()
    from inventory.cisco_backup_tools import setup_storage, CISCO_DIR, METADATA_DIR, LOG_DIR
    setup_storage()
    print("CISCO_DIR=", CISCO_DIR)
    print("METADATA_DIR=", METADATA_DIR)
    print("LOG_DIR=", LOG_DIR)
    print("PHASE84_CISCO_BACKUP_CENTER_APPLY_OK")


if __name__ == "__main__":
    main()
