import io
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse


django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from inventory.access_control import ROLE_VIEW_ONLY
from inventory.models import SystemAuditLog

User = get_user_model()


def _make_valid_sqlite_bytes():
    temp_dir = Path(tempfile.mkdtemp(prefix="switchmap34_sqlite_"))
    sqlite_path = temp_dir / "restore.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute("CREATE TABLE auth_user (id integer primary key, username varchar(150));")
        connection.execute("CREATE TABLE inventory_switch (id integer primary key, name varchar(100));")
        connection.execute("CREATE TABLE inventory_port (id integer primary key, interface_name varchar(30));")
        connection.commit()
    finally:
        connection.close()
    data = sqlite_path.read_bytes()
    try:
        sqlite_path.unlink(missing_ok=True)
        temp_dir.rmdir()
    except Exception:
        pass
    return data


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    with tempfile.TemporaryDirectory(prefix="switchmap34_backup_") as backup_dir:
        with override_settings(SWITCHMAP_SQLITE_BACKUP_DIR=Path(backup_dir), SWITCHMAP_SQLITE_BACKUP_RETENTION=5):
            User.objects.filter(username__in=["switchmap_phase34_admin", "switchmap_phase34_viewer"]).delete()
            Group.objects.get_or_create(name=ROLE_VIEW_ONLY)
            admin = User.objects.create_superuser(
                username="switchmap_phase34_admin",
                email="phase34@example.local",
                password="Phase34AdminPass!",
            )
            viewer = User.objects.create_user(
                username="switchmap_phase34_viewer",
                password="Phase34ViewerPass!",
            )
            viewer.groups.add(Group.objects.get(name=ROLE_VIEW_ONLY))

            client = Client(HTTP_HOST="127.0.0.1")
            client.force_login(admin)

            response = client.get(reverse("inventory:backup_center"))
            assert response.status_code == 200, response.status_code
            content = response.content.decode("utf-8", errors="replace")
            assert "Backup / Restore Center" in content
            assert "Create Backup Now" in content

            response = client.post(reverse("inventory:backup_create"))
            assert response.status_code == 302, response.status_code
            backup_files = list(Path(backup_dir).glob("switchmap_sqlite_*.zip"))
            assert backup_files, "backup file was not created"

            response = client.get(reverse("inventory:backup_download", args=[backup_files[0].name]))
            assert response.status_code == 200, response.status_code

            sqlite_bytes = _make_valid_sqlite_bytes()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("restore.sqlite3", sqlite_bytes)
            zip_buffer.seek(0)
            zip_buffer.name = "restore_candidate.zip"

            response = client.post(
                reverse("inventory:backup_validate_restore"),
                {"restore_file": zip_buffer},
            )
            assert response.status_code == 302, response.status_code
            assert list((Path(backup_dir) / "restore_candidates").glob("restore_candidate_*.zip"))
            assert SystemAuditLog.objects.filter(action="backup_create", actor_username="switchmap_phase34_admin").exists()
            assert SystemAuditLog.objects.filter(action="restore_candidate_valid", actor_username="switchmap_phase34_admin").exists()

            client.force_login(viewer)
            response = client.get(reverse("inventory:backup_center"))
            assert response.status_code == 403, response.status_code

    User.objects.filter(username__in=["switchmap_phase34_admin", "switchmap_phase34_viewer"]).delete()
    print("PHASE34_BACKUP_CENTER_OK")


if __name__ == "__main__":
    main()
