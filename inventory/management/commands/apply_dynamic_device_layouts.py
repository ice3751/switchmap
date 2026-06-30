from django.core.management.base import BaseCommand

from inventory.models import Port, Switch


LAYOUTS = {
    "rb5009": [
        "ether1", "ether2", "ether3", "ether4", "ether5", "ether6", "ether7", "ether8", "sfp-sfpplus1",
    ],
    "crs354": [
        *[f"ether{i}" for i in range(1, 49)],
        "sfp-sfpplus1", "sfp-sfpplus2", "sfp-sfpplus3", "sfp-sfpplus4", "qsfpplus1-1", "qsfpplus2-1",
    ],
    "hex-s": ["ether1", "ether2", "ether3", "ether4", "ether5", "sfp1"],
    "hex s": ["ether1", "ether2", "ether3", "ether4", "ether5", "sfp1"],
    "rb2011": [*[f"ether{i}" for i in range(1, 11)], "sfp1"],
    "hap ax3": ["ether1", "ether2", "ether3", "ether4", "ether5"],
    "ax3": ["ether1", "ether2", "ether3", "ether4", "ether5"],
    "cap": ["ether1", "ether2"],
    "routerboard": ["ether1", "ether2", "ether3", "ether4", "ether5"],
    "chr": ["ether1"],
    "vps": ["ether1"],
}


ROLE_MODE_DEFAULTS = {
    Switch.DeviceRole.CORE_ROUTER: Port.PortMode.TRUNK,
    Switch.DeviceRole.CORE_SWITCH: Port.PortMode.TRUNK,
    Switch.DeviceRole.EDGE_ROUTER: Port.PortMode.TRUNK,
    Switch.DeviceRole.REMOTE_OFFICE: Port.PortMode.ACCESS,
    Switch.DeviceRole.ACCESS_POINT: Port.PortMode.ACCESS,
}


def layout_for_switch(switch):
    text = f"{switch.name} {switch.model} {switch.device_family}".lower()
    for key, layout in LAYOUTS.items():
        if key in text:
            return list(layout)
    if switch.device_family == Switch.DeviceFamily.MIKROTIK_SWITCH:
        return [f"ether{i}" for i in range(1, max(switch.port_count or 24, 24) + 1)]
    if switch.device_family == Switch.DeviceFamily.MIKROTIK_AP:
        return ["ether1", "ether2"]
    if switch.vendor == Switch.Vendor.MIKROTIK:
        return ["ether1", "ether2", "ether3", "ether4", "ether5"]
    return []


class Command(BaseCommand):
    help = "Create/update visual placeholder ports for devices whose physical layout is model-specific."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_created = 0
        total_updated = 0
        total_devices = 0

        switches = Switch.objects.filter(is_active=True).order_by("topology_position", "name")
        for switch in switches:
            if switch.vendor != Switch.Vendor.MIKROTIK:
                continue

            layout = layout_for_switch(switch)
            if not layout:
                continue

            total_devices += 1
            created = 0
            updated = 0
            default_mode = ROLE_MODE_DEFAULTS.get(switch.device_role, Port.PortMode.UNKNOWN)
            existing = {port.interface_name.lower(): port for port in switch.ports.all()}

            for index, interface_name in enumerate(layout, start=1):
                key = interface_name.lower()
                port = existing.get(key)
                if port is None:
                    created += 1
                    if not dry_run:
                        Port.objects.create(
                            switch=switch,
                            interface_name=interface_name,
                            display_order=index,
                            status=Port.Status.DOWN,
                            port_mode=default_mode,
                            description="Auto visual placeholder",
                        )
                    continue

                changed = []
                if port.display_order != index:
                    port.display_order = index
                    changed.append("display_order")
                if not port.port_mode or port.port_mode == Port.PortMode.UNKNOWN:
                    port.port_mode = default_mode
                    changed.append("port_mode")
                if changed:
                    updated += 1
                    if not dry_run:
                        port.save(update_fields=changed)

            if switch.port_count != len(layout):
                updated += 1
                if not dry_run:
                    switch.port_count = len(layout)
                    switch.save(update_fields=["port_count"])

            total_created += created
            total_updated += updated
            status = "DRY" if dry_run else "OK"
            self.stdout.write(f"LAYOUT_{status} {switch.name} ports={len(layout)} created={created} updated={updated}")

        suffix = "DRY_RUN" if dry_run else "OK"
        self.stdout.write(f"DYNAMIC_DEVICE_LAYOUTS_{suffix} devices={total_devices} created={total_created} updated={total_updated}")
