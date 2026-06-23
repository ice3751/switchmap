import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from inventory.models import AlarmNotification, Port, Switch
from inventory.views import _sync_alarm_notifications

settings.ALLOWED_HOSTS = list(set([*getattr(settings, "ALLOWED_HOSTS", []), "127.0.0.1", "localhost", "testserver"]))

PREFIX = "PHASE31B1-"
PASSWORD = "SwitchMap@Test123"


def make_user(username, group_name):
    user, created = User.objects.get_or_create(username=username)
    if created or not user.has_usable_password():
        user.set_password(PASSWORD)
        user.save()
    user.groups.clear()
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


def cleanup():
    AlarmNotification.objects.filter(fingerprint__contains="phase31b1").delete()
    Switch.objects.filter(name__startswith=PREFIX).delete()
    User.objects.filter(username__in=["phase31b1_view", "phase31b1_operator"]).delete()


def main():
    cleanup()
    make_user("phase31b1_view", "View Only")
    make_user("phase31b1_operator", "Operator")

    switch = Switch.objects.create(
        name=f"{PREFIX}SW1",
        management_ip="10.31.32.1",
        model="Cisco Catalyst 3850",
        snmp_enabled=True,
        snmp_last_error="phase31b1 SNMP timeout",
        ssh_enabled=True,
        ssh_username="admin",
    )
    port = Port.objects.create(
        switch=switch,
        interface_name="Te1/1/1",
        display_order=1001,
        status=Port.Status.ERROR,
        port_mode=Port.PortMode.TRUNK,
    )

    _sync_alarm_notifications()
    alarm = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, switch=switch, title="SNMP Down").first()
    assert alarm is not None

    view_client = Client(HTTP_HOST="127.0.0.1")
    assert view_client.login(username="phase31b1_view", password=PASSWORD)
    response = view_client.get(reverse("inventory:alarm_center"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    view_content = response.content.decode("utf-8", errors="ignore")
    assert "alarm-bulk-form" not in view_content
    assert "Resolve selected" not in view_content

    operator_client = Client(HTTP_HOST="127.0.0.1")
    assert operator_client.login(username="phase31b1_operator", password=PASSWORD)

    response = operator_client.get(reverse("inventory:switch_list"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    dash_content = response.content.decode("utf-8", errors="ignore")
    assert "alarm-mini-dropdown" in dash_content
    assert "alarm-dashboard-card" not in dash_content

    response = operator_client.get(reverse("inventory:alarm_center"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    alarm_content = response.content.decode("utf-8", errors="ignore")
    assert "alarm-bulk-form" in alarm_content
    assert "Resolve selected" in alarm_content

    response = operator_client.post(
        reverse("inventory:alarm_resolve", args=[alarm.id]),
        {"next": reverse("inventory:alarm_center")},
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code in (302, 303), response.status_code
    alarm.refresh_from_db()
    assert alarm.status == AlarmNotification.Status.RESOLVED

    _sync_alarm_notifications()
    alarm.refresh_from_db()
    assert alarm.status == AlarmNotification.Status.RESOLVED

    bulk_a = AlarmNotification.objects.create(
        fingerprint="phase31b1-bulk-a",
        source="SmokeTest",
        category=AlarmNotification.Category.SYSTEM,
        severity=AlarmNotification.Severity.WARNING,
        status=AlarmNotification.Status.ACTIVE,
        title="Bulk A",
        message="Bulk action test A",
        switch=switch,
        port=port,
    )
    bulk_b = AlarmNotification.objects.create(
        fingerprint="phase31b1-bulk-b",
        source="SmokeTest",
        category=AlarmNotification.Category.SYSTEM,
        severity=AlarmNotification.Severity.WARNING,
        status=AlarmNotification.Status.ACTIVE,
        title="Bulk B",
        message="Bulk action test B",
        switch=switch,
        port=port,
    )

    response = operator_client.post(
        reverse("inventory:alarm_bulk_action"),
        {
            "bulk_action": "acknowledge",
            "alarm_ids": [str(bulk_a.id), str(bulk_b.id)],
            "next": reverse("inventory:alarm_center"),
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code in (302, 303), response.status_code
    bulk_a.refresh_from_db()
    bulk_b.refresh_from_db()
    assert bulk_a.status == AlarmNotification.Status.ACKNOWLEDGED
    assert bulk_b.status == AlarmNotification.Status.ACKNOWLEDGED
    assert bulk_a.acknowledged_by == "phase31b1_operator"

    response = operator_client.post(
        reverse("inventory:alarm_bulk_action"),
        {
            "bulk_action": "resolve",
            "alarm_ids": [str(bulk_a.id), str(bulk_b.id)],
            "next": reverse("inventory:alarm_center"),
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code in (302, 303), response.status_code
    bulk_a.refresh_from_db()
    bulk_b.refresh_from_db()
    assert bulk_a.status == AlarmNotification.Status.RESOLVED
    assert bulk_b.status == AlarmNotification.Status.RESOLVED
    assert bulk_a.resolved_at is not None

    cleanup()
    print("PHASE31B1_ALARM_ACTIONS_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
