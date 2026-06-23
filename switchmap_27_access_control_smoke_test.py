import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from inventory.models import Port, Switch


User = get_user_model()


def ensure_user(username, password, group_name=None, superuser=False):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"is_staff": superuser, "is_superuser": superuser},
    )
    user.set_password(password)
    user.is_active = True
    if superuser:
        user.is_staff = True
        user.is_superuser = True
    user.save()
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.clear()
        user.groups.add(group)
    return user


def ensure_sample_port():
    switch, _ = Switch.objects.get_or_create(
        name="SMOKE-SWITCH",
        defaults={
            "management_ip": "10.255.27.27",
            "model": "Cisco Catalyst 3850",
            "location": "Smoke Test",
            "port_count": 48,
            "is_active": True,
        },
    )
    port, _ = Port.objects.get_or_create(
        switch=switch,
        interface_name="Gi1/0/1",
        defaults={
            "display_order": 1,
            "status": Port.Status.DOWN,
            "port_mode": Port.PortMode.ACCESS,
        },
    )
    return switch, port


def assert_status(response, expected, label):
    if response.status_code != expected:
        raise AssertionError(f"{label}: expected={expected} actual={response.status_code}")


def main():
    for role_name in ["View Only", "Operator", "Admin"]:
        Group.objects.get_or_create(name=role_name)

    switch, port = ensure_sample_port()
    password = "SwitchMap27!"
    view_user = ensure_user("phase27_viewonly", password, "View Only")
    operator_user = ensure_user("phase27_operator", password, "Operator")
    admin_user = ensure_user("phase27_admin", password, "Admin")

    client = Client(HTTP_HOST="127.0.0.1")

    response = client.get(reverse("inventory:switch_list"))
    if response.status_code != 302 or "/accounts/login/" not in response.headers.get("Location", ""):
        raise AssertionError("anonymous dashboard redirect failed")

    client.login(username=view_user.username, password=password)
    assert_status(client.get(reverse("inventory:switch_list")), 200, "view dashboard")
    assert_status(client.get(reverse("inventory:switch_bulk_import")), 403, "view import blocked")
    response = client.post(
        reverse("inventory:ssh_action_preview"),
        {"port_id": port.id, "action": "set_description", "value": "test"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert_status(response, 403, "view ssh preview blocked")
    client.logout()

    client.login(username=operator_user.username, password=password)
    assert_status(client.get(reverse("inventory:port_edit", args=[port.id])), 200, "operator edit allowed")
    response = client.post(
        reverse("inventory:ssh_action_preview"),
        {"port_id": port.id, "action": "set_description", "value": "test"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert_status(response, 200, "operator allowed ssh preview")
    response = client.post(
        reverse("inventory:ssh_action_preview"),
        {"port_id": port.id, "action": "set_voice_vlan", "value": "10"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert_status(response, 403, "operator admin-only ssh blocked")
    client.logout()

    client.login(username=admin_user.username, password=password)
    assert_status(client.get(reverse("inventory:switch_bulk_import")), 200, "admin import allowed")
    response = client.post(
        reverse("inventory:ssh_action_preview"),
        {"port_id": port.id, "action": "set_voice_vlan", "value": "10"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert_status(response, 200, "admin ssh preview allowed")
    client.logout()

    print("PHASE27_ACCESS_CONTROL_OK")


if __name__ == "__main__":
    main()
