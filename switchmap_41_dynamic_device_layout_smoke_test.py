import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model

from inventory.models import Port, Switch
from inventory.templatetags.switchmap_extras import dynamic_device_visual_context
from switchmap_smoke import read_static_css


SMOKE_USER = "switchmap_phase41_smoke"


def cleanup_user():
    get_user_model().objects.filter(username=SMOKE_USER).delete()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    cleanup_user()
    call_command("seed_mikrotik_devices")
    call_command("apply_dynamic_device_layouts")

    expected = {
        "RB5009": ("mikrotik-rb5009", 9),
        "CRS354": ("mikrotik-crs354", 54),
        "Hex-S": ("mikrotik-hex", 6),
        "RB2011-Iranmall": ("mikrotik-rb2011", 11),
        "AX3-Karaj": ("mikrotik-ax3", 5),
        "Cap-Edari": ("mikrotik-cap", 2),
    }

    for name, (layout_key, port_count) in expected.items():
        switch = Switch.objects.get(name=name)
        actual_count = Port.objects.filter(switch=switch).count()
        assert actual_count >= port_count, f"{name} port placeholders missing: {actual_count}/{port_count}"
        visual = dynamic_device_visual_context(switch, "dashboard")
        assert visual["layout_key"] == layout_key, f"{name} layout invalid: {visual['layout_key']}"

    crs = Switch.objects.get(name="CRS354")
    assert crs.ports.filter(interface_name="ether48").exists(), "CRS354 ether48 missing"
    assert crs.ports.filter(interface_name="sfp-sfpplus4").exists(), "CRS354 SFP+ missing"

    user = get_user_model().objects.create_superuser(username=SMOKE_USER, password="Phase41Pass!", email="")
    client = Client(HTTP_HOST="127.0.0.1")
    client.force_login(user)

    dashboard = client.get(reverse("inventory:switch_list"))
    assert dashboard.status_code == 200, dashboard.status_code
    html = dashboard.content.decode("utf-8", errors="replace")
    assert "dynamic-device-panel" in html, "dynamic device panel missing from dashboard"
    assert "data-dynamic-device-layout=\"mikrotik-rb5009\"" in html, "RB5009 dynamic layout missing"
    assert "data-dynamic-device-layout=\"mikrotik-crs354\"" in html, "CRS354 dynamic layout missing"
    assert "ether48" in html, "CRS354 port label missing"

    detail = client.get(reverse("inventory:switch_detail", args=[crs.id]))
    assert detail.status_code == 200, detail.status_code
    detail_html = detail.content.decode("utf-8", errors="replace")
    assert "mikrotik-crs354" in detail_html, "CRS354 full layout missing"
    assert "sfp-sfpplus4" in detail_html, "CRS354 full SFP missing"

    css = read_static_css()
    assert "Phase 41 - Dynamic device visual layouts" in css, "phase 41 CSS marker missing"

    cleanup_user()
    print("PHASE41_DYNAMIC_DEVICE_LAYOUT_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        cleanup_user()
        raise
