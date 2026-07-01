from __future__ import annotations

import json
from django.core.management.base import BaseCommand

from inventory.backup_schedule_policy import DEFAULT_POLICY, POLICY_PATH, load_policy, save_policy


class Command(BaseCommand):
    help = "Phase89: show or initialize backup schedule policy."

    def add_arguments(self, parser):
        parser.add_argument("--init-defaults", action="store_true")
        parser.add_argument("--show", action="store_true")

    def handle(self, *args, **options):
        if options.get("init_defaults"):
            policy = load_policy(create=True)
            save_policy(policy)
            self.stdout.write("POLICY_INIT_OK=" + str(POLICY_PATH))
        policy = load_policy(create=True)
        self.stdout.write("POLICY_PATH=" + str(POLICY_PATH))
        self.stdout.write("AUTO_INCLUDE_NEW_DEVICES=" + str(policy.get("auto_include_new_devices")))
        self.stdout.write("CISCO_EXCLUDE_IDS=" + ",".join(str(x) for x in (policy.get("cisco") or {}).get("exclude_ids") or []))
        self.stdout.write("MIKROTIK_EXCLUDE_IDS=" + ",".join(str(x) for x in (policy.get("mikrotik") or {}).get("exclude_ids") or []))
        self.stdout.write("MIKROTIK_FULL_BACKUP_IDS=" + ",".join(str(x) for x in (policy.get("mikrotik") or {}).get("full_backup_ids") or []))
        if options.get("show"):
            self.stdout.write(json.dumps(policy, indent=2, ensure_ascii=False))
