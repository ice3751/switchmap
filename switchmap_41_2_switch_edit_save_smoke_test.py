import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model
from inventory.models import Switch

SMOKE_USER = "switchmap_phase41_2_smoke"


def cleanup_user():
    get_user_model().objects.filter(username=SMOKE_USER).delete()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    cleanup_user()

    switch, _ = Switch.objects.get_or_create(
        name="Phase41-2-Edit-Smoke",
        defaults={
            "management_ip": "10.41.2.1",
            "model": "MikroTik RB5009UG+S+",
            "vendor": Switch.Vendor.MIKROTIK,
            "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
            "device_role": Switch.DeviceRole.CORE_ROUTER,
            "site": "Smoke",
            "location": "Smoke Rack",
            "topology_position": 41,
            "winbox_port": 9169,
            "port_count": 9,
            "is_active": True,
        },
    )

    user = get_user_model().objects.create_superuser(username=SMOKE_USER, password="Phase41EditPass!", email="")
    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)

    url = reverse("inventory:switch_edit", args=[switch.id])
    response = client.get(url)
    assert response.status_code == 200, response.status_code
    html = response.content.decode("utf-8", errors="replace")
    assert "ذخیره تغییرات" in html, "switch edit form missing"

    data = {
        "name": switch.name,
        "management_ip": switch.management_ip,
        "model": "MikroTik RB5009UG+S+ Phase41.2",
        "vendor": Switch.Vendor.MIKROTIK,
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.CORE_ROUTER,
        "site": "Qazvin",
        "location": "Core Rack",
        "topology_position": 11,
        "winbox_port": 9169,
        "port_count": 9,
        "notes": "switch edit save smoke ok",
        "is_active": "on",
        "snmp_enabled": "on",
        "snmp_community": "public",
        "snmp_port": 161,
        "snmp_timeout": 2,
        "ssh_enabled": "on",
        "ssh_username": "admin",
        "ssh_port": 22,
    }
    response = client.post(url, data=data, follow=True)
    assert response.status_code == 200, response.status_code

    switch.refresh_from_db()
    assert switch.site == "Qazvin", f"site not saved: {switch.site}"
    assert switch.location == "Core Rack", f"location not saved: {switch.location}"
    assert switch.model.endswith("Phase41.2"), f"model not saved: {switch.model}"
    assert switch.snmp_enabled is True, "snmp_enabled not saved"

    cleanup_user()
    print("PHASE41_2_SWITCH_EDIT_SAVE_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup_user()
        raise
