import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model

from inventory.models import Port, Switch
from inventory.views import _build_topology_payload, _normalize_name

PREFIX = "SMOKE33B-"


def cleanup():
    Switch.objects.filter(name__startswith=PREFIX).delete()
    get_user_model().objects.filter(username="switchmap_phase33b_smoke").delete()


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
        username="switchmap_phase33b_smoke",
        email="phase33b@example.local",
        password="Phase33BPass!",
    )

    core = Switch.objects.create(
        name=f"{PREFIX}NEXUS",
        management_ip="10.33.44.1",
        model="Cisco Nexus",
        location="Core Room",
    )
    access = Switch.objects.create(
        name=f"{PREFIX}Edari-1",
        management_ip="10.33.44.2",
        model="Cisco Catalyst 3850",
        location="Access Rack",
    )

    access_port = make_port(
        access,
        "Te1/1/4",
        52,
        neighbor_source="CDP",
        neighbor_device="N3K-Core-SW.winac-co.com(FOC1916R26A)",
        neighbor_port="Ethernet1/46",
        trunk_vlans="1,101,200",
    )
    core_port = make_port(
        core,
        "Ethernet1/46",
        46,
        neighbor_source="CDP",
        neighbor_device=f"{PREFIX}Edari-1.winac-co.com",
        neighbor_port="TenGigabitEthernet1/1/4",
        trunk_vlans="1,101,200",
    )

    payload = _build_topology_payload()
    assert _normalize_name("N3K-Core-SW.winac-co.com(FOC1916R26A)") == "n3kcoresw"
    assert payload["matched_link_count"] >= 1
    assert any(
        link["matched_switch"].id == core.id and link["matched_by"] in ("alias", "partial-alias")
        for link in payload["internal_links"]
        if link["source_port"].id == access_port.id
    )
    assert any(link["matched_port"] and link["matched_port"].id in (access_port.id, core_port.id) for link in payload["internal_links"])
    assert payload["topology_map"]["links"]
    assert any(group["key"] == "core" and any(node["switch"].id == core.id for node in group["nodes"]) for group in payload["topology_groups"])
    assert any(group["key"] == "access" and any(node["switch"].id == access.id for node in group["nodes"]) for group in payload["topology_groups"])

    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)
    response = client.get(reverse("inventory:topology"))
    assert response.status_code == 200, response.status_code
    content = response.content.decode("utf-8", errors="replace")
    assert "Visual Link Map" in content
    assert "topology-visual-map" in content
    assert "N3K-Core-SW" in content

    cleanup()
    print("PHASE33B_TOPOLOGY_MATCHING_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup()
        raise
