import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse

from inventory.models import Port, PortActionLog, Switch

settings.ALLOWED_HOSTS = list(set([*getattr(settings, "ALLOWED_HOSTS", []), "127.0.0.1", "localhost", "testserver"]))


def make_user(username, group_name):
    user, created = User.objects.get_or_create(username=username)
    if created or not user.has_usable_password():
        user.set_password("SwitchMap@Test123")
        user.save()
    user.groups.clear()
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


view_user = make_user("phase31a_view", "View Only")
operator_user = make_user("phase31a_operator", "Operator")

switch, _ = Switch.objects.get_or_create(
    name="PHASE31A-BULK-TEST",
    defaults={
        "management_ip": "10.255.31.1",
        "model": "Cisco Catalyst 3850",
        "port_count": 2,
        "ssh_enabled": True,
        "ssh_username": "admin",
    },
)
if str(switch.management_ip) != "10.255.31.1":
    switch.management_ip = "10.255.31.1"
    switch.ssh_enabled = True
    switch.ssh_username = "admin"
    switch.save()

port1, _ = Port.objects.get_or_create(
    switch=switch,
    interface_name="Gi1/0/1",
    defaults={"display_order": 1, "status": Port.Status.DOWN, "port_mode": Port.PortMode.ACCESS},
)
port2, _ = Port.objects.get_or_create(
    switch=switch,
    interface_name="Gi1/0/2",
    defaults={"display_order": 2, "status": Port.Status.DOWN, "port_mode": Port.PortMode.ACCESS},
)

operator_client = Client(HTTP_HOST="127.0.0.1")
assert operator_client.login(username="phase31a_operator", password="SwitchMap@Test123")

table_url = reverse("inventory:switch_ports_table", args=[switch.id])
response = operator_client.get(table_url, HTTP_HOST="127.0.0.1")
assert response.status_code == 200, response.status_code
content = response.content.decode("utf-8", errors="ignore")
assert "Bulk SSH" in content
assert "data-bulk-ssh-form" in content

bulk_url = reverse("inventory:switch_bulk_ssh_action", args=[switch.id])
response = operator_client.post(
    bulk_url,
    {
        "port_ids": [str(port1.id), str(port2.id)],
        "action": "set_description",
        "value": "PHASE31A-SMOKE",
        "ssh_username": "admin",
        "ssh_password": "",
        "confirmed": "1",
    },
    HTTP_HOST="127.0.0.1",
    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
)
assert response.status_code == 400, response.status_code
payload = response.json()
assert payload.get("ok") is False
assert PortActionLog.objects.filter(switch=switch, action="bulk_set_description").exists()

view_client = Client(HTTP_HOST="127.0.0.1")
assert view_client.login(username="phase31a_view", password="SwitchMap@Test123")
response = view_client.get(table_url, HTTP_HOST="127.0.0.1")
assert response.status_code == 200, response.status_code
content = response.content.decode("utf-8", errors="ignore")
assert "data-bulk-ssh-form" not in content

response = view_client.post(
    bulk_url,
    {
        "port_ids": [str(port1.id)],
        "action": "set_description",
        "value": "DENIED",
        "ssh_username": "admin",
        "ssh_password": "x",
        "confirmed": "1",
    },
    HTTP_HOST="127.0.0.1",
    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
)
assert response.status_code == 403, response.status_code

print("PHASE31A_BULK_SSH_OK")
