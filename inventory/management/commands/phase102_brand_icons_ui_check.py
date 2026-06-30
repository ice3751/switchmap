from __future__ import annotations

import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.urls import reverse, resolve

ROOT = Path(settings.BASE_DIR)
REQUIRED_FILES = [
    "inventory/static/inventory/brand/phase102/switchmap-header-logo.svg",
    "inventory/static/inventory/brand/phase102/switchmap-app-icon.svg",
    "inventory/static/inventory/brand/phase102/favicon.svg",
    "inventory/static/inventory/brand/phase102/switchmap-brand-preview.png",
    "inventory/static/inventory/css/switchmap-phase102-brand-icons.css",
]
REQUIRED_ICONS = [
    "dashboard", "monitoring", "devices", "operations", "management", "alerts", "topology", "assets",
    "documentation", "backup-restore", "secure-backup-storage", "config-diff", "ssh-automation",
    "automation-templates", "logs", "reports", "users", "admin", "noc-dashboard", "mikrotik",
    "cisco-backup", "restore-guard", "csv", "sfp-live",
]
BASE_MARKERS = [
    "data-phase102-brand-icons",
    "switchmap-phase102-brand-icons.css",
    "inventory/brand/phase102/favicon.svg",
    "phase102-brand-link",
    "phase102-brand-mark",
    "switchmap-app-icon.svg",
]
CSS_MARKERS = [
    "Phase102 - SwitchMap Brand + Navigation Icon System",
    "dashboard.svg",
    "monitoring.svg",
    "devices.svg",
    "operations.svg",
    "management.svg",
    ".topbar-dropdown > summary.topbar-link::before",
    "alerts.svg",
    "topology.svg",
    "secure-backup-storage.svg",
    "config-diff.svg",
    "automation-templates.svg",
]
URL_NAMES = [
    "switch_list", "backup_storage_status", "backup_center", "cisco_backup_center", "mikrotik_backup_center",
    "config_backups", "automation_templates", "action_logs", "reports", "topology", "sfp_monitor", "alarm_center",
]

class Command(BaseCommand):
    help = "Phase102 brand and navigation icon static/template guard. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        out = []
        failures = []
        report = {
            "phase": "PHASE102",
            "mode": "read_only_brand_icon_ui_guard_no_db_no_service_no_restore_no_ssh",
            "root": str(ROOT),
            "checks": [],
            "db_mutation": "NO",
            "service_restart": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
        }

        def ok(msg):
            out.append(f"OK={msg}")
            report["checks"].append({"status": "OK", "message": msg})

        def fail(msg):
            out.append(f"FAIL={msg}")
            failures.append(msg)
            report["checks"].append({"status": "FAIL", "message": msg})

        out.append("PHASE102_BRAND_ICONS_UI_CHECK_START")
        out.append("MODE=read_only_brand_icon_ui_guard_no_db_no_service_no_restore_no_ssh")
        out.append(f"ROOT={ROOT}")

        for rel in REQUIRED_FILES:
            p = ROOT / rel
            if p.exists() and p.stat().st_size > 0:
                ok(f"file_exists:{rel}")
            else:
                fail(f"missing_or_empty:{rel}")

        for icon in REQUIRED_ICONS:
            rel = f"inventory/static/inventory/brand/phase102/icons/{icon}.svg"
            p = ROOT / rel
            if p.exists() and p.stat().st_size > 0:
                ok(f"icon_exists:{icon}")
            else:
                fail(f"missing_icon:{icon}")

        base = ROOT / "inventory/templates/inventory/base.html"
        css = ROOT / "inventory/static/inventory/css/switchmap-phase102-brand-icons.css"
        base_text = base.read_text(encoding="utf-8") if base.exists() else ""
        css_text = css.read_text(encoding="utf-8") if css.exists() else ""
        for marker in BASE_MARKERS:
            if marker in base_text:
                ok(f"base_marker:{marker}")
            else:
                fail(f"base_marker_missing:{marker}")
        for marker in CSS_MARKERS:
            if marker in css_text:
                ok(f"css_marker:{marker}")
            else:
                fail(f"css_marker_missing:{marker}")

        for name in URL_NAMES:
            try:
                url = reverse(f"inventory:{name}")
                resolved = resolve(url).url_name
                ok(f"url_reverse_resolve:inventory:{name}:{url}:resolve={resolved}")
            except Exception as exc:
                fail(f"url_reverse_resolve_failed:inventory:{name}:{exc}")

        # staticfiles sync is not mandatory, but report when present.
        static_root = getattr(settings, "STATIC_ROOT", None)
        if static_root:
            static_phase102 = Path(static_root) / "inventory/brand/phase102"
            if static_phase102.exists():
                ok(f"staticfiles_phase102_present:{static_phase102}")
            else:
                out.append(f"WARNING=staticfiles_phase102_not_present:{static_phase102}")

        report["final_fail_count"] = len(failures)
        report["db_mutation"] = "NO"
        report["service_restart"] = "NO"
        report["restore_enable_change"] = "NO"
        report["ssh_execution"] = "NO"
        report["backup_write"] = "NO"
        if options.get("output"):
            p = Path(options["output"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            out.append(f"REPORT_JSON={p}")
        out.append(f"FINAL_FAIL_COUNT={len(failures)}")
        out.append("DB_MUTATION=NO")
        out.append("SERVICE_RESTART=NO")
        out.append("RESTORE_ENABLE_CHANGE=NO")
        out.append("SSH_EXECUTION=NO")
        out.append("BACKUP_WRITE=NO")
        if failures and options.get("strict"):
            out.append("PHASE102_BRAND_ICONS_UI_CHECK_FAIL")
            self.stdout.write("\n".join(out))
            raise CommandError("Phase102 brand icon UI check failed")
        out.append("PHASE102_BRAND_ICONS_UI_CHECK_OK")
        self.stdout.write("\n".join(out))
