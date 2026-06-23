import os
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from inventory.models import Port, SfpMonitorSnapshot, Switch


TEST_SWITCH_NAME = "SWITCHMAP_PHASE28_SFP_TEST"
TEST_USERNAME = "phase28_sfp_admin"


def cleanup():
    Switch.objects.filter(name=TEST_SWITCH_NAME).delete()
    get_user_model().objects.filter(username=TEST_USERNAME).delete()


def make_snapshot(switch, port, interface_name, poll_time, **kwargs):
    data = {
        "switch": switch,
        "port": port,
        "interface_name": interface_name,
        "link_status": "connected",
        "speed": "10G",
        "media_type": "SFP-10GBase-LR",
        "health_state": SfpMonitorSnapshot.Health.HEALTHY,
        "health_note": "OK",
        "rx_power_dbm": Decimal("-3.00"),
        "tx_power_dbm": Decimal("-2.00"),
        "temperature_c": Decimal("35.00"),
    }
    data.update(kwargs)
    item = SfpMonitorSnapshot.objects.create(**data)
    item.poll_time = poll_time
    item.save(update_fields=["poll_time"])
    return item


def main():
    cleanup()
    now = timezone.now()
    user = get_user_model().objects.create_superuser(
        username=TEST_USERNAME,
        email="phase28@example.local",
        password="phase28-test-password",
    )
    switch = Switch.objects.create(
        name=TEST_SWITCH_NAME,
        management_ip="10.28.28.28",
        model="Cisco Catalyst 3850",
        snmp_enabled=False,
        ssh_enabled=False,
    )
    issue_port = Port.objects.create(
        switch=switch,
        interface_name="Te1/1/1",
        display_order=1001,
        status=Port.Status.UP,
    )
    healthy_port = Port.objects.create(
        switch=switch,
        interface_name="Te1/1/2",
        display_order=1002,
        status=Port.Status.UP,
    )

    make_snapshot(switch, issue_port, "Te1/1/1", now - timedelta(minutes=5))
    make_snapshot(
        switch,
        issue_port,
        "Te1/1/1",
        now,
        fcs_delta=2,
        input_error_delta=1,
        rx_power_dbm=Decimal("-21.00"),
        health_state=SfpMonitorSnapshot.Health.WARNING,
        health_note="CRC Increased | Input Error | Rx Power abnormal",
    )
    make_snapshot(switch, healthy_port, "Te1/1/2", now)

    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)

    data_response = client.get("/sfp-monitor/data/")
    assert data_response.status_code == 200, data_response.status_code
    data = data_response.json()
    assert data["summary"]["problem"] >= 1, data["summary"]
    issue_rows = [row for row in data["snapshots"] if row["switch"] == TEST_SWITCH_NAME and row["interface"] == "Te1/1/1"]
    assert issue_rows, data
    issue = issue_rows[0]
    assert "CRC Increased" in issue["issue_tags"], issue
    assert "Input Error" in issue["issue_tags"], issue
    assert "Rx Power abnormal" in issue["issue_tags"], issue
    assert issue["previous_poll"] != "-", issue
    assert issue["history"], issue

    dashboard_response = client.get("/sfp-monitor/data/?dashboard=1")
    assert dashboard_response.status_code == 200, dashboard_response.status_code
    dashboard = dashboard_response.json()["dashboard"]
    dashboard_ports = {(item["switch"], item["interface"]) for item in dashboard["items"]}
    assert (TEST_SWITCH_NAME, "Te1/1/1") in dashboard_ports, dashboard
    assert (TEST_SWITCH_NAME, "Te1/1/2") not in dashboard_ports, dashboard

    page_response = client.get("/sfp-monitor/")
    assert page_response.status_code == 200, page_response.status_code
    assert "CRC Increased" in page_response.content.decode("utf-8"), "SFP alert label not rendered"

    cleanup()
    print("PHASE28_SFP_ALERT_OK")


if __name__ == "__main__":
    main()
