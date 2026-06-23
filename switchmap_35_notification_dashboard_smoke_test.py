import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse


django.setup()

from django.contrib.auth import get_user_model
from inventory.models import AlarmNotification, Port, Switch

User = get_user_model()
PREFIX = "PHASE35-"


def cleanup():
    AlarmNotification.objects.filter(fingerprint__startswith="phase35-").delete()
    Switch.objects.filter(name__startswith=PREFIX).delete()
    User.objects.filter(username="phase35_admin").delete()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    cleanup()
    admin = User.objects.create_superuser(
        username="phase35_admin",
        email="phase35@example.local",
        password="Phase35_AdminPass!",
    )
    switch = Switch.objects.create(
        name=f"{PREFIX}SW1",
        management_ip="10.35.0.1",
        model="Cisco Catalyst 3850",
        snmp_enabled=True,
        ssh_enabled=True,
        ssh_username="admin",
    )
    port = Port.objects.create(
        switch=switch,
        interface_name="Te1/1/4",
        display_order=1004,
        status=Port.Status.ERROR,
        port_mode=Port.PortMode.TRUNK,
    )
    AlarmNotification.objects.create(
        fingerprint="phase35-critical-sfp",
        source="SmokeTest",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.CRITICAL,
        status=AlarmNotification.Status.ACTIVE,
        title="Phase35 Critical SFP",
        message="Phase35 dashboard notification test",
        switch=switch,
        port=port,
    )
    AlarmNotification.objects.create(
        fingerprint="phase35-warning-snmp",
        source="SmokeTest",
        category=AlarmNotification.Category.SNMP,
        severity=AlarmNotification.Severity.WARNING,
        status=AlarmNotification.Status.ACTIVE,
        title="Phase35 SNMP Warning",
        message="Phase35 sidebar notification test",
        switch=switch,
    )

    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(admin)

    response = client.get(reverse("inventory:switch_list"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="replace")
    assert "sidebar-notification-box" in content
    assert "alarm-category-strip" in content
    assert "switch-alert-chip" in content
    assert "switch-alarm-inline-list" in content
    assert "Phase35 Critical SFP" in content
    assert "Phase35 SNMP Warning" in content

    response = client.get(reverse("inventory:alarm_center"), HTTP_HOST="127.0.0.1")
    assert response.status_code == 200, response.status_code
    alarm_content = response.content.decode("utf-8", errors="replace")
    assert "Phase35 Critical SFP" in alarm_content
    assert "Phase35 SNMP Warning" in alarm_content

    cleanup()
    print("PHASE35_NOTIFICATION_DASHBOARD_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
