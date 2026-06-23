import sqlite3
import zipfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Create a verified SQLite backup for SwitchMap."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--keep", type=int, default=None)
        parser.add_argument("--check-only", action="store_true")
        parser.add_argument("--plain", action="store_true")

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            raise CommandError(f"SQLite database not found: {db_path}")

        backup_dir = Path(options["output_dir"] or settings.SWITCHMAP_SQLITE_BACKUP_DIR)
        if not backup_dir.is_absolute():
            backup_dir = Path(settings.BASE_DIR) / backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

        keep = options["keep"]
        if keep is None:
            keep = int(settings.SWITCHMAP_SQLITE_BACKUP_RETENTION)

        if options["check_only"]:
            self.stdout.write(self.style.SUCCESS(f"BACKUP_CHECK_OK db={db_path} output={backup_dir} keep={keep}"))
            return

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        sqlite_backup = backup_dir / f"switchmap_sqlite_{timestamp}.sqlite3"
        zip_backup = backup_dir / f"switchmap_sqlite_{timestamp}.zip"

        source = sqlite3.connect(str(db_path))
        try:
            destination = sqlite3.connect(str(sqlite_backup))
            try:
                source.backup(destination)
                integrity = destination.execute("PRAGMA integrity_check;").fetchone()[0]
                if integrity.lower() != "ok":
                    raise CommandError(f"SQLite integrity check failed: {integrity}")
            finally:
                destination.close()
        finally:
            source.close()

        if not options["plain"]:
            with zipfile.ZipFile(zip_backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(sqlite_backup, sqlite_backup.name)
            sqlite_backup.unlink(missing_ok=True)
            final_path = zip_backup
        else:
            final_path = sqlite_backup

        if keep > 0:
            backups = sorted(backup_dir.glob("switchmap_sqlite_*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
            backups += sorted(backup_dir.glob("switchmap_sqlite_*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
            for old_backup in backups[keep:]:
                old_backup.unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f"BACKUP_OK {final_path}"))
