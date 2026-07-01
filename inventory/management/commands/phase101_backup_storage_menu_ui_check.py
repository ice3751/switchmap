from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.urls import resolve, reverse


class Command(BaseCommand):
    help = "Phase101 read-only UI guard for backup storage filter and operations menu refine."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        root = Path.cwd()
        report = {
            "phase": "PHASE101",
            "mode": "read_only_template_url_guard_no_db_no_service_no_restore_no_ssh",
            "checks": [],
            "failures": [],
            "db_mutation": "NO",
            "service_restart": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
        }

        def ok(name, detail=""):
            self.stdout.write(f"OK={name}{(':' + str(detail)) if detail else ''}")
            report["checks"].append({"name": name, "status": "ok", "detail": detail})

        def fail(name, detail=""):
            self.stdout.write(f"FAIL={name}{(':' + str(detail)) if detail else ''}")
            report["failures"].append({"name": name, "detail": detail})

        self.stdout.write("PHASE101_BACKUP_STORAGE_MENU_UI_CHECK_START")
        self.stdout.write(f"MODE={report['mode']}")
        self.stdout.write(f"ROOT={root}")

        base = root / "inventory" / "templates" / "inventory" / "base.html"
        storage = root / "inventory" / "templates" / "inventory" / "backup_storage_status.html"
        for path in (base, storage):
            if path.exists():
                ok("file_exists", str(path.relative_to(root)))
            else:
                fail("file_missing", str(path.relative_to(root)))

        base_text = base.read_text(encoding="utf-8") if base.exists() else ""
        storage_text = storage.read_text(encoding="utf-8") if storage.exists() else ""

        required_base = [
            "data-phase101-operations-menu-refine",
            "phase101-operations-panel",
            "Backup / Restore",
            "Overview / Restore Guard",
            "Cisco Backup Center",
            "MikroTik Backup",
            "Secure Backup Storage",
            "Config Backup / Diff",
            "SSH Automation",
            "Automation Templates",
        ]
        for marker in required_base:
            if marker in base_text:
                ok("base_marker", marker)
            else:
                fail("base_marker_missing", marker)

        if "Scheduled Credentials" in base_text or "backup_credential_prepare" in base_text:
            fail("scheduled_credentials_still_visible", "base.html")
        else:
            ok("scheduled_credentials_hidden_from_menu")

        required_storage = [
            "data-phase101-backup-storage-filter-ui",
            "data-phase101-filter-table",
            "data-phase101-global-filter",
            "data-phase101-column-filter",
            "data-phase101-clear-filter",
            "Recent Samples",
            "Issues",
        ]
        for marker in required_storage:
            if marker in storage_text:
                ok("storage_marker", marker)
            else:
                fail("storage_marker_missing", marker)

        if "Retention Dry-run" in storage_text or "delete_candidates" in storage_text or "report.retention" in storage_text:
            fail("retention_dry_run_still_visible", "backup_storage_status.html")
        else:
            ok("retention_dry_run_hidden_from_ui")

        url_names = [
            "backup_storage_status",
            "backup_center",
            "cisco_backup_center",
            "mikrotik_backup_center",
            "config_backups",
            "automation_templates",
            "action_logs",
            "reports",
        ]
        for name in url_names:
            full = f"inventory:{name}"
            try:
                path = reverse(full)
                resolved = resolve(path).url_name
                ok("url_reverse_resolve", f"{full}:{path}:resolve={resolved}")
            except Exception as exc:
                fail("url_reverse_resolve", f"{full}:{exc}")

        report["final_fail_count"] = len(report["failures"])
        report["final_ok"] = report["final_fail_count"] == 0
        report["output"] = options.get("output") or ""
        if report["output"]:
            out = Path(report["output"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"REPORT_JSON={out}")
        self.stdout.write(f"FINAL_FAIL_COUNT={report['final_fail_count']}")
        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("SERVICE_RESTART=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("BACKUP_WRITE=NO")
        if report["final_ok"]:
            self.stdout.write("PHASE101_BACKUP_STORAGE_MENU_UI_CHECK_OK")
            return
        self.stdout.write("PHASE101_BACKUP_STORAGE_MENU_UI_CHECK_FAIL")
        raise CommandError("Phase101 backup storage/menu UI check failed")
