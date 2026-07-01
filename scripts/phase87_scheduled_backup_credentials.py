from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

MARKER = "PHASE87_SCHEDULED_BACKUP_CREDENTIAL_PREPARE"


def backup_file(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    target = backup_dir / path.relative_to(PROJECT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def patch_urls(backup_dir: Path) -> str:
    path = PROJECT / "inventory" / "urls.py"
    backup_file(path, backup_dir)
    text = path.read_text(encoding="utf-8")
    changed = False
    if "backup_credential_views" not in text:
        marker = "    backup_views,\n"
        if marker not in text:
            raise RuntimeError("URL import anchor not found: backup_views")
        text = text.replace(marker, marker + "    backup_credential_views,\n", 1)
        changed = True
    route = '    path("backup-credentials/", backup_management_required(backup_credential_views.backup_credential_prepare_view), name="backup_credential_prepare"),\n'
    if "backup-credentials/" not in text:
        anchors = [
            '    path("backup-storage/",',
            '    path("mikrotik-backups/",',
            '    path("cisco-backups/",',
            '    path("backups/",',
        ]
        for anchor in anchors:
            idx = text.find(anchor)
            if idx >= 0:
                text = text[:idx] + route + text[idx:]
                changed = True
                break
        else:
            raise RuntimeError("URL route anchor not found")
    if changed:
        path.write_text(text, encoding="utf-8")
        return "patched"
    return "already-present"


def patch_base(backup_dir: Path) -> str:
    path = PROJECT / "inventory" / "templates" / "inventory" / "base.html"
    if not path.exists():
        return "base-missing-skip"
    backup_file(path, backup_dir)
    text = path.read_text(encoding="utf-8")
    if "backup_credential_prepare" in text:
        return "already-present"
    link = '{% if swmap_can_manage_backups %}<a class="command-dropdown-item {% if current == \'backup_credential_prepare\' %}active{% endif %}" href="{% url \'inventory:backup_credential_prepare\' %}">Scheduled Credentials</a>{% endif %}\n                        '
    anchors = [
        "MikroTik Backup",
        "Cisco Backup",
        "Backup Storage",
        "Config Backup / Diff",
        "Backup / Restore",
    ]
    for token in anchors:
        pos = text.find(token)
        if pos < 0:
            continue
        end = text.find("\n", pos)
        if end < 0:
            continue
        text = text[:end+1] + "                        " + link + text[end+1:]
        path.write_text(text, encoding="utf-8")
        return "patched"
    return "anchor-not-found-skip"


def main() -> int:
    print("PHASE87_SCHEDULED_BACKUP_CREDENTIALS_START")
    backup_dir = PROJECT / "backups" / f"phase87_scheduled_backup_credentials_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    print("BACKUP_DIR=", backup_dir)
    print("URLS_PATCH=", patch_urls(backup_dir))
    print("BASE_MENU_PATCH=", patch_base(backup_dir))

    import django
    django.setup()
    from django.core.management import call_command
    from django.test import Client
    from django.urls import reverse
    from inventory.secure_credentials import credential_status

    call_command("check")
    print("REVERSE", reverse("inventory:backup_credential_prepare"))
    for profile in ("cisco", "mikrotik"):
        status = credential_status(profile)
        print(f"{profile.upper()}_CREDENTIAL_EXISTS=", status.get("exists"))
        print(f"{profile.upper()}_CREDENTIAL_LOCATION=", status.get("location"))
        print(f"{profile.upper()}_CREDENTIAL_FILE=", status.get("file"))
    c = Client(HTTP_HOST="it-tools.winac-co.com:8000")
    checks = ["/backup-credentials/", "/cisco-backups/", "/mikrotik-backups/", "/backup-storage/"]
    ok = 0
    for url in checks:
        response = c.get(url)
        print("URL", url, response.status_code)
        if response.status_code in (200, 302):
            ok += 1
    if ok != len(checks):
        print("PHASE87_URL_CHECK_FAIL")
        return 2
    call_command("scheduled_backup_credential_check", "--profile", "all")
    print("PHASE87_SCHEDULED_BACKUP_CREDENTIALS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
