import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client

from inventory.models import Port, SfpMonitorSnapshot, Switch
from inventory.views import (
    _health_for_sfp,
    _parse_sfp_error_counters,
    _parse_sfp_status,
    _parse_sfp_transceivers,
)


switch, _ = Switch.objects.update_or_create(
    name="SMOKE-SFP-SW",
    defaults={
        "management_ip": "192.0.2.44",
        "model": "Cisco Catalyst 3850",
        "location": "Smoke Test",
        "port_count": 48,
        "is_active": True,
        "ssh_enabled": True,
        "ssh_username": "admin",
    },
)
port, _ = Port.objects.update_or_create(
    switch=switch,
    interface_name="Te1/1/1",
    defaults={"display_order": 1001, "status": Port.Status.UP},
)

status_output = """
Port      Name               Status       Vlan       Duplex  Speed Type
Te1/1/1                      connected    trunk      full    10G   SFP-10GBase-SR
Te1/1/2                      err-disabled 1          auto    auto  SFP-10GBase-LR
"""
error_output = """
Port        Align-Err     FCS-Err    Xmit-Err     Rcv-Err UnderSize OutDiscards
Te1/1/1             0           3           0           1         0           2
Te1/1/2             0           0           0           0         0           0
"""
transceiver_output = """
Port       Temperature  Voltage  Current   Tx Power  Rx Power
Te1/1/1          30.12    3.291      7.20      -2.10     -3.40
"""

status_map = _parse_sfp_status(status_output)
assert status_map["Te1/1/1"]["link_status"].lower() == "connected"
assert status_map["Te1/1/2"]["link_status"].lower() == "err-disabled"

counter_map = _parse_sfp_error_counters(error_output)
assert counter_map["Te1/1/1"]["fcs_errors"] == 3
assert counter_map["Te1/1/1"]["rcv_errors"] == 1
assert counter_map["Te1/1/1"]["out_discards"] == 2

transceiver_map = _parse_sfp_transceivers(transceiver_output)
assert str(transceiver_map["Te1/1/1"]["rx_power_dbm"]) == "-3.40"

health, note = _health_for_sfp({"link_status": "err-disabled", "err_disabled": True})
assert health == SfpMonitorSnapshot.Health.CRITICAL

SfpMonitorSnapshot.objects.create(
    switch=switch,
    port=port,
    interface_name="Te1/1/1",
    link_status="connected",
    speed="10G",
    media_type="SFP-10GBase-SR",
    fcs_errors=3,
    fcs_delta=3,
    input_error_delta=1,
    output_error_delta=0,
    out_discard_delta=2,
    rx_power_dbm="-3.40",
    tx_power_dbm="-2.10",
    temperature_c="30.12",
    health_state=SfpMonitorSnapshot.Health.WARNING,
    health_note="error counter increased",
)

client = Client(HTTP_HOST="127.0.0.1")
response = client.get("/sfp-monitor/")
assert response.status_code == 200, response.status_code
assert b"SFP Live Monitor" in response.content

response = client.get(f"/sfp-monitor/data/?switch={switch.id}")
assert response.status_code == 200, response.status_code
assert response.json()["ok"] is True

print("SMOKE_TEST_OK")
