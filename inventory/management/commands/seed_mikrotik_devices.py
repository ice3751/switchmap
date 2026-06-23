from django.core.management.base import BaseCommand

from inventory.models import Switch


MIKROTIK_DEVICES = [
    {
        "name": "RB5009",
        "management_ip": "192.168.0.234",
        "model": "MikroTik RB5009UG+S+",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.CORE_ROUTER,
        "site": "Qazvin",
        "location": "Core",
        "topology_position": 10,
        "winbox_port": 9169,
        "notes": "Core router. No password stored.",
        "port_count": 9,
        "needs_review": False,
    },
    {
        "name": "CRS354",
        "management_ip": "192.168.0.252",
        "model": "MikroTik CRS354",
        "device_family": Switch.DeviceFamily.MIKROTIK_SWITCH,
        "device_role": Switch.DeviceRole.CORE_SWITCH,
        "site": "Qazvin",
        "location": "Server/Core switching",
        "topology_position": 20,
        "winbox_port": 9169,
        "notes": "Core switch between servers and rest of network. No password stored.",
        "port_count": 54,
        "needs_review": False,
    },
    {
        "name": "Hex-S",
        "management_ip": "192.168.0.253",
        "model": "MikroTik hEX S",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.EDGE_ROUTER,
        "site": "Qazvin",
        "location": "Internet edge",
        "topology_position": 30,
        "winbox_port": 9169,
        "notes": "Edge router between internet handoff and internal network. No password stored.",
        "port_count": 6,
        "needs_review": False,
    },
    {
        "name": "RB2011-Iranmall",
        "management_ip": "172.20.20.1",
        "model": "MikroTik RB2011",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.REMOTE_OFFICE,
        "site": "Tehran / Iranmall",
        "location": "Remote office",
        "topology_position": 60,
        "winbox_port": 9169,
        "notes": "Remote office router. No password stored.",
        "port_count": 11,
        "needs_review": False,
    },
    {
        "name": "AliHome",
        "management_ip": "192.168.2.1",
        "model": "MikroTik RouterBOARD",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.REMOTE_OFFICE,
        "site": "Ali Home",
        "location": "Remote office / home",
        "topology_position": 62,
        "winbox_port": 9169,
        "notes": "Remote work router. No password stored.",
        "port_count": 5,
        "needs_review": False,
    },
    {
        "name": "AX3-Karaj",
        "management_ip": "192.168.102.1",
        "model": "MikroTik hAP ax3",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.REMOTE_OFFICE,
        "site": "Karaj",
        "location": "Remote office",
        "topology_position": 64,
        "winbox_port": 9169,
        "notes": "Remote work router. No password stored.",
        "port_count": 5,
        "needs_review": False,
    },
    {
        "name": "VPS-Germany",
        "management_ip": "213.183.63.107",
        "model": "MikroTik CHR / VPS",
        "device_family": Switch.DeviceFamily.MIKROTIK_ROUTER,
        "device_role": Switch.DeviceRole.REMOTE_OFFICE,
        "site": "Germany VPS",
        "location": "Cloud edge",
        "topology_position": 70,
        "winbox_port": 9169,
        "notes": "Remote/cloud router. No password stored.",
        "port_count": 1,
        "needs_review": True,
    },
    {
        "name": "Cap-Managment",
        "management_ip": "172.16.25.204",
        "model": "MikroTik cAP",
        "device_family": Switch.DeviceFamily.MIKROTIK_AP,
        "device_role": Switch.DeviceRole.ACCESS_POINT,
        "site": "Qazvin",
        "location": "Management WiFi",
        "topology_position": 120,
        "winbox_port": 9169,
        "notes": "Access Point. No password stored.",
        "port_count": 2,
        "needs_review": False,
    },
    {
        "name": "Cap-Tolid",
        "management_ip": "172.16.25.203",
        "model": "MikroTik cAP",
        "device_family": Switch.DeviceFamily.MIKROTIK_AP,
        "device_role": Switch.DeviceRole.ACCESS_POINT,
        "site": "Qazvin",
        "location": "Production WiFi",
        "topology_position": 122,
        "winbox_port": 9169,
        "notes": "Access Point. No password stored.",
        "port_count": 2,
        "needs_review": False,
    },
    {
        "name": "Cap-Edari",
        "management_ip": "172.16.25.202",
        "model": "MikroTik cAP",
        "device_family": Switch.DeviceFamily.MIKROTIK_AP,
        "device_role": Switch.DeviceRole.ACCESS_POINT,
        "site": "Qazvin",
        "location": "Office WiFi",
        "topology_position": 124,
        "winbox_port": 9169,
        "notes": "Access Point. No password stored.",
        "port_count": 2,
        "needs_review": False,
    },
    {
        "name": "cap-patrol",
        "management_ip": "192.168.0.9",
        "model": "MikroTik cAP",
        "device_family": Switch.DeviceFamily.MIKROTIK_AP,
        "device_role": Switch.DeviceRole.ACCESS_POINT,
        "site": "Qazvin",
        "location": "Patrol WiFi",
        "topology_position": 126,
        "winbox_port": 9169,
        "notes": "Access Point. No password stored.",
        "port_count": 2,
        "needs_review": False,
    },
]


class Command(BaseCommand):
    help = "Seed/update known MikroTik devices without storing credentials."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show changes without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created = 0
        updated = 0

        for item in MIKROTIK_DEVICES:
            payload = {
                "model": item["model"],
                "vendor": Switch.Vendor.MIKROTIK,
                "device_family": item["device_family"],
                "device_role": item["device_role"],
                "site": item["site"],
                "location": item["location"],
                "port_count": item.get("port_count", 0),
                "winbox_port": item["winbox_port"],
                "topology_position": item["topology_position"],
                "notes": item["notes"],
                "needs_review": item["needs_review"],
                "ssh_enabled": True,
                "ssh_port": 22,
                "ssh_username": "admin",
                "is_active": True,
            }

            existing = Switch.objects.filter(management_ip=item["management_ip"]).first()
            if not existing:
                existing = Switch.objects.filter(name__iexact=item["name"]).first()

            if existing:
                changed = []
                if existing.name != item["name"]:
                    existing.name = item["name"]
                    changed.append("name")
                if str(existing.management_ip) != item["management_ip"]:
                    existing.management_ip = item["management_ip"]
                    changed.append("management_ip")
                for key, value in payload.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed.append(key)
                if changed and not dry_run:
                    existing.save()
                if changed:
                    updated += 1
                    self.stdout.write(f"UPDATED {item['name']} {item['management_ip']} fields={','.join(sorted(set(changed)))}")
                else:
                    self.stdout.write(f"UNCHANGED {item['name']} {item['management_ip']}")
            else:
                created += 1
                self.stdout.write(f"CREATE {item['name']} {item['management_ip']}")
                if not dry_run:
                    Switch.objects.create(
                        name=item["name"],
                        management_ip=item["management_ip"],
                        **payload,
                    )

        suffix = "DRY_RUN" if dry_run else "OK"
        self.stdout.write(f"MIKROTIK_SEED_{suffix} created={created} updated={updated} total={len(MIKROTIK_DEVICES)}")
