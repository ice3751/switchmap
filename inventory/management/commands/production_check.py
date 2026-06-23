import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate SwitchMap production readiness without executing restore."

    def add_arguments(self, parser):
        parser.add_argument("--strict-https", action="store_true")
        parser.add_argument("--skip-static", action="store_true")

    def handle(self, *args, **options):
        errors = []
        warnings = []

        if settings.DEBUG:
            errors.append("SWITCHMAP_DEBUG must be False.")

        if len(settings.SECRET_KEY or "") < 50 or str(settings.SECRET_KEY).startswith("switchmap-dev-key"):
            errors.append("SWITCHMAP_SECRET_KEY must be changed to a long production secret.")

        allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
        if not allowed_hosts:
            errors.append("SWITCHMAP_ALLOWED_HOSTS is empty.")
        if "*" in allowed_hosts:
            errors.append("SWITCHMAP_ALLOWED_HOSTS must not contain wildcard '*'.")
        if "testserver" in allowed_hosts:
            warnings.append("Remove testserver from SWITCHMAP_ALLOWED_HOSTS for the final server.")

        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            errors.append(f"SQLite database not found: {db_path}")
        else:
            try:
                connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                try:
                    integrity = connection.execute("PRAGMA integrity_check;").fetchone()[0]
                    if str(integrity).lower() != "ok":
                        errors.append(f"SQLite integrity check failed: {integrity}")
                finally:
                    connection.close()
            except sqlite3.Error as exc:
                errors.append(f"SQLite check failed: {exc}")

        static_root = Path(getattr(settings, "STATIC_ROOT", ""))
        if not options["skip_static"]:
            if not static_root.exists():
                errors.append(f"STATIC_ROOT does not exist. Run collectstatic: {static_root}")
            elif not any(static_root.iterdir()):
                errors.append(f"STATIC_ROOT is empty. Run collectstatic: {static_root}")

        backup_dir = Path(settings.SWITCHMAP_SQLITE_BACKUP_DIR)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            probe = backup_dir / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Backup directory is not writable: {backup_dir} | {exc}")

        try:
            import waitress  # noqa: F401
        except Exception as exc:
            errors.append(f"Waitress is not installed or importable: {exc}")

        if options["strict_https"]:
            if not settings.SECURE_SSL_REDIRECT:
                errors.append("SWITCHMAP_SECURE_SSL_REDIRECT must be True in strict HTTPS mode.")
            if not settings.SESSION_COOKIE_SECURE:
                errors.append("SWITCHMAP_SESSION_COOKIE_SECURE must be True in strict HTTPS mode.")
            if not settings.CSRF_COOKIE_SECURE:
                errors.append("SWITCHMAP_CSRF_COOKIE_SECURE must be True in strict HTTPS mode.")
            if settings.SECURE_HSTS_SECONDS <= 0:
                errors.append("SWITCHMAP_SECURE_HSTS_SECONDS must be positive in strict HTTPS mode.")
        else:
            if not settings.SECURE_SSL_REDIRECT:
                warnings.append("HTTPS redirect is disabled. This is acceptable only for trusted internal HTTP.")

        try:
            call_command("backup_sqlite", check_only=True, verbosity=0)
        except Exception as exc:
            errors.append(f"backup_sqlite --check-only failed: {exc}")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"PRODUCTION_WARN {warning}"))

        if errors:
            raise CommandError("PRODUCTION_CHECK_FAILED | " + " | ".join(errors))

        self.stdout.write(self.style.SUCCESS("PRODUCTION_CHECK_OK"))
