from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from inventory.mikrotik_backup_tools import BACKUP_TYPE_LABELS, mikrotik_switches, run_single_backup, save_backup_failure
from inventory.models import Switch
from inventory.secure_credentials import load_ssh_monitor_credentials


class Command(BaseCommand):
    help = "Run scheduled MikroTik backups using DPAPI-protected credentials."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Backup all active MikroTik devices")
        parser.add_argument("--switch-id", action="append", default=[], help="Switch ID to backup; can be repeated")
        parser.add_argument("--type", action="append", default=[], choices=list(BACKUP_TYPE_LABELS.keys()), help="Backup type; can be repeated")

    def handle(self, *args, **options):
        backup_types = options.get("type") or ["export"]
        if options.get("all"):
            switches = mikrotik_switches()
        else:
            ids = [int(x) for x in options.get("switch_id") or [] if str(x).isdigit()]
            if not ids:
                raise CommandError("Use --all or at least one --switch-id")
            mikrotik_ids = {sw.id for sw in mikrotik_switches()}
            switches = [sw for sw in Switch.objects.filter(id__in=ids, is_active=True).order_by("topology_position", "name") if sw.id in mikrotik_ids]
        if not switches:
            raise CommandError("No MikroTik devices selected")
        cred = load_ssh_monitor_credentials(profile="mikrotik")
        username = cred.get("username") or ""
        password = cred.get("password") or ""
        ok = 0
        failed = 0
        for switch in switches:
            for backup_type in backup_types:
                try:
                    row = run_single_backup(switch=switch, backup_type=backup_type, username=username, password=password, created_by="scheduled", source="scheduled")
                    ok += 1
                    self.stdout.write(f"OK {switch.name} {backup_type} {row.get('filename')}")
                except Exception as exc:
                    failed += 1
                    save_backup_failure(switch=switch, backup_type=backup_type, command=backup_type, error=str(exc), created_by="scheduled", source="scheduled")
                    self.stdout.write(f"FAIL {switch.name} {backup_type} {exc}")
        self.stdout.write(f"MIKROTIK_BACKUP_SCHEDULED_DONE ok={ok} failed={failed}")
        if failed:
            raise CommandError(f"{failed} MikroTik backup(s) failed")
