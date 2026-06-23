import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model

from inventory.models import Port, Switch
from inventory.views import _build_topology_payload

PREFIX = "SMOKE33-"


def cleanup():
    Switch.objects.filter(name__startswith=PREFIX).delete()
    get_user_model().objects.filter(username="switchmap_phase33_smoke").delete()


def make_port(switch, interface, order, **kwargs):
    defaults = {
        "display_order": order,
        "status": Port.Status.UP,
        "port_mode": Port.PortMode.TRUNK,
        "device_type": Port.DeviceType.UPLINK,
    }
    defaults.update(kwargs)
    return Port.objects.create(switch=switch, interface_name=interface, **defaults)


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    cleanup()
    user = get_user_model().objects.create_superuser(
        username="switchmap_phase33_smoke",
        email="phase33@example.local",
        password="Phase33Pass!",
    )

    core = Switch.objects.create(
        name=f"{PREFIX}N3K-Core",
        management_ip="10.33.33.1",
        model="Cisco Nexus",
        location="Core Room",
    )
    access = Switch.objects.create(
        name=f"{PREFIX}Access-3850",
        management_ip="10.33.33.2",
        model="Cisco Catalyst 3850",
        location="Access Rack",
    )
    isolated = Switch.objects.create(
        name=f"{PREFIX}Unknown-SW",
        management_ip="10.33.33.3",
        model="Other",
        location="Smoke Lab",
    )

    make_port(
        core,
        "Eth1/40",
        40,
        neighbor_source="CDP",
        neighbor_device=access.name,
        neighbor_port="Gi1/0/48",
        neighbor_ip=access.management_ip,
        trunk_vlans="1,101,200",
    )
    make_port(
        access,
        "Gi1/0/48",
        48,
        neighbor_source="CDP",
        neighbor_device=core.name,
        neighbor_port="Eth1/40",
        neighbor_ip=core.management_ip,
        trunk_vlans="1,101,200",
    )
    make_port(
        access,
        "Gi1/0/47",
        47,
        status=Port.Status.DOWN,
        neighbor_source="LLDP",
        neighbor_device="UNKNOWN-PHASE33-UPLINK",
        neighbor_port="Eth9/1",
    )
    make_port(isolated, "Gi1/0/48", 48, neighbor_device="", neighbor_port="")

    payload = _build_topology_payload()
    assert payload["matched_link_count"] >= 1
    assert payload["external_link_count"] >= 1
    assert payload["down_link_count"] >= 1
    assert any(group["key"] == "core" and any(node["switch"].id == core.id for node in group["nodes"]) for group in payload["topology_groups"])
    assert any(group["key"] == "access" and any(node["switch"].id == access.id for node in group["nodes"]) for group in payload["topology_groups"])
    assert any(link["health"] == "down" for link in payload["links"] if link["source_switch"].id == access.id)

    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)
    response = client.get(reverse("inventory:topology"))
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="replace")
    assert "Switch Groups" in content
    assert "Internal Links" in content
    assert "UNKNOWN-PHASE33-UPLINK" in content
    assert "Duplicate CDP / LLDP Entries" in content

    cleanup()
    print("PHASE33_TOPOLOGY_UI_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
