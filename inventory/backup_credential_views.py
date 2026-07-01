from __future__ import annotations

from django.shortcuts import render

from .secure_credentials import CREDENTIAL_PROFILES, credential_status
from .models import Switch


def _switch_text(switch: Switch) -> str:
    return " ".join([
        str(getattr(switch, "vendor", "") or ""),
        str(getattr(switch, "device_family", "") or ""),
        str(getattr(switch, "model", "") or ""),
        str(getattr(switch, "name", "") or ""),
    ]).lower()


def _is_cisco_switch(switch: Switch) -> bool:
    return any(token in _switch_text(switch) for token in ("cisco", "catalyst", "nexus", "3850"))


def _is_mikrotik_switch(switch: Switch) -> bool:
    text = _switch_text(switch)
    return any(token in text for token in ("mikrotik", "routeros", "rb", "crs", "hex", "hap", "ax3", "cap-"))


def _sample_ids(profile: str, limit: int = 2) -> list[int]:
    items = []
    for switch in Switch.objects.filter(is_active=True, ssh_enabled=True).order_by("topology_position", "name"):
        if profile == "cisco" and _is_cisco_switch(switch):
            items.append(int(switch.id))
        elif profile == "mikrotik" and _is_mikrotik_switch(switch):
            items.append(int(switch.id))
        if len(items) >= limit:
            break
    return items


def backup_credential_prepare_view(request):
    profiles = []
    for profile in sorted(CREDENTIAL_PROFILES.keys()):
        status = credential_status(profile)
        ids = _sample_ids(profile)
        if profile == "cisco":
            scheduled_selected = "python manage.py cisco_backup_scheduled " + " ".join(f"--switch-id {i}" for i in ids) + " --type running-config --type startup-config"
            scheduled_all = "python manage.py cisco_backup_scheduled --all --type running-config --type startup-config"
            schtasks = 'schtasks /Create /TN "SwitchMap Cisco Backup" /SC DAILY /ST 23:45 /TR "\\\"C:\\SwitchMap\\venv\\Scripts\\python.exe\\\" \\\"C:\\SwitchMap\\manage.py\\\" cisco_backup_scheduled --all --type running-config --type startup-config" /RU "%USERNAME%"'
        else:
            scheduled_selected = "python manage.py mikrotik_backup_scheduled " + " ".join(f"--switch-id {i}" for i in ids) + " --type export"
            scheduled_all = "python manage.py mikrotik_backup_scheduled --all --type export"
            schtasks = 'schtasks /Create /TN "SwitchMap MikroTik Backup" /SC DAILY /ST 23:55 /TR "\\\"C:\\SwitchMap\\venv\\Scripts\\python.exe\\\" \\\"C:\\SwitchMap\\manage.py\\\" mikrotik_backup_scheduled --all --type export" /RU "%USERNAME%"'
        profiles.append({
            "name": profile,
            "title": "Cisco" if profile == "cisco" else "MikroTik",
            "status": status,
            "sample_ids": ids,
            "commands": {
                "set": f"python manage.py set_ssh_monitor_credentials --profile {profile}",
                "status": f"python manage.py set_ssh_monitor_credentials --profile {profile} --status",
                "migrate": f"python manage.py set_ssh_monitor_credentials --profile {profile} --migrate-legacy",
                "test": f"python manage.py set_ssh_monitor_credentials --profile {profile} --test",
                "scheduled_selected": scheduled_selected,
                "scheduled_all": scheduled_all,
                "schtasks": schtasks,
            },
        })
    context = {
        "current": "backup_credential_prepare",
        "profiles": profiles,
        "strict_check": "python manage.py scheduled_backup_credential_check --profile all --strict",
        "note": "Credential با Windows DPAPI و همان Windows User قابل بازشدن است؛ رمز داخل فرم وب یا فایل پروژه ذخیره نمی‌شود.",
    }
    return render(request, "inventory/backup_credential_prepare.html", context)
