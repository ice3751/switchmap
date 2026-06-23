import os
from io import StringIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model

from inventory.management.commands.seed_mikrotik_devices import MIKROTIK_DEVICES
from inventory.models import Switch
from inventory.views import _build_topology_payload


SMOKE_USER = "switchmap_phase40_smoke"
EXPECTED = {
    "RB5009": Switch.DeviceRole.CORE_ROUTER,
    "CRS354": Switch.DeviceRole.CORE_SWITCH,
    "Hex-S": Switch.DeviceRole.EDGE_ROUTER,
    "RB2011-Iranmall": Switch.DeviceRole.REMOTE_OFFICE,
    "AliHome": Switch.DeviceRole.REMOTE_OFFICE,
    "AX3-Karaj": Switch.DeviceRole.REMOTE_OFFICE,
    "Cap-Managment": Switch.DeviceRole.ACCESS_POINT,
    "Cap-Tolid": Switch.DeviceRole.ACCESS_POINT,
    "Cap-Edari": Switch.DeviceRole.ACCESS_POINT,
    "cap-patrol": Switch.DeviceRole.ACCESS_POINT,
}


def cleanup_user():
    get_user_model().objects.filter(username=SMOKE_USER).delete()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    cleanup_user()
    assert len(MIKROTIK_DEVICES) >= 10, "MikroTik seed list is incomplete"

    call_command("seed_mikrotik_devices", stdout=StringIO())

    for name, role in EXPECTED.items():
        switch = Switch.objects.get(name=name)
        assert switch.vendor == Switch.Vendor.MIKROTIK, f"{name} vendor invalid"
        assert switch.device_role == role, f"{name} role invalid: {switch.device_role}"
        assert switch.winbox_port == 9169, f"{name} winbox port invalid"

    assert Switch.objects.get(name="RB5009").device_role == Switch.DeviceRole.CORE_ROUTER
    assert Switch.objects.get(name="CRS354").device_family == Switch.DeviceFamily.MIKROTIK_SWITCH
    assert Switch.objects.get(name="Hex-S").device_role == Switch.DeviceRole.EDGE_ROUTER

    payload = _build_topology_payload()
    groups = {group["key"]: group for group in payload["topology_groups"]}
    for key in ("core", "edge", "remote", "wireless"):
        assert key in groups, f"{key} group missing"
    assert any(node["switch"].name == "RB5009" for node in groups["core"]["nodes"]), "RB5009 not in core"
    assert any(node["switch"].name == "CRS354" for node in groups["core"]["nodes"]), "CRS354 not in core"
    assert any(node["switch"].name == "Hex-S" for node in groups["edge"]["nodes"]), "Hex-S not in edge"
    assert any(node["switch"].name == "AliHome" for node in groups["remote"]["nodes"]), "AliHome not in remote"
    assert any(node["switch"].name == "Cap-Edari" for node in groups["wireless"]["nodes"]), "CAP not in wireless"

    user = get_user_model().objects.create_superuser(username=SMOKE_USER, password="Phase40Pass!", email="")
    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)

    dashboard = client.get(reverse("inventory:switch_list"))
    assert dashboard.status_code == 200, dashboard.status_code
    dashboard_html = dashboard.content.decode("utf-8", errors="replace")
    assert "RB5009" in dashboard_html, "RB5009 missing from dashboard"
    assert ("mikrotik-device-card" in dashboard_html or "device-visual" in dashboard_html), "MikroTik dashboard visual missing"

    topology = client.get(reverse("inventory:topology"))
    assert topology.status_code == 200, topology.status_code
    topology_html = topology.content.decode("utf-8", errors="replace")
    for item in ("RB5009", "CRS354", "Hex-S", "AliHome", "Cap-Edari"):
        assert item in topology_html, f"{item} missing from topology"

    cleanup_user()
    print("PHASE40_MIKROTIK_TOPOLOGY_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup_user()
        raise
