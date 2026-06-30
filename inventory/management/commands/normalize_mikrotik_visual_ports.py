from django.core.management.base import BaseCommand

from inventory.models import Port, Switch


AUTO_MARKER = "Auto visual placeholder"


class Command(BaseCommand):
    help = "Normalize MikroTik auto-created visual ports so fake status/mode is not shown as real live data."

    def handle(self, *args, **options):
        switches = Switch.objects.filter(vendor=Switch.Vendor.MIKROTIK).order_by("name")
        changed_ports = 0
        checked_ports = 0
        for switch in switches:
            for port in switch.ports.all():
                checked_ports += 1
                description = (port.description or "").strip()
                if AUTO_MARKER.lower() not in description.lower():
                    continue
                real_data = any([
                    port.snmp_last_poll,
                    bool(port.snmp_oper_status),
                    bool(port.snmp_admin_status),
                    bool(port.neighbor_device),
                    bool(port.neighbor_port),
                    bool(port.connected_device),
                    bool(port.ip_address),
                    bool(port.mac_address),
                    bool(port.vlan),
                    bool(port.access_vlan),
                    bool(port.native_vlan),
                ])
                if real_data:
                    continue
                update_fields = []
                if port.port_mode != Port.PortMode.UNKNOWN:
                    port.port_mode = Port.PortMode.UNKNOWN
                    update_fields.append("port_mode")
                if port.status != Port.Status.DOWN:
                    port.status = Port.Status.DOWN
                    update_fields.append("status")
                if update_fields:
                    port.save(update_fields=update_fields)
                    changed_ports += 1
        self.stdout.write(f"MIKROTIK_VISUAL_PORTS_NORMALIZED checked={checked_ports} changed={changed_ports}")
