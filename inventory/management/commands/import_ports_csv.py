import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from inventory.models import Port, Switch


STATUS_VALUES = {
    Port.Status.UP,
    Port.Status.DOWN,
    Port.Status.DISABLED,
    Port.Status.ERROR,
}

DEVICE_TYPE_VALUES = {
    choice[0] for choice in Port.DeviceType.choices
}

PORT_MODE_VALUES = {
    choice[0] for choice in Port.PortMode.choices
}

TRUE_VALUES = {"1", "true", "yes", "y", "on", "فعال"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "غیرفعال", ""}


class Command(BaseCommand):
    help = "Import and update switch port data from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            help="Input CSV file path",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate CSV without saving changes",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        updated_count = 0
        skipped_count = 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)

            required_columns = {"switch", "interface_name"}
            missing_columns = required_columns - set(reader.fieldnames or [])

            if missing_columns:
                raise CommandError(
                    "Missing required columns: "
                    + ", ".join(sorted(missing_columns))
                )

            for row_number, row in enumerate(reader, start=2):
                switch_name = (row.get("switch") or "").strip()
                interface_name = (row.get("interface_name") or "").strip()

                if not switch_name or not interface_name:
                    skipped_count += 1
                    self.stdout.write(
                        f"Row {row_number}: skipped because switch or interface_name is empty"
                    )
                    continue

                try:
                    switch = Switch.objects.get(name=switch_name)
                    port = Port.objects.get(
                        switch=switch,
                        interface_name=interface_name,
                    )
                except Switch.DoesNotExist:
                    skipped_count += 1
                    self.stdout.write(
                        f'Row {row_number}: skipped because switch "{switch_name}" was not found'
                    )
                    continue
                except Port.DoesNotExist:
                    skipped_count += 1
                    self.stdout.write(
                        f'Row {row_number}: skipped because port "{interface_name}" was not found on "{switch_name}"'
                    )
                    continue

                for field_name in [
                    "description",
                    "connected_device",
                    "owner",
                    "mac_address",
                    "room",
                    "patch_panel",
                    "outlet",
                    "cable_label",
                    "prtg_url",
                    "trunk_vlans",
                    "poe_admin_status",
                    "poe_detection_status",
                    "notes",
                ]:
                    self.update_text_field(port, row, field_name)

                if "display_order" in row:
                    display_order = (row.get("display_order") or "").strip()
                    if display_order:
                        port.display_order = int(display_order)

                if "device_type" in row:
                    device_type = (row.get("device_type") or "").strip().lower()
                    if device_type:
                        if device_type not in DEVICE_TYPE_VALUES:
                            raise CommandError(
                                f'Row {row_number}: invalid device_type "{device_type}"'
                            )
                        port.device_type = device_type

                if "ip_address" in row:
                    ip_value = (row.get("ip_address") or "").strip()
                    port.ip_address = ip_value or None

                if "port_mode" in row:
                    port_mode = (row.get("port_mode") or "").strip().lower()
                    if port_mode:
                        if port_mode not in PORT_MODE_VALUES:
                            raise CommandError(
                                f'Row {row_number}: invalid port_mode "{port_mode}"'
                            )
                        port.port_mode = port_mode

                for number_field in ["access_vlan", "native_vlan", "voice_vlan"]:
                    if number_field in row:
                        value = (row.get(number_field) or "").strip()
                        setattr(port, number_field, int(value) if value else None)

                if "vlan" in row:
                    vlan_value = (row.get("vlan") or "").strip()
                    port.vlan = int(vlan_value) if vlan_value else None

                if "status" in row:
                    status_value = (row.get("status") or "").strip().lower()

                    if status_value:
                        if status_value not in STATUS_VALUES:
                            raise CommandError(
                                f'Row {row_number}: invalid status "{status_value}"'
                            )

                        port.status = status_value

                if "poe_enabled" in row:
                    poe_value = (row.get("poe_enabled") or "").strip().lower()

                    if poe_value in TRUE_VALUES:
                        port.poe_enabled = True
                    elif poe_value in FALSE_VALUES:
                        port.poe_enabled = False
                    else:
                        raise CommandError(
                            f'Row {row_number}: invalid poe_enabled "{poe_value}"'
                        )

                updated_count += 1

                if not dry_run:
                    port.save()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run completed. Valid rows: {updated_count}, skipped rows: {skipped_count}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import completed. Updated rows: {updated_count}, skipped rows: {skipped_count}"
                )
            )

    @staticmethod
    def update_text_field(port, row, field_name):
        if field_name in row:
            setattr(port, field_name, (row.get(field_name) or "").strip())
