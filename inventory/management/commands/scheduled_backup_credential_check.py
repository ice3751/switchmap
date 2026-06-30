from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from inventory.secure_credentials import CREDENTIAL_PROFILES, SecureCredentialError, credential_status, load_ssh_monitor_credentials


class Command(BaseCommand):
    help = "Check scheduled backup DPAPI credential status without printing passwords."

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=sorted(CREDENTIAL_PROFILES.keys()) + ["all"], default="all")
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        selected = sorted(CREDENTIAL_PROFILES.keys()) if options.get("profile") == "all" else [options.get("profile")]
        missing = 0
        decrypt_fail = 0
        for profile in selected:
            status = credential_status(profile)
            prefix = profile.upper()
            self.stdout.write(f"{prefix}_EXISTS={'YES' if status.get('exists') else 'NO'}")
            self.stdout.write(f"{prefix}_LOCATION={status.get('location')}")
            self.stdout.write(f"{prefix}_FILE={status.get('file')}")
            if not status.get("exists"):
                missing += 1
                continue
            try:
                payload = load_ssh_monitor_credentials(profile=profile)
                self.stdout.write(f"{prefix}_DECRYPT=OK")
                self.stdout.write(f"{prefix}_USER={payload.get('username', '')}")
                self.stdout.write(f"{prefix}_CREATED_AT={payload.get('created_at', '')}")
                self.stdout.write(f"{prefix}_LEGACY={'YES' if payload.get('credential_is_legacy') else 'NO'}")
            except SecureCredentialError as exc:
                decrypt_fail += 1
                self.stdout.write(f"{prefix}_DECRYPT=FAIL {exc}")
        self.stdout.write(f"SCHEDULED_BACKUP_CREDENTIAL_CHECK missing={missing} decrypt_fail={decrypt_fail}")
        if options.get("strict") and (missing or decrypt_fail):
            raise CommandError("Scheduled backup credential check failed")
