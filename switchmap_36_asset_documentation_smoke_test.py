import os
import zipfile
from io import BytesIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from inventory.models import Port, PortDocumentationHistory, Switch


User = get_user_model()


def main():
    username = "switchmap_phase36_smoke_admin"
    password = "SwitchMapPhase36TestPass!"

    User.objects.filter(username=username).delete()
    Switch.objects.filter(name="SWITCHMAP-PHASE36-SMOKE").delete()

    user = User.objects.create_superuser(username=username, password=password, email="")
    switch = Switch.objects.create(
        name="SWITCHMAP-PHASE36-SMOKE",
        management_ip="10.255.36.1",
        model="Cisco Catalyst 3850",
        location="Smoke Lab",
        port_count=48,
        is_active=True,
    )
    port = Port.objects.create(
        switch=switch,
        interface_name="Gi1/0/1",
        display_order=1,
        status=Port.Status.UP,
        port_mode=Port.PortMode.ACCESS,
        access_vlan=100,
        connected_device="Smoke-PC",
    )

    client = Client(HTTP_HOST="127.0.0.1")
    assert client.login(username=username, password=password), "login failed"

    assets_url = reverse("inventory:asset_documentation")
    response = client.get(assets_url, {"q": "Smoke-PC"})
    assert response.status_code == 200, f"assets page status={response.status_code}"
    assert b"Asset / Documentation" in response.content, "assets page title missing"

    csv_response = client.get(reverse("inventory:asset_documentation_export_csv"), {"q": "Smoke-PC"})
    assert csv_response.status_code == 200, f"csv status={csv_response.status_code}"
    assert "text/csv" in csv_response["Content-Type"], "csv content type invalid"

    xlsx_response = client.get(reverse("inventory:asset_documentation_export_xlsx"), {"q": "Smoke-PC"})
    assert xlsx_response.status_code == 200, f"xlsx status={xlsx_response.status_code}"
    ZipFile = zipfile.ZipFile
    with ZipFile(BytesIO(xlsx_response.content)) as archive:
        assert "xl/workbook.xml" in archive.namelist(), "xlsx workbook missing"
        assert "xl/worksheets/sheet1.xml" in archive.namelist(), "xlsx sheet missing"

    edit_payload = {
        "interface_name": port.interface_name,
        "display_order": str(port.display_order),
        "description": "Smoke description",
        "connected_device": port.connected_device,
        "device_type": Port.DeviceType.PC,
        "owner": "Smoke Owner",
        "ip_address": "10.255.36.101",
        "mac_address": "0011.2233.4455",
        "port_mode": Port.PortMode.ACCESS,
        "access_vlan": "100",
        "native_vlan": "",
        "voice_vlan": "",
        "trunk_vlans": "",
        "vlan": "100",
        "status": Port.Status.UP,
        "documentation_status": Port.DocumentationStatus.DOCUMENTED,
        "asset_tag": "ASSET-36",
        "room": "Room-36",
        "rack": "Rack-A",
        "rack_unit": "U12",
        "patch_panel": "PP-1",
        "patch_panel_port": "24",
        "outlet": "O-36",
        "cable_label": "CAB-36",
        "cable_type": "Cat6",
        "cable_length": "15m",
        "prtg_url": "",
        "notes": "Smoke note",
        "next": "assets",
    }
    response = client.post(reverse("inventory:port_edit", args=[port.id]), edit_payload)
    assert response.status_code in (302, 303), f"edit redirect status={response.status_code}"
    assert PortDocumentationHistory.objects.filter(port=port).exists(), "documentation history not created"

    history_response = client.get(reverse("inventory:port_documentation_history", args=[port.id]))
    assert history_response.status_code == 200, f"history status={history_response.status_code}"
    assert b"Port Documentation History" in history_response.content, "history page title missing"

    Switch.objects.filter(id=switch.id).delete()
    User.objects.filter(id=user.id).delete()
    print("PHASE36_SMOKE_OK")


if __name__ == "__main__":
    main()
