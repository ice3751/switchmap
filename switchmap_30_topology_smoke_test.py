import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from inventory.models import Port, Switch
from inventory.views import _build_topology_payload


PREFIX = "SMOKE30-"


def cleanup():
    Switch.objects.filter(name__startswith=PREFIX).delete()
    get_user_model().objects.filter(username="switchmap_phase30_smoke").delete()


def make_port(switch, interface, order, **kwargs):
    defaults = {
        "display_order": order,
        "status": Port.Status.UP,
        "port_mode": Port.PortMode.TRUNK,
        "device_type": Port.DeviceType.UPLINK,
    }
    defaults.update(kwargs)
    return Port.objects.create(
        switch=switch,
        interface_name=interface,
        **defaults,
    )


def main():
    cleanup()
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="switchmap_phase30_smoke",
        password="switchmap_phase30_smoke",
        is_staff=True,
        is_superuser=True,
    )

    sw_a = Switch.objects.create(
        name=f"{PREFIX}A",
        management_ip="10.30.30.1",
        model="Cisco Catalyst 3850",
        location="Smoke Lab",
        snmp_enabled=False,
    )
    sw_b = Switch.objects.create(
        name=f"{PREFIX}B",
        management_ip="10.30.30.2",
        model="Cisco Catalyst 3850",
        location="Smoke Lab",
        snmp_enabled=False,
    )

    make_port(
        sw_a,
        "Gi1/0/48",
        48,
        neighbor_source="CDP",
        neighbor_device=sw_b.name,
        neighbor_port="Gi1/0/48",
        neighbor_ip=sw_b.management_ip,
        trunk_vlans="1,101,200",
    )
    make_port(
        sw_b,
        "Gi1/0/48",
        48,
        neighbor_source="CDP",
        neighbor_device=sw_a.name,
        neighbor_port="Gi1/0/48",
        neighbor_ip=sw_a.management_ip,
        trunk_vlans="1,101,200",
    )
    make_port(
        sw_a,
        "Gi1/0/47",
        47,
        neighbor_source="LLDP",
        neighbor_device="UNKNOWN-UPLINK-SMOKE30",
        neighbor_port="Eth1/1",
        trunk_vlans="1,101",
    )
    make_port(
        sw_b,
        "Te1/1/1",
        1001,
        neighbor_source="",
        neighbor_device="",
        neighbor_port="",
    )

    payload = _build_topology_payload()
    smoke_links = [
        link for link in payload["links"]
        if link["source_switch"].name.startswith(PREFIX)
    ]
    assert any(link["matched_switch"] and link["matched_switch"].name == sw_b.name for link in smoke_links), "internal topology match missing"
    assert any(link["neighbor_device"] == "UNKNOWN-UPLINK-SMOKE30" for link in smoke_links), "unknown neighbor missing"
    assert any(port.switch.name == sw_b.name and port.interface_name == "Te1/1/1" for port in payload["uplinks_without_neighbor"]), "unknown uplink missing"

    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)
    response = client.get(reverse("inventory:topology"))
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="replace")
    assert "Topology واقعی شبکه" in content
    assert "UNKNOWN-UPLINK-SMOKE30" in content
    assert "Gi1/0/48" in content

    cleanup()
    print("PHASE30_TOPOLOGY_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
