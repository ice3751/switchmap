from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import resolve, reverse

PHASE = "PHASE103R10"


def add(results: List[Dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


class Command(BaseCommand):
    help = "Phase103R10 dashboard four-card UI guard. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        results: List[Dict[str, Any]] = []
        self.stdout.write("PHASE103R10_DASHBOARD_CARDS_UI_CHECK_START")
        self.stdout.write("MODE=read_only_template_static_guard_no_db_no_service_no_restore_no_ssh")
        self.stdout.write(f"ROOT={root}")

        template = root / "inventory" / "templates" / "inventory" / "switch_list.html"
        css = root / "inventory" / "static" / "inventory" / "css" / "switchmap-phase103-dashboard-cards.css"
        icon_dir = root / "inventory" / "static" / "inventory" / "brand" / "phase103" / "icons"
        icon_files = [
            icon_dir / "card-connectivity.svg",
            icon_dir / "card-urgent.svg",
            icon_dir / "card-alarms.svg",
            icon_dir / "card-topology.svg",
            icon_dir / "card-topology-map.svg",
        ]

        for path in [template, css] + icon_files:
            add(results, "file_exists", path.exists(), str(path.relative_to(root)).replace("\\", "/"))

        template_text = read_text(template)
        required_template_markers = [
            "data-phase103-dashboard-cards",
            "switchmap-phase103-dashboard-cards.css",
            "phase103R10-dashboard-cards-codex-reviewed-fix",
            "Phase103 Dashboard Cards Visual Refine",
            "phase103-card-connectivity",
            "phase103-card-critical",
            "phase103-card-alarms",
            "phase103-card-topology",
            "data-dashboard-connectivity-card",
            "data-dashboard-primary-action",
            "data-dashboard-actions",
            "data-dashboard-alarms",
            "data-dashboard-topology-issues",
            "data-field-style=\"coverage_percent\"",
            "data-field=\"coverage_percent\"",
            "data-field=\"attention\"",
            "data-field=\"active_alarms\"",
            "data-field=\"topology_issues\"",
            "phase103-note-connectivity",
            "phase103-note-warning",
            "phase103-note-info",
            "phase103-topology-discovery",
            "phase103-topology-sfp",
            "phase103-topology-link",
        ]
        for marker in required_template_markers:
            add(results, f"template_marker:{marker}", marker in template_text)

        forbidden_template_markers = [
            "SwitchMap_Phase103_Cards_Fix_Candidate.zip",
            "codex_phase103_card_fix_candidate",
            "VISIBLE_TEST_DATA_CREATED=YES",
        ]
        for marker in forbidden_template_markers:
            add(results, f"template_forbidden_absent:{marker}", marker not in template_text)

        css_text = read_text(css)
        required_css_markers = [
            "Phase103R10 dashboard cards Codex-reviewed fix",
            "phase103R10-dashboard-cards-codex-reviewed-fix",
            "#sm-main-dashboard[data-phase103-dashboard-cards] .sm-main-grid",
            "grid-auto-rows: 392px",
            "height: 392px",
            "max-height: 392px",
            ".phase103-card-connectivity",
            ".phase103-card-critical",
            ".phase103-card-alarms",
            ".phase103-card-topology",
            ".phase103-card-critical::before",
            ".phase103-card-topology::before",
            "card-connectivity.svg",
            "card-urgent.svg",
            "card-alarms.svg",
            "card-topology.svg",
            "card-topology-map.svg",
            "phase103-topology-visual",
            "phase103-note-connectivity",
            "phase103-note-warning",
            "phase103-note-info",
            "@media (max-width: 1080px)",
            "@media (max-width: 620px)",
        ]
        for marker in required_css_markers:
            add(results, f"css_marker:{marker}", marker in css_text)
        add(results, "css_brace_balance", css_text.count("{") == css_text.count("}"), f"open={css_text.count('{')} close={css_text.count('}')}")
        add(results, "css_no_old_300px_fixed_card", "height:300px" not in css_text and "min-height:300px" not in css_text)

        for svg_path in icon_files:
            try:
                ET.parse(str(svg_path))
                add(results, "svg_xml_well_formed", True, svg_path.name)
            except Exception as exc:
                add(results, "svg_xml_well_formed", False, f"{svg_path.name}:{exc}")

        for name in [
            "inventory:switch_list",
            "inventory:switchmap_dashboard_data",
            "inventory:alarm_center",
            "inventory:topology",
            "inventory:backup_storage_status",
        ]:
            try:
                url = reverse(name)
                match = resolve(url)
                add(results, f"url_reverse_resolve:{name}", True, f"{url}:resolve={match.url_name}")
            except Exception as exc:
                add(results, f"url_reverse_resolve:{name}", False, str(exc))

        staticfiles = root / "staticfiles"
        if staticfiles.exists():
            static_targets = [
                staticfiles / "inventory" / "css" / "switchmap-phase103-dashboard-cards.css",
                staticfiles / "inventory" / "brand" / "phase103" / "icons" / "card-connectivity.svg",
                staticfiles / "inventory" / "brand" / "phase103" / "icons" / "card-urgent.svg",
                staticfiles / "inventory" / "brand" / "phase103" / "icons" / "card-alarms.svg",
                staticfiles / "inventory" / "brand" / "phase103" / "icons" / "card-topology.svg",
                staticfiles / "inventory" / "brand" / "phase103" / "icons" / "card-topology-map.svg",
            ]
            for path in static_targets:
                add(results, "staticfiles_target_present", path.exists(), str(path.relative_to(root)).replace("\\", "/"))
        else:
            add(results, "staticfiles_dir_absent_skip", True, "collectstatic target not present before production sync")

        failures = [item for item in results if not item["ok"]]
        report = {
            "phase": PHASE,
            "root": str(root),
            "results": results,
            "final_fail_count": len(failures),
            "final_ok": len(failures) == 0,
            "db_mutation": "NO",
            "service_restart": "NO",
            "migration_write": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "operational_backup_write": "NO",
            "visible_test_data_created": "NO",
        }

        output = options.get("output") or ""
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"REPORT_JSON={out_path}")

        for item in results:
            prefix = "OK" if item["ok"] else "FAIL"
            detail = f":{item['detail']}" if item.get("detail") else ""
            self.stdout.write(f"{prefix}={item['name']}{detail}")

        self.stdout.write(f"FINAL_FAIL_COUNT={len(failures)}")
        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("SERVICE_RESTART=NO")
        self.stdout.write("MIGRATION_WRITE=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("OPERATIONAL_BACKUP_WRITE=NO")
        self.stdout.write("VISIBLE_TEST_DATA_CREATED=NO")

        if failures:
            self.stdout.write("PHASE103R10_DASHBOARD_CARDS_UI_CHECK_FAIL")
            if options.get("strict"):
                raise CommandError("Phase103R10 dashboard cards UI check failed")
        else:
            self.stdout.write("PHASE103R10_DASHBOARD_CARDS_UI_CHECK_OK")
