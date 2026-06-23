from django.core.management.base import BaseCommand, CommandError

from inventory.models import Switch
from inventory.snmp_tools import SnmpError, poll_switch_discovery


class Command(BaseCommand):
    help = "Read CDP, LLDP and MAC table from a switch using SNMP read-only"

    def add_arguments(self, parser):
        parser.add_argument("switch_name")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        switch_name = options["switch_name"]
        dry_run = options["dry_run"]

        try:
            switch = Switch.objects.get(name=switch_name)
        except Switch.DoesNotExist as exc:
            raise CommandError(
                f'Switch "{switch_name}" was not found.'
            ) from exc

        try:
            result = poll_switch_discovery(
                switch=switch,
                dry_run=dry_run,
            )
        except SnmpError as exc:
            raise CommandError(str(exc)) from exc

        label = "DISCOVERY DRY RUN OK" if dry_run else "DISCOVERY POLL OK"
        self.stdout.write(
            self.style.SUCCESS(
                f"{label} | matched={result['matched']} | updated={result['updated']} | "
                f"neighbors={result['neighbors']} | mac_ports={result['mac_ports']} | "
                f"target={result.get('target', '-')} | local={result.get('local', '-')}"
            )
        )
