import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django
    from django.conf import settings
    from django.core.management import call_command
except Exception as exc:
    print(f"PHASE29_IMPORT_FAILED: {exc}")
    sys.exit(1)


def fail(message):
    print(f"PHASE29_PRODUCTION_FAILED: {message}")
    sys.exit(1)


django.setup()

if settings.DEBUG is not False:
    fail("DEBUG must be False")

if len(settings.SECRET_KEY) < 50 or settings.SECRET_KEY.startswith("switchmap-dev-key"):
    fail("SECRET_KEY must be production-grade")

if not settings.ALLOWED_HOSTS:
    fail("ALLOWED_HOSTS is empty")

if "*" in settings.ALLOWED_HOSTS:
    fail("ALLOWED_HOSTS must not contain wildcard")

if not settings.SECURE_SSL_REDIRECT:
    fail("SECURE_SSL_REDIRECT must be True")

if not settings.SESSION_COOKIE_SECURE:
    fail("SESSION_COOKIE_SECURE must be True")

if not settings.CSRF_COOKIE_SECURE:
    fail("CSRF_COOKIE_SECURE must be True")

if settings.SECURE_HSTS_SECONDS <= 0:
    fail("SECURE_HSTS_SECONDS must be positive")

if not settings.SECURE_HSTS_INCLUDE_SUBDOMAINS:
    fail("SECURE_HSTS_INCLUDE_SUBDOMAINS must be True for strict deploy checks")

if not settings.SECURE_HSTS_PRELOAD:
    fail("SECURE_HSTS_PRELOAD must be True for strict deploy checks")

if not getattr(settings, "STATIC_ROOT", None):
    fail("STATIC_ROOT is not configured")

if not getattr(settings, "SWITCHMAP_SQLITE_BACKUP_DIR", None):
    fail("SQLite backup directory is not configured")

call_command("backup_sqlite", check_only=True, verbosity=0)
print("PHASE29_PRODUCTION_OK")
