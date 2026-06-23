from django.core.management.base import BaseCommand, CommandError

from inventory.models import Switch
from inventory.snmp_tools import SnmpError, poll_switch_ports, sync_missing_snmp_ports


class Command(BaseCommand):
    help = "Create missing physical ports from SNMP interface table"

    def add_arguments(self, parser):
        parser.add_argument("switch_name")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-poll", action="store_true")

    def handle(self, *args, **options):
        switch_name = options["switch_name"]
        dry_run = options["dry_run"]
        no_poll = options["no_poll"]

        try:
            switch = Switch.objects.get(name=switch_name)
        except Switch.DoesNotExist as exc:
            raise CommandError(f'Switch "{switch_name}" was not found.') from exc

        try:
            result = sync_missing_snmp_ports(
                switch=switch,
                dry_run=dry_run,
            )

            if not dry_run and not no_poll:
                poll_switch_ports(
                    switch=switch,
                    dry_run=False,
                    show_ignored=False,
                )
        except SnmpError as exc:
            raise CommandError(str(exc)) from exc

        label = "SNMP PORT SYNC DRY RUN OK" if dry_run else "SNMP PORT SYNC OK"
        self.stdout.write(
            self.style.SUCCESS(
                f"{label} | created={result['created']} | existing={result['existing']} | "
                f"skipped={result['skipped']} | target={result.get('target', '-')} | "
                f"local={result.get('local', '-')}"
            )
        )

        for name in result.get("created_names", []):
            self.stdout.write(f"- {name}")
