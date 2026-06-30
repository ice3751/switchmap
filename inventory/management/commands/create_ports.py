from django.core.management.base import BaseCommand, CommandError

from inventory.models import Port, Switch


class Command(BaseCommand):
    help = "Create GigabitEthernet ports for a switch"

    def add_arguments(self, parser):
        parser.add_argument("switch_name")
        parser.add_argument("--count", type=int, default=48)
        parser.add_argument("--member", type=int, default=1)

    def handle(self, *args, **options):
        switch_name = options["switch_name"]
        count = options["count"]
        member = options["member"]

        try:
            switch = Switch.objects.get(name=switch_name)
        except Switch.DoesNotExist as exc:
            raise CommandError(
                f'Switch "{switch_name}" was not found.'
            ) from exc

        created_count = 0

        for number in range(1, count + 1):
            _, created = Port.objects.update_or_create(
                switch=switch,
                interface_name=f"Gi{member}/0/{number}",
                defaults={
                    "display_order": number,
                },
            )

            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{created_count} ports created successfully."
            )
        )