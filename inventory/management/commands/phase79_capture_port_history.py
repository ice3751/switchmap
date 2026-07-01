from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Port, PortConnectionHistory, Switch
from inventory.phase79_history import record_port_identity_snapshot


class Command(BaseCommand):
    help = "Capture current Port identity data into Phase79 PortConnectionHistory. No network polling is performed."

    def add_arguments(self, parser):
        parser.add_argument("--switch", dest="switch", default="", help="Switch name or management IP")
        parser.add_argument("--source", dest="source", default="manual_capture", help="History source label")
        parser.add_argument("--force", action="store_true", help="Create records even when no identity data exists")
        parser.add_argument("--dry-run", action="store_true", help="Show counts without writing")

    def handle(self, *args, **options):
        qs = Port.objects.select_related("switch").order_by("switch__name", "display_order")
        switch_filter = str(options.get("switch") or "").strip()
        if switch_filter:
            switch = Switch.objects.filter(name__iexact=switch_filter).first() or Switch.objects.filter(management_ip=switch_filter).first()
            if not switch:
                self.stdout.write(f"PHASE79_1_CAPTURE_FAIL switch_not_found={switch_filter}")
                return
            qs = qs.filter(switch=switch)

        total = qs.count()
        with_identity = 0
        touched = 0
        created_or_updated = 0
        dry_run = bool(options.get("dry_run"))
        now = timezone.now()

        for port in qs:
            has_identity = any([
                port.connected_device,
                port.neighbor_device,
                port.neighbor_port,
                port.neighbor_ip,
                port.ip_address,
                port.mac_address,
                port.mac_addresses,
                port.mac_count,
            ])
            if has_identity:
                with_identity += 1
            if dry_run:
                continue
            history = record_port_identity_snapshot(
                port,
                source=str(options.get("source") or "manual_capture"),
                observed_at=now,
                force=bool(options.get("force")),
            )
            touched += 1
            if history:
                created_or_updated += 1

        self.stdout.write("PHASE79_1_CAPTURE_REPORT")
        self.stdout.write(f"total_ports={total}")
        self.stdout.write(f"ports_with_identity={with_identity}")
        self.stdout.write(f"dry_run={1 if dry_run else 0}")
        self.stdout.write(f"processed={touched}")
        self.stdout.write(f"history_rows_now={PortConnectionHistory.objects.count() if not dry_run else 'not_changed'}")
        self.stdout.write(f"created_or_updated={created_or_updated if not dry_run else 'not_changed'}")
        self.stdout.write("PHASE79_1_CAPTURE_OK")
