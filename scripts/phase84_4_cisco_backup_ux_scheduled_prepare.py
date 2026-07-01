from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(r"C:\SwitchMap")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _patch_base_menu() -> bool:
    base = PROJECT_ROOT / "inventory" / "templates" / "inventory" / "base.html"
    if not base.exists():
        raise SystemExit(f"BASE_NOT_FOUND={base}")
    text = base.read_text(encoding="utf-8")
    changed = False

    if "cisco_backup_center" not in text:
        needle = """{% if swmap_can_manage_backups %}<a class=\"command-dropdown-item {% if current == 'config_backups' or current == 'config_backup_detail' %}active{% endif %}\" href=\"{% url 'inventory:config_backups' %}\">Config Backup / Diff</a>{% endif %}"""
        insert = needle + "\n" + """                        {% if swmap_can_manage_backups %}<a class=\"command-dropdown-item {% if current == 'cisco_backup_center' or current == 'cisco_backup_detail' %}active{% endif %}\" href=\"{% url 'inventory:cisco_backup_center' %}\">Cisco Backup Center</a>{% endif %}"""
        if needle not in text:
            raise SystemExit("BASE_PATCH_FAIL: Config Backup anchor not found")
        text = text.replace(needle, insert, 1)
        changed = True

    summary_old = "current == 'backup_center' or current == 'config_backups' or current == 'config_backup_detail'"
    summary_new = "current == 'backup_center' or current == 'cisco_backup_center' or current == 'cisco_backup_detail' or current == 'config_backups' or current == 'config_backup_detail'"
    if summary_old in text and summary_new not in text:
        text = text.replace(summary_old, summary_new, 1)
        changed = True

    if changed:
        backup = base.with_suffix(".html.phase84_4_bak")
        if not backup.exists():
            backup.write_text(base.read_text(encoding="utf-8"), encoding="utf-8")
        base.write_text(text, encoding="utf-8")
    return changed


def _verify_files() -> None:
    required = [
        PROJECT_ROOT / "inventory" / "cisco_backup_views.py",
        PROJECT_ROOT / "inventory" / "cisco_backup_tools.py",
        PROJECT_ROOT / "inventory" / "templates" / "inventory" / "cisco_backup_center.html",
        PROJECT_ROOT / "inventory" / "templates" / "inventory" / "cisco_backup_detail.html",
        PROJECT_ROOT / "inventory" / "management" / "commands" / "cisco_backup_scheduled.py",
    ]
    for path in required:
        if not path.exists():
            raise SystemExit(f"MISSING={path}")
    center = (PROJECT_ROOT / "inventory" / "templates" / "inventory" / "cisco_backup_center.html").read_text(encoding="utf-8")
    for marker in ("PHASE84_4_CISCO_BACKUP_UX_SCHEDULED_PREPARE", "Scheduled Backup Prepare", "phase84-cisco-center"):
        if marker not in center:
            raise SystemExit(f"MARKER_MISSING={marker}")


def main() -> None:
    print("PHASE84_4_CISCO_BACKUP_UX_SCHEDULED_PREPARE_START")
    _verify_files()
    base_changed = _patch_base_menu()
    print("BASE_MENU_PATCH=", "changed" if base_changed else "already-present")

    import django
    django.setup()

    from django.core.management import call_command
    from django.test import Client
    from django.urls import reverse
    from inventory.cisco_backup_tools import list_backups

    call_command("check")
    urls = [
        reverse("inventory:cisco_backup_center"),
    ]
    rows = list_backups(limit=20)
    if rows:
        urls.append(reverse("inventory:cisco_backup_detail", kwargs={"backup_id": rows[0]["backup_id"]}))
    client = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    ok = 0
    for url in urls:
        status = client.get(url).status_code
        print(f"URL {url} {status}")
        if status in (200, 302):
            ok += 1
    if ok != len(urls):
        raise SystemExit("URL_CHECK_FAIL")
    print("URL_CHECK_OK=", ok)
    print("RECENT_BACKUPS=", len(rows))
    print("PHASE84_4_CISCO_BACKUP_UX_SCHEDULED_PREPARE_OK")


if __name__ == "__main__":
    main()
