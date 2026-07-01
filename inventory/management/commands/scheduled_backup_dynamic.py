from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand

from inventory.backup_schedule_policy import ids, load_policy, schedule_candidates

PHASE89_MARKER = "PHASE89_DYNAMIC_SCHEDULED_BACKUP"


def _run(label: str, args: List[str]) -> int:
    print(f"----- {label} START -----")
    p = subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=str(settings.BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=3600,
    )
    if p.stdout:
        print(p.stdout, end="" if p.stdout.endswith("\n") else "\n")
    print(f"{label}_EXIT={p.returncode}")
    print(f"----- {label} END -----")
    return int(p.returncode)


class Command(BaseCommand):
    help = "Phase89: run scheduled backup with dynamic policy-based coverage and auto-include new devices."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show dynamic coverage without running backups.")
        parser.add_argument("--no-health-report", action="store_true", help="Do not generate health report after backup.")
        parser.add_argument("--no-storage-verify", action="store_true", help="Do not run backup_storage_verify after backup.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        no_health_report = bool(options.get("no_health_report"))
        no_storage_verify = bool(options.get("no_storage_verify"))
        policy = load_policy(create=True)
        plan = schedule_candidates(policy)

        cisco_ids = ids(plan["cisco"])
        mt_export_ids = ids(plan["mikrotik_export"])
        mt_full_ids = ids(plan["mikrotik_full"])

        self.stdout.write("PHASE89_DYNAMIC_SCHEDULED_BACKUP_START")
        self.stdout.write("MODE=" + ("dry-run" if dry_run else "execute"))
        self.stdout.write("DATE_TIME=" + datetime.datetime.now().isoformat(sep=" ", timespec="seconds"))
        self.stdout.write("POLICY=" + str(plan["policy_path"]))
        self.stdout.write("AUTO_INCLUDE_NEW_DEVICES=" + str(policy.get("auto_include_new_devices")))
        self.stdout.write("CISCO_IDS=" + ",".join(str(x) for x in cisco_ids))
        self.stdout.write("MIKROTIK_EXPORT_IDS=" + ",".join(str(x) for x in mt_export_ids))
        self.stdout.write("MIKROTIK_FULL_BACKUP_IDS=" + ",".join(str(x) for x in mt_full_ids))
        self.stdout.write("SKIPPED_COUNT=" + str(len(plan.get("skipped") or [])))
        for item in plan.get("skipped") or []:
            self.stdout.write(f"SKIP profile={item.get('profile')} id={item.get('id')} name={item.get('name')} reason={item.get('reason')}")

        if dry_run:
            self.stdout.write("PHASE89_DYNAMIC_SCHEDULED_BACKUP_DRY_RUN_DONE")
            return

        final = 0
        final = max(final, _run("CREDENTIAL_CHECK", ["scheduled_backup_credential_check", "--profile", "all", "--strict"]))

        if cisco_ids:
            cmd = ["cisco_backup_scheduled"]
            for sid in cisco_ids:
                cmd.extend(["--switch-id", str(sid)])
            for typ in plan["cisco_types"]:
                cmd.extend(["--type", str(typ)])
            final = max(final, _run("CISCO_BACKUP", cmd))
        else:
            self.stdout.write("CISCO_BACKUP_SKIP=no cisco ids")

        if mt_export_ids:
            cmd = ["mikrotik_backup_scheduled"]
            for sid in mt_export_ids:
                cmd.extend(["--switch-id", str(sid)])
            for typ in plan["mikrotik_export_types"]:
                cmd.extend(["--type", str(typ)])
            final = max(final, _run("MIKROTIK_EXPORT_BACKUP", cmd))
        else:
            self.stdout.write("MIKROTIK_EXPORT_BACKUP_SKIP=no mikrotik export ids")

        if mt_full_ids:
            cmd = ["mikrotik_backup_scheduled"]
            for sid in mt_full_ids:
                cmd.extend(["--switch-id", str(sid)])
            for typ in plan["mikrotik_full_types"]:
                cmd.extend(["--type", str(typ)])
            final = max(final, _run("MIKROTIK_FULL_BACKUP", cmd))
        else:
            self.stdout.write("MIKROTIK_FULL_BACKUP_SKIP=no mikrotik full-backup ids")

        if not no_storage_verify:
            final = max(final, _run("STORAGE_VERIFY", ["backup_storage_verify", "--strict"]))
        if not no_health_report:
            final = max(final, _run("HEALTH_REPORT", ["backup_health_report", "--strict"]))

        self.stdout.write("FINAL_EXIT=" + str(final))
        self.stdout.write("PHASE89_DYNAMIC_SCHEDULED_BACKUP_DONE")
        raise SystemExit(final)
