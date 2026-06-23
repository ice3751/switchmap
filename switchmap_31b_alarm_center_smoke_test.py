import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse

from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot, Switch
from inventory.views import _sync_alarm_notifications

settings.ALLOWED_HOSTS = list(set([*getattr(settings, "ALLOWED_HOSTS", []), "127.0.0.1", "localhost", "testserver"]))

PREFIX = "PHASE31B-"
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
    AlarmNotification.objects.filter(fingerprint__contains="phase31b").delete()
    Switch.objects.filter(name__startswith=PREFIX).delete()
    User.objects.filter(username__in=["phase31b_view", "phase31b_operator"]).delete()


def main():
    cleanup()
    make_user("phase31b_view", "View Only")
    make_user("phase31b_operator", "Operator")

    switch = Switch.objects.create(
        name=f"{PREFIX}SW1",
        management_ip="10.31.31.1",
        model="Cisco Catalyst 3850",
        snmp_enabled=True,
        snmp_last_error="PHASE31B SNMP timeout",
        discovery_last_error="",
        ssh_enabled=True,
        ssh_username="admin",
    )
    port = Port.objects.create(
        switch=switch,
        interface_name="Te1/1/1",
        display_order=1001,
        status=Port.Status.ERROR,
        port_mode=Port.PortMode.TRUNK,
        device_type=Port.DeviceType.UPLINK,
    )
    SfpMonitorSnapshot.objects.create(
        switch=switch,
        port=port,
        interface_name="Te1/1/1",
        link_status="connected",
        fcs_errors=20,
        input_errors=12,
        output_errors=0,
        fcs_delta=5,
        input_error_delta=3,
        output_error_delta=0,
        rx_power_dbm="-25.00",
        tx_power_dbm="0.10",
        temperature_c="32.00",
        health_state=SfpMonitorSnapshot.Health.WARNING,
        health_note="PHASE31B SFP issue",
    )

    summary = _sync_alarm_notifications()
    assert summary["active"] >= 3, summary
    assert AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, title="SNMP Down", switch=switch).exists()
    assert AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, category=AlarmNotification.Category.SFP, switch=switch).exists()

    view_client = Client(HTTP_HOST="127.0.0.1")
    assert view_client.login(username="phase31b_view", password=PASSWORD)
    response = view_client.get(reverse("inventory:alarm_center"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="ignore")
    assert "Alarm / Notification Center" in content
    assert "SNMP Down" in content
    assert ">Ack<" not in content

    alarm = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, switch=switch).first()
    response = view_client.post(reverse("inventory:alarm_acknowledge", args=[alarm.id]), HTTP_HOST="127.0.0.1")
    assert response.status_code == 403, response.status_code

    operator_client = Client(HTTP_HOST="127.0.0.1")
    assert operator_client.login(username="phase31b_operator", password=PASSWORD)
    response = operator_client.get(reverse("inventory:switch_list"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="ignore")
    assert "Alarm Center" in content
    assert "SNMP، CRC" in content

    response = operator_client.post(reverse("inventory:alarm_acknowledge", args=[alarm.id]), {"next": reverse("inventory:alarm_center")}, HTTP_HOST="127.0.0.1")
    assert response.status_code in (302, 303), response.status_code
    alarm.refresh_from_db()
    assert alarm.status == AlarmNotification.Status.ACKNOWLEDGED
    assert alarm.acknowledged_by == "phase31b_operator"

    cleanup()
    print("PHASE31B_ALARM_CENTER_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
