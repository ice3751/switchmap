from django.core.management.base import BaseCommand, CommandError

from inventory.models import Switch
from inventory.snmp_tools import SnmpError, poll_switch_ports, test_snmp_connection


class Command(BaseCommand):
    help = "Poll a switch with read-only SNMP v2c and update local port status"

    def add_arguments(self, parser):
        parser.add_argument("switch_name")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--show-ignored", action="store_true")
        parser.add_argument("--test", action="store_true")

    def handle(self, *args, **options):
        switch_name = options["switch_name"]
        dry_run = options["dry_run"]
        show_ignored = options["show_ignored"]
        test_only = options["test"]

        try:
            switch = Switch.objects.get(name=switch_name)
        except Switch.DoesNotExist as exc:
            raise CommandError(f'Switch "{switch_name}" was not found.') from exc

        if test_only:
            result = test_snmp_connection(switch)
            if not result["ok"]:
                raise CommandError(
                    f'{result["message"]} target={result.get("target", "-")} '
                    f'local={result.get("local", "-")} error={result.get("error", "-")}'
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f'{result["message"]} target={result.get("target", "-")} '
                    f'local={result.get("local", "-")} value={result.get("value", "-")}'
                )
            )
            return

        try:
            result = poll_switch_ports(
                switch=switch,
                dry_run=dry_run,
                show_ignored=show_ignored,
            )
        except SnmpError as exc:
            raise CommandError(f"SNMP polling failed: {exc}") from exc

        result_label = "SNMP_DRY_RUN_OK" if dry_run else "SNMP_UPDATE_OK"
        self.stdout.write(
            self.style.SUCCESS(
                f"{result_label} switch={switch.name} matched={result['matched']} "
                f"updated={result['updated']} ignored={result['ignored']} "
                f"target={result.get('target', '-')} local={result.get('local', '-')}"
            )
        )

        if show_ignored and result["ignored_interfaces"]:
            self.stdout.write("Ignored interfaces:")
            for name in result["ignored_interfaces"]:
                self.stdout.write(f"- {name}")
