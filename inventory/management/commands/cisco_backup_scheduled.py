from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from inventory.cisco_backup_tools import BACKUP_TYPE_LABELS, cisco_switches, run_single_backup, setup_storage, save_backup_failure, command_for_type
from inventory.secure_credentials import SecureCredentialError, load_ssh_monitor_credentials


class Command(BaseCommand):
    help = "SwitchMap Phase84 scheduled Cisco config backup using stored Cisco DPAPI credential."

    def add_arguments(self, parser):
        parser.add_argument("--type", dest="backup_types", action="append", choices=list(BACKUP_TYPE_LABELS.keys()))
        parser.add_argument("--all", action="store_true", help="Backup all active Cisco devices.")
        parser.add_argument("--switch-id", action="append", type=int, default=[])

    def handle(self, *args, **options):
        setup_storage()
        backup_types = options.get("backup_types") or ["running-config"]
        try:
            cred = load_ssh_monitor_credentials(profile="cisco")
        except SecureCredentialError as exc:
            self.stderr.write(f"CREDENTIAL_FAIL={exc}")
            raise SystemExit(2)
        devices = cisco_switches()
        switch_ids = set(options.get("switch_id") or [])
        if switch_ids:
            devices = [sw for sw in devices if sw.id in switch_ids]
        elif not options.get("all"):
            self.stderr.write("Use --all or --switch-id")
            raise SystemExit(2)
        created = 0
        failed = 0
        for switch in devices:
            for backup_type in backup_types:
                try:
                    row = run_single_backup(
                        switch=switch,
                        backup_type=backup_type,
                        username=cred.get("username"),
                        password=cred.get("password"),
                        enable_password=cred.get("enable_password") or "",
                        created_by="scheduled-task",
                        source="scheduled-ssh",
                    )
                    created += 1
                    self.stdout.write(f"OK {switch.name} {backup_type} {row.get('filename')}")
                except Exception as exc:
                    failed += 1
                    try:
                        save_backup_failure(
                            switch=switch,
                            backup_type=backup_type,
                            command=command_for_type(backup_type),
                            error=str(exc),
                            created_by="scheduled-task",
                            source="scheduled-ssh",
                        )
                    except Exception:
                        pass
                    self.stderr.write(f"FAIL {switch.name} {backup_type} {exc}")
        self.stdout.write(f"PHASE84_CISCO_SCHEDULED_BACKUP_DONE created={created} failed={failed}")
        if failed:
            raise CommandError(f"Cisco scheduled backup finished with failed={failed}")
