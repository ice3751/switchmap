import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from inventory.models import Port, Switch
from switchmap_smoke import read_static_css


User = get_user_model()


def main():
    username = "switchmap_phase36_1_smoke_admin"
    password = "SwitchMapPhase361TestPass!"

    User.objects.filter(username=username).delete()
    Switch.objects.filter(name="SWITCHMAP-PHASE36-1-SMOKE").delete()

    user = User.objects.create_superuser(username=username, password=password, email="")
    switch = Switch.objects.create(
        name="SWITCHMAP-PHASE36-1-SMOKE",
        management_ip="10.255.36.11",
        model="Cisco Catalyst 3850",
        location="Smoke Lab",
        port_count=48,
        is_active=True,
    )
    Port.objects.create(
        switch=switch,
        interface_name="Gi1/0/1",
        display_order=1,
        status=Port.Status.UP,
        port_mode=Port.PortMode.ACCESS,
        access_vlan=100,
        connected_device="Smoke-PC-UI",
        owner="Smoke Owner",
        documentation_status=Port.DocumentationStatus.PARTIAL,
    )

    client = Client(HTTP_HOST="127.0.0.1")
    assert client.login(username=username, password=password), "login failed"

    response = client.get(reverse("inventory:asset_documentation"), {"q": "Smoke-PC-UI"})
    assert response.status_code == 200, f"assets page status={response.status_code}"
    html = response.content.decode("utf-8")
    assert "asset-filter-grid-clean" in html, "clean filter grid class missing"
    assert "asset-doc-table-clean" in html, "clean table class missing"
    assert "Smoke-PC-UI" in html, "test port not rendered"

    css = read_static_css()
    assert "Phase 36.1 - Asset / Documentation UI cleanup" in css, "phase 36.1 css missing"

    Switch.objects.filter(id=switch.id).delete()
    User.objects.filter(id=user.id).delete()
    print("PHASE36_1_UI_SMOKE_OK")


if __name__ == "__main__":
    main()
