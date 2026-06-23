import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def fail(message):
    print(f"PHASE37_PRODUCTION_FAILED: {message}")
    sys.exit(1)


try:
    import django
    from django.conf import settings
    from django.core.management import call_command
except Exception as exc:
    fail(f"django import failed: {exc}")


django.setup()

root = Path(__file__).resolve().parent
required_files = [
    "run_waitress.py",
    "scripts/phase37_prepare_production.cmd",
    "scripts/run_waitress.cmd",
    "scripts/install_waitress_startup_task.cmd",
    "scripts/install_backup_task.cmd",
    "scripts/install_service_nssm.cmd",
    "docs/PHASE37_PRODUCTION.md",
    "inventory/management/commands/production_check.py",
]

for relative_path in required_files:
    if not (root / relative_path).exists():
        fail(f"missing file: {relative_path}")

requirements = (root / "requirements.txt").read_text(encoding="utf-8")
if "waitress==3.0.2" not in requirements:
    fail("waitress is missing from requirements.txt")

try:
    import waitress  # noqa: F401
except Exception as exc:
    fail(f"waitress import failed: {exc}")

if not getattr(settings, "STATIC_ROOT", None):
    fail("STATIC_ROOT is not configured")

if not getattr(settings, "SWITCHMAP_SQLITE_BACKUP_DIR", None):
    fail("SWITCHMAP_SQLITE_BACKUP_DIR is not configured")

if not hasattr(settings, "SWITCHMAP_WAITRESS_HOST"):
    fail("SWITCHMAP_WAITRESS_HOST is not configured")

if not hasattr(settings, "SWITCHMAP_LOG_DIR"):
    fail("SWITCHMAP_LOG_DIR is not configured")

call_command("check", verbosity=0)
call_command("backup_sqlite", check_only=True, verbosity=0)
print("PHASE37_PRODUCTION_PACKAGE_OK")
