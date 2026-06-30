from __future__ import annotations

from django.shortcuts import render

from .backup_storage_tools import verify_secure_backup_storage

PHASE86_MARKER = "PHASE86_SECURE_BACKUP_STORAGE"


def backup_storage_status_view(request):
    report = verify_secure_backup_storage()
    return render(request, "inventory/backup_storage_status.html", {"report": report, "phase86_marker": PHASE86_MARKER})
