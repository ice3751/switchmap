from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Port, Switch

PHASE = "67"
DEFAULT_CSV = Path("inventory") / "data" / "office_port_labels_phase67.csv"
VALID_FIELDS = {"description", "connected_device", "cable_label", "outlet"}

ALIASES = {
    "Edari-1": ["Edari-1", "Edari 1", "EDARI-1", "اداری-1", "اداری 1", "سوییچ اداری 1"],
    "Edari-2": ["Edari-2", "Edari 2", "EDARI-2", "اداری-2", "اداری 2", "سوییچ اداری 2"],
    "Edari-3": ["Edari-3", "Edari 3", "EDARI-3", "اداری-3", "اداری 3", "سوییچ اداری 3"],
    "Edari-4": ["Edari-4", "Edari 4", "EDARI-4", "اداری-4", "اداری 4", "سوییچ اداری 4"],
    "Edari-5": ["Edari-5", "Edari 5", "EDARI-5", "اداری-5", "اداری 5", "دوربین", "Camera", "CCTV"],
    "Edari-6": ["Edari-6", "Edari 6", "EDARI-6", "اداری-6", "اداری 6", "سوییچ اداری 6"],
}


def norm(value: str) -> str:
    return "".join(ch for ch in (value or "").casefold() if ch.isalnum())


def load_rows(path: Path) -> List[dict]:
    if not path.exists():
        raise CommandError(f"PHASE67_FAIL missing csv: {path}")
    rows: List[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"switch", "display_order", "label", "source_page"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise CommandError(f"PHASE67_FAIL csv missing columns: {sorted(required)}")
        for line_no, row in enumerate(reader, start=2):
            sw = (row.get("switch") or "").strip()
            label = (row.get("label") or "").strip()
            try:
                display_order = int((row.get("display_order") or "").strip())
            except ValueError:
                raise CommandError(f"PHASE67_FAIL invalid display_order at csv line {line_no}")
            if not sw or not label or display_order < 1 or display_order > 48:
                raise CommandError(f"PHASE67_FAIL invalid row at csv line {line_no}")
            rows.append({
                "switch": sw,
                "display_order": display_order,
                "label": label,
                "source_page": (row.get("source_page") or "").strip(),
                "source_note": (row.get("source_note") or "").strip(),
            })
    return rows


def find_switch(logical_name: str) -> Optional[Switch]:
    names = ALIASES.get(logical_name, [logical_name])
    all_switches = list(Switch.objects.all())
    # exact case-insensitive alias match
    alias_norms = {norm(x) for x in names + [logical_name]}
    matches = [s for s in all_switches if norm(s.name) in alias_norms]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CommandError(f"PHASE67_FAIL multiple switch matches for {logical_name}: {', '.join(s.name for s in matches)}")
    # substring fallback, useful when switch has location/model suffix
    matches = []
    for s in all_switches:
        ns = norm(s.name)
        if any(a and a in ns for a in alias_norms):
            matches.append(s)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CommandError(f"PHASE67_FAIL multiple switch matches for {logical_name}: {', '.join(s.name for s in matches)}")
    return None


def find_port(switch: Switch, display_order: int) -> Optional[Port]:
    port = switch.ports.filter(display_order=display_order).first()
    if port:
        return port
    suffixes = (f"/{display_order}", f"0/{display_order}", f"1/0/{display_order}")
    for candidate in switch.ports.all():
        name = (candidate.interface_name or "").strip()
        if any(name.endswith(sfx) for sfx in suffixes) or name == str(display_order):
            return candidate
    return None


def backup_database(dest_root: Path) -> Optional[Path]:
    db_name = settings.DATABASES.get("default", {}).get("NAME")
    if not db_name:
        return None
    db_path = Path(db_name)
    if not db_path.exists() or db_path.is_dir():
        return None
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / db_path.name
    shutil.copy2(db_path, dest)
    return dest


class Command(BaseCommand):
    help = "Import office switch port labels extracted from rack diagrams (Phase 67)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Mapping CSV path relative to project root or absolute path.")
        parser.add_argument("--field", default="description", choices=sorted(VALID_FIELDS), help="Port field to update. Default: description")
        parser.add_argument("--apply", action="store_true", help="Write changes. Without this flag only dry-run is performed.")
        parser.add_argument("--backup-db", action="store_true", help="Backup SQLite DB before writing.")
        parser.add_argument("--clear-missing", action="store_true", help="Clear target field on unmapped ports for matched switches. Default: off.")

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
        field = options["field"]
        apply = bool(options["apply"])
        clear_missing = bool(options["clear_missing"])

        rows = load_rows(csv_path)
        by_switch: Dict[str, List[dict]] = {}
        for row in rows:
            by_switch.setdefault(row["switch"], []).append(row)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path.cwd() / "reports" / f"phase67_office_port_labels_{stamp}"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / ("apply_report.csv" if apply else "dry_run_report.csv")

        if apply and options.get("backup_db"):
            backup_path = backup_database(Path.cwd() / "backups" / f"phase67_office_port_labels_{stamp}")
            if backup_path:
                self.stdout.write(f"PHASE67_DB_BACKUP={backup_path}")
            else:
                self.stdout.write("PHASE67_WARN db backup skipped; sqlite db file not found")

        summary = {"switches": 0, "mapped_rows": len(rows), "updated": 0, "unchanged": 0, "missing_switch": 0, "missing_port": 0, "cleared": 0}
        report_rows = []

        with transaction.atomic():
            for logical_name, switch_rows in by_switch.items():
                switch = find_switch(logical_name)
                if not switch:
                    summary["missing_switch"] += 1
                    for row in switch_rows:
                        report_rows.append({**row, "actual_switch": "", "interface_name": "", "old_value": "", "new_value": row["label"], "action": "missing_switch"})
                    continue
                summary["switches"] += 1
                mapped_ports = set()
                for row in sorted(switch_rows, key=lambda r: r["display_order"]):
                    mapped_ports.add(row["display_order"])
                    port = find_port(switch, row["display_order"])
                    if not port:
                        summary["missing_port"] += 1
                        report_rows.append({**row, "actual_switch": switch.name, "interface_name": "", "old_value": "", "new_value": row["label"], "action": "missing_port"})
                        continue
                    old_value = getattr(port, field) or ""
                    new_value = row["label"]
                    action = "unchanged" if old_value == new_value else ("update" if apply else "would_update")
                    if old_value == new_value:
                        summary["unchanged"] += 1
                    else:
                        summary["updated"] += 1
                        if apply:
                            setattr(port, field, new_value)
                            port.save(update_fields=[field, "updated_at"])
                    report_rows.append({**row, "actual_switch": switch.name, "interface_name": port.interface_name, "old_value": old_value, "new_value": new_value, "action": action})

                if clear_missing:
                    for port in switch.ports.exclude(display_order__in=mapped_ports):
                        old_value = getattr(port, field) or ""
                        if old_value:
                            action = "clear" if apply else "would_clear"
                            summary["cleared"] += 1
                            if apply:
                                setattr(port, field, "")
                                port.save(update_fields=[field, "updated_at"])
                            report_rows.append({"switch": logical_name, "display_order": port.display_order, "label": "", "source_page": "", "source_note": "clear_missing", "actual_switch": switch.name, "interface_name": port.interface_name, "old_value": old_value, "new_value": "", "action": action})

            if not apply:
                transaction.set_rollback(True)

        with report_path.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = ["switch", "display_order", "label", "source_page", "source_note", "actual_switch", "interface_name", "old_value", "new_value", "action"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader(); writer.writerows(report_rows)

        self.stdout.write(f"PHASE67_MODE={'APPLY' if apply else 'DRY_RUN'}")
        self.stdout.write(f"PHASE67_FIELD={field}")
        self.stdout.write(f"PHASE67_REPORT={report_path}")
        for key in ["switches", "mapped_rows", "updated", "unchanged", "missing_switch", "missing_port", "cleared"]:
            self.stdout.write(f"PHASE67_{key.upper()}={summary[key]}")
        if summary["missing_switch"] or summary["missing_port"]:
            raise CommandError("PHASE67_FAIL missing switch or port; inspect report")
        self.stdout.write("PHASE67_OK")
