from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name.lower() == "patches":
    ROOT = ROOT.parent

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
SETTINGS = ROOT / "config" / "settings.py"
VIEWS = ROOT / "inventory" / "views.py"
DB = ROOT / "db.sqlite3"
BACKUP_DIR = ROOT / "backups" / "sqlite"


def backup_file(path: Path) -> Path:
    backup = path.with_name(path.name + f".bak-phase41-5-{TS}")
    shutil.copy2(path, backup)
    return backup


def patch_settings() -> None:
    if not SETTINGS.exists():
        raise FileNotFoundError(f"Missing settings.py: {SETTINGS}")
    backup = backup_file(SETTINGS)
    text = SETTINGS.read_text(encoding="utf-8")

    marker = "# Phase 41.5 - allow large admin/device forms"
    block = (
        "\n"
        f"{marker}\n"
        "DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get('SWITCHMAP_DATA_UPLOAD_MAX_NUMBER_FIELDS', '20000'))\n"
    )

    text = re.sub(
        r"(?m)^DATA_UPLOAD_MAX_NUMBER_FIELDS\s*=.*$",
        "DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get('SWITCHMAP_DATA_UPLOAD_MAX_NUMBER_FIELDS', '20000'))",
        text,
    )
    if "DATA_UPLOAD_MAX_NUMBER_FIELDS" not in text:
        text = text.rstrip() + block + "\n"

    if "import os" not in text and "from os import" not in text:
        text = "import os\n" + text

    SETTINGS.write_text(text, encoding="utf-8")
    print(f"SETTINGS_PATCH_OK backup={backup}")


def patch_views_import() -> None:
    if not VIEWS.exists():
        print("VIEWS_PATCH_SKIPPED missing inventory/views.py")
        return
    text = VIEWS.read_text(encoding="utf-8")
    if "SwitchForm" not in text:
        print("VIEWS_PATCH_SKIPPED SwitchForm not used")
        return
    if "import SwitchForm" in text or " SwitchForm" in text.split("\n", 40)[0:40].__str__():
        print("VIEWS_PATCH_OK SwitchForm import already present")
        return

    backup = backup_file(VIEWS)
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("from .forms import "):
            if "SwitchForm" not in line:
                lines[i] = line.rstrip() + ", SwitchForm"
                changed = True
            break
    if not changed:
        lines.insert(0, "from .forms import SwitchForm")
        changed = True
    VIEWS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"VIEWS_PATCH_OK backup={backup}")


def backup_db() -> None:
    if not DB.exists():
        print("DB_BACKUP_SKIPPED missing db.sqlite3")
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"db_pre_phase41_5_{TS}.sqlite3"
    shutil.copy2(DB, target)
    print(f"DB_BACKUP_OK {target}")


def cleanup_test_switches() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(ROOT))
    import django
    django.setup()
    from inventory.models import Switch

    patterns = ["smoke", "test", "demo", "sample"]
    candidates = []
    for sw in Switch.objects.all().order_by("id"):
        name = (getattr(sw, "name", "") or "").lower()
        hostname = (getattr(sw, "hostname", "") or "").lower()
        if any(p in name or p in hostname for p in patterns):
            candidates.append(sw)

    count = len(candidates)
    for sw in candidates:
        print(f"DELETE_TEST_SWITCH id={sw.id} name={getattr(sw, 'name', '')} ip={getattr(sw, 'management_ip', '')}")
        sw.delete()
    print(f"TEST_SWITCH_CLEANUP_OK deleted={count}")


def main() -> None:
    print("PHASE41_5_START")
    backup_db()
    patch_settings()
    patch_views_import()
    cleanup_test_switches()
    print("PHASE41_5_PATCH_OK")


if __name__ == "__main__":
    main()
