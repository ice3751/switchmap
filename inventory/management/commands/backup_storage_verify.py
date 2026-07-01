from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from inventory.backup_storage_tools import verify_secure_backup_storage


class Command(BaseCommand):
    help = "Verify SwitchMap secure backup storage, hashes, paths, metadata and dry-run retention."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Print full JSON report")
        parser.add_argument("--strict", action="store_true", help="Exit non-zero if any warning/failure exists")

    def handle(self, *args, **options):
        report = verify_secure_backup_storage()
        if options.get("json"):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            stats = report.get("stats", {})
            self.stdout.write("PHASE86_BACKUP_STORAGE_VERIFY_START")
            self.stdout.write(f"ROOT={report.get('root')}")
            self.stdout.write(f"OK={report.get('ok')}")
            self.stdout.write(f"TOTAL_ROWS={stats.get('total_rows')}")
            self.stdout.write(f"SUCCESS_ROWS={stats.get('success_rows')}")
            self.stdout.write(f"FAILED_ROWS={stats.get('failed_rows')}")
            self.stdout.write(f"VERIFIED_FILES={stats.get('verified_files')}")
            self.stdout.write(f"HASH_MISMATCH={stats.get('hash_mismatch')}")
            self.stdout.write(f"MISSING_FILES={stats.get('missing_files')}")
            self.stdout.write(f"FAILURE_ISSUES={stats.get('failure_issues')}")
            self.stdout.write(f"WARNING_ISSUES={stats.get('warning_issues')}")
            self.stdout.write(f"OUTSIDE_ROOT={stats.get('outside_root')}")
            self.stdout.write(f"INSIDE_PROJECT={stats.get('inside_project')}")
            self.stdout.write(f"RETENTION_KEEP={report.get('retention', {}).get('keep_count')}")
            self.stdout.write(f"RETENTION_DELETE_CANDIDATES={report.get('retention', {}).get('delete_candidates')}")
            self.stdout.write("PHASE86_BACKUP_STORAGE_VERIFY_DONE")
        failure_issues = int(report.get("stats", {}).get("failure_issues") or 0)
        if options.get("strict") and (not report.get("ok") or failure_issues > 0):
            raise SystemExit(2)
