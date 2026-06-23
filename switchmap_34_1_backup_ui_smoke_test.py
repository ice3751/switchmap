import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse


django.setup()

from django.contrib.auth import get_user_model
from inventory.models import SystemAuditLog

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    with tempfile.TemporaryDirectory(prefix="switchmap34_1_backup_") as backup_dir:
        with override_settings(SWITCHMAP_SQLITE_BACKUP_DIR=Path(backup_dir), SWITCHMAP_SQLITE_BACKUP_RETENTION=5):
            User.objects.filter(username="switchmap_phase34_1_admin").delete()
            admin = User.objects.create_superuser(
                username="switchmap_phase34_1_admin",
                email="phase34_1@example.local",
                password="Phase34_1_AdminPass!",
            )
            client = Client(HTTP_HOST="127.0.0.1")
            client.force_login(admin)

            response = client.post(reverse("inventory:backup_create"))
            assert response.status_code == 302, response.status_code

            response = client.get(reverse("inventory:backup_center"))
            assert response.status_code == 200, response.status_code
            content = response.content.decode("utf-8", errors="replace")
            assert "backup-page-stack" in content
            assert "backup-compact-summary" in content
            assert "data-backup-list" in content
            assert "Backup / Restore Center" in content
            assert "Validate Restore Candidate" in content
            assert "backup-table" not in content
            assert SystemAuditLog.objects.filter(action="backup_create", actor_username="switchmap_phase34_1_admin").exists()

    User.objects.filter(username="switchmap_phase34_1_admin").delete()
    print("PHASE34_1_BACKUP_UI_OK")


if __name__ == "__main__":
    main()
