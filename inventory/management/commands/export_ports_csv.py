import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from inventory.models import Port


class Command(BaseCommand):
    help = "Export switch ports to a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            help="Output CSV file path",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        ports = (
            Port.objects.select_related("switch")
            .all()
            .order_by("switch__name", "display_order")
        )

        fieldnames = [
            "switch",
            "interface_name",
            "display_order",
            "description",
            "connected_device",
            "device_type",
            "owner",
            "ip_address",
            "mac_address",
            "port_mode",
            "access_vlan",
            "native_vlan",
            "voice_vlan",
            "trunk_vlans",
            "vlan",
            "status",
            "poe_enabled",
            "poe_admin_status",
            "poe_detection_status",
            "room",
            "patch_panel",
            "outlet",
            "cable_label",
            "prtg_url",
            "notes",
            "snmp_if_index",
            "snmp_raw_name",
            "snmp_alias",
            "snmp_admin_status",
            "snmp_oper_status",
            "snmp_speed_mbps",
            "snmp_last_poll",
            "neighbor_source",
            "neighbor_device",
            "neighbor_port",
            "neighbor_ip",
            "mac_count",
            "mac_addresses",
            "discovery_last_poll",
        ]

        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            for port in ports:
                writer.writerow(
                    {
                        "switch": port.switch.name,
                        "interface_name": port.interface_name,
                        "display_order": port.display_order,
                        "description": port.description,
                        "connected_device": port.connected_device,
                        "device_type": port.device_type,
                        "owner": port.owner,
                        "ip_address": port.ip_address if port.ip_address else "",
                        "mac_address": port.mac_address,
                        "port_mode": port.port_mode,
                        "access_vlan": port.access_vlan if port.access_vlan is not None else "",
                        "native_vlan": port.native_vlan if port.native_vlan is not None else "",
                        "voice_vlan": port.voice_vlan if port.voice_vlan is not None else "",
                        "trunk_vlans": port.trunk_vlans,
                        "vlan": port.vlan if port.vlan is not None else "",
                        "status": port.status,
                        "poe_enabled": "yes" if port.poe_enabled else "no",
                        "poe_admin_status": port.poe_admin_status,
                        "poe_detection_status": port.poe_detection_status,
                        "room": port.room,
                        "patch_panel": port.patch_panel,
                        "outlet": port.outlet,
                        "cable_label": port.cable_label,
                        "prtg_url": port.prtg_url,
                        "notes": port.notes,
                        "snmp_if_index": port.snmp_if_index or "",
                        "snmp_raw_name": port.snmp_raw_name,
                        "snmp_alias": port.snmp_alias,
                        "snmp_admin_status": port.snmp_admin_status,
                        "snmp_oper_status": port.snmp_oper_status,
                        "snmp_speed_mbps": port.snmp_speed_mbps or "",
                        "snmp_last_poll": port.snmp_last_poll.isoformat() if port.snmp_last_poll else "",
                        "neighbor_source": port.neighbor_source,
                        "neighbor_device": port.neighbor_device,
                        "neighbor_port": port.neighbor_port,
                        "neighbor_ip": port.neighbor_ip if port.neighbor_ip else "",
                        "mac_count": port.mac_count,
                        "mac_addresses": port.mac_addresses,
                        "discovery_last_poll": port.discovery_last_poll.isoformat() if port.discovery_last_poll else "",
                    }
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {ports.count()} ports to {csv_path}"
            )
        )
