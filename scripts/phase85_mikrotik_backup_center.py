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
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = BASE / "backups" / f"phase85_mikrotik_backup_{STAMP}"


def backup_file(path: Path):
    if path.exists():
        target = BACKUP_DIR / path.relative_to(BASE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def patch_urls():
    path = BASE / "inventory" / "urls.py"
    backup_file(path)
    text = path.read_text(encoding="utf-8")
    if "mikrotik_backup_views" not in text:
        if "    mikrotik_views,\n" in text:
            text = text.replace("    mikrotik_views,\n", "    mikrotik_views,\n    mikrotik_backup_views,\n")
        elif "mikrotik_views" in text:
            text = text.replace("mikrotik_views", "mikrotik_views, mikrotik_backup_views", 1)
        else:
            raise SystemExit("URL_IMPORT_PATCH_FAIL: mikrotik_views anchor not found")
    routes = '''    path("mikrotik-backups/", backup_management_required(mikrotik_backup_views.mikrotik_backup_center_view), name="mikrotik_backup_center"),
    path("mikrotik-backups/run/", backup_management_required(mikrotik_backup_views.mikrotik_backup_run_view), name="mikrotik_backup_run"),
    path("mikrotik-backups/batch/", backup_management_required(mikrotik_backup_views.mikrotik_backup_batch_view), name="mikrotik_backup_batch"),
    path("mikrotik-backups/<str:backup_id>/download/", admin_required(mikrotik_backup_views.mikrotik_backup_download_view), name="mikrotik_backup_download"),
    path("mikrotik-backups/<str:backup_id>/validate-restore/", admin_required(mikrotik_backup_views.mikrotik_backup_validate_restore_view), name="mikrotik_backup_validate_restore"),
    path("mikrotik-backups/<str:backup_id>/", backup_management_required(mikrotik_backup_views.mikrotik_backup_detail_view), name="mikrotik_backup_detail"),
'''
    if 'path("mikrotik-backups/"' not in text:
        if 'path("cisco-backups/<str:backup_id>/validate-restore/"' in text:
            marker = re.search(r'    path\("cisco-backups/<str:backup_id>/validate-restore/".*?\),\n', text)
            if marker:
                text = text[:marker.end()] + routes + text[marker.end():]
            else:
                text = text.replace('    path("backups/",', routes + '    path("backups/",', 1)
        else:
            text = text.replace('    path("backups/",', routes + '    path("backups/",', 1)
    if "mikrotik_backup_views" not in text:
        raise SystemExit("URL_IMPORT_PATCH_FAIL: mikrotik_backup_views not imported")
    if 'path("mikrotik-backups/"' not in text:
        raise SystemExit("URL_ROUTE_PATCH_FAIL: mikrotik-backups route not added")
    path.write_text(text, encoding="utf-8")
    return "patched"


def patch_base():
    path = BASE / "inventory" / "templates" / "inventory" / "base.html"
    if not path.exists():
        return "missing"
    backup_file(path)
    text = path.read_text(encoding="utf-8")
    original = text

    mikrotik_link = '''                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'mikrotik_backup_center' or current == 'mikrotik_backup_detail' %}active{% endif %}" href="{% url 'inventory:mikrotik_backup_center' %}">MikroTik Backup</a>{% endif %}'''
    cisco_link_center = '''                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}" href="{% url 'inventory:cisco_backup_center' %}">Cisco Backup Center</a>{% endif %}'''
    cisco_link_short = '''                        {% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}" href="{% url 'inventory:cisco_backup_center' %}">Cisco Backup</a>{% endif %}'''
    config_link = '''{% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'config_backups' or current == 'config_backup_detail' %}active{% endif %}" href="{% url 'inventory:config_backups' %}">Config Backup / Diff</a>{% endif %}'''
    backup_link = '''{% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == 'backup_center' %}active{% endif %}" href="{% url 'inventory:backup_center' %}">Backup / Restore</a>{% endif %}'''

    if "mikrotik_backup_center" not in text:
        if cisco_link_center in text:
            text = text.replace(cisco_link_center, cisco_link_center + "\n" + mikrotik_link, 1)
        elif cisco_link_short in text:
            text = text.replace(cisco_link_short, cisco_link_short + "\n" + mikrotik_link, 1)
        elif config_link in text:
            extra = "\n" + cisco_link_center + "\n" + mikrotik_link if "cisco_backup_center" not in text else "\n" + mikrotik_link
            text = text.replace(config_link, config_link + extra, 1)
        elif backup_link in text:
            extra = "\n" + cisco_link_center + "\n" + mikrotik_link if "cisco_backup_center" not in text else "\n" + mikrotik_link
            text = text.replace(backup_link, backup_link + extra, 1)
        else:
            raise SystemExit("BASE_PATCH_FAIL: backup menu anchor not found")

    summary_new = "current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'mikrotik_backup_center' or current == 'mikrotik_backup_detail' or current == 'config_backups' or current == 'config_backup_detail'"
    summary_patterns = [
        "current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'config_backups' or current == 'config_backup_detail'",
        "current == 'backup_center' or current == 'config_backups' or current == 'config_backup_detail'",
        "current == 'backup_center' or current == 'config_backups'",
    ]
    if "current == 'mikrotik_backup_center'" not in text:
        for pattern in summary_patterns:
            if pattern in text:
                text = text.replace(pattern, summary_new, 1)
                break

    # Guard against duplicate short Cisco link introduced by older test patch.
    if cisco_link_center in text and cisco_link_short in text:
        text = text.replace(cisco_link_short + "\n", "", 1)

    path.write_text(text, encoding="utf-8")
    return "patched" if text != original else "already-present"


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print("PHASE85_MIKROTIK_BACKUP_CENTER_START")
    print("BACKUP_DIR=", BACKUP_DIR)
    print("URLS_PATCH=", patch_urls())
    print("BASE_MENU_PATCH=", patch_base())
    # Cisco UI cleanup sanity
    cisco_tpl = BASE / "inventory" / "templates" / "inventory" / "cisco_backup_center.html"
    if cisco_tpl.exists():
        cisco_text = cisco_tpl.read_text(encoding="utf-8")
        print("CISCO_POLICY_VISIBLE=", "Policy" in cisco_text)
        print("CISCO_SCHEDULED_PANEL=", "phase84-scheduled-panel" in cisco_text)
        if "<h2>Policy</h2>" in cisco_text:
            raise SystemExit("CISCO_POLICY_PANEL_STILL_VISIBLE")
        if "PHASE85_CISCO_BACKUP_UI_CLEANUP" not in cisco_text:
            raise SystemExit("CISCO_UI_CLEANUP_MARKER_MISSING")
    # Storage setup without importing before URL patch.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from inventory.mikrotik_backup_tools import setup_storage, mikrotik_switches
    setup_storage()
    print("MIKROTIK_SWITCHES=", len(mikrotik_switches()))
    # Verify URL names are importable after patch.
    from django.urls import reverse
    for name in ("inventory:mikrotik_backup_center", "inventory:mikrotik_backup_run", "inventory:mikrotik_backup_batch"):
        print("REVERSE", name, reverse(name))
    from django.test import Client
    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    ok = 0
    for p in ["/mikrotik-backups/", "/cisco-backups/"]:
        code = c.get(p).status_code
        print("URL", p, code)
        if code in (200, 302, 403):
            ok += 1
    print("URL_CHECK_OK=", ok)
    if ok != 2:
        raise SystemExit(2)
    print("PHASE85_MIKROTIK_BACKUP_CENTER_OK")


if __name__ == "__main__":
    main()
