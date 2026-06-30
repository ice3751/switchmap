from django.core.management.base import BaseCommand

from inventory.models import Switch
from inventory.snmp_tools import (
    SnmpError,
    poll_switch_discovery,
    poll_switch_ports,
    sync_missing_snmp_ports,
)


class Command(BaseCommand):
    help = "Poll all active SNMP-enabled switches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Read SNMP data without updating port records.",
        )
        parser.add_argument(
            "--ports-only",
            action="store_true",
            help="Only poll port status/VLAN/PoE data.",
        )
        parser.add_argument(
            "--discovery-only",
            action="store_true",
            help="Only poll CDP/LLDP/MAC data.",
        )
        parser.add_argument(
            "--no-sync",
            action="store_true",
            help="Do not auto-create missing SNMP ports before polling ports.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        ports_only = options["ports_only"]
        discovery_only = options["discovery_only"]
        no_sync = options["no_sync"]

        switches = Switch.objects.filter(
            is_active=True,
            snmp_enabled=True,
        ).order_by("name")

        ok_count = 0
        error_count = 0

        for switch in switches:
            self.stdout.write(f"Polling {switch.name} ({switch.management_ip})")

            try:
                if not discovery_only:
                    if not no_sync:
                        sync_result = sync_missing_snmp_ports(
                            switch=switch,
                            dry_run=dry_run,
                        )
                        self.stdout.write(
                            f"  sync created={sync_result['created']} existing={sync_result['existing']} skipped={sync_result['skipped']}"
                        )

                    port_result = poll_switch_ports(
                        switch=switch,
                        dry_run=dry_run,
                        show_ignored=False,
                    )
                    self.stdout.write(
                        f"  ports matched={port_result['matched']} updated={port_result['updated']} ignored={port_result['ignored']}"
                    )

                if not ports_only:
                    discovery_result = poll_switch_discovery(
                        switch=switch,
                        dry_run=dry_run,
                    )
                    self.stdout.write(
                        f"  discovery matched={discovery_result['matched']} updated={discovery_result['updated']} neighbors={discovery_result['neighbors']} mac_ports={discovery_result['mac_ports']}"
                    )

                ok_count += 1
            except SnmpError as exc:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  ERROR {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. ok={ok_count} errors={error_count}"
            )
        )
