import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from inventory.models import Switch

HOSTS = {"it-tools", "it-tools.winac-co.com", "192.168.0.11", "127.0.0.1", "localhost"}
missing = [host for host in HOSTS if host not in settings.ALLOWED_HOSTS]
assert not missing, f"ALLOWED_HOSTS_MISSING {missing} current={settings.ALLOWED_HOSTS}"

USER = "switchmap_phase41_4_admin"
PASS = "Phase41FixPass!"
user_model = get_user_model()
user_model.objects.filter(username=USER).delete()
admin = user_model.objects.create_superuser(username=USER, password=PASS, email="")

switch, created = Switch.objects.get_or_create(
    name="Phase41-4-Edit-Smoke",
    defaults={
        "management_ip": "10.241.4.4",
        "model": "Smoke Test Device",
        "vendor": Switch.Vendor.MIKROTIK,
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.UNKNOWN,
        "site": "Smoke",
        "location": "Smoke",
        "topology_position": 240,
        "winbox_port": 9169,
        "needs_review": True,
        "port_count": 1,
        "is_active": True,
        "snmp_enabled": False,
        "snmp_community": "",
        "snmp_port": 161,
        "snmp_timeout": 2,
        "ssh_enabled": False,
        "ssh_username": "admin",
        "ssh_port": 22,
    },
)

client = Client(HTTP_HOST="it-tools.winac-co.com")
assert client.login(username=USER, password=PASS), "LOGIN_FAILED"

admin_url = f"/admin/inventory/switch/{switch.id}/change/"
resp = client.get(admin_url, HTTP_HOST="it-tools.winac-co.com")
assert resp.status_code == 200, f"ADMIN_CHANGE_GET_FAILED status={resp.status_code}"

edit_url = reverse("inventory:switch_edit", args=[switch.id])
post_data = {
    "name": switch.name,
    "management_ip": switch.management_ip,
    "model": switch.model,
    "vendor": Switch.Vendor.MIKROTIK,
    "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
    "device_role": Switch.DeviceRole.REMOTE_OFFICE,
    "site": "Smoke-Site-Updated",
    "location": "Smoke-Location-Updated",
    "topology_position": "241",
    "winbox_port": "9169",
    "port_count": "1",
    "notes": "Phase41.4 edit save smoke update",
    "snmp_community": "",
    "snmp_port": "161",
    "snmp_timeout": "2",
    "ssh_username": "admin",
    "ssh_port": "22",
    "is_active": "on",
}
resp = client.post(edit_url, data=post_data, HTTP_HOST="it-tools.winac-co.com")
assert resp.status_code in (302, 200), f"SWITCH_EDIT_POST_FAILED status={resp.status_code} body={resp.content[:200]!r}"

switch.refresh_from_db()
assert switch.site == "Smoke-Site-Updated", "SWITCH_EDIT_SAVE_FAILED"
assert switch.device_role == Switch.DeviceRole.REMOTE_OFFICE, "SWITCH_EDIT_ROLE_SAVE_FAILED"

user_model.objects.filter(username=USER).delete()
Switch.objects.filter(name="Phase41-4-Edit-Smoke").delete()
print("PHASE41_4_ADMIN_HOST_AND_EDIT_OK")
