from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.backup_schedule_policy import ids, load_policy, schedule_candidates

try:
    from inventory.backup_storage_tools import load_all_backup_rows
except Exception:  # pragma: no cover
    load_all_backup_rows = None

PHASE89_HEALTH_MARKER = "PHASE89_BACKUP_HEALTH_REPORT"
REPORT_DIR = Path(settings.BASE_DIR) / "logs"


def _parse_dt(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except Exception:
        return None


def _row_device_id(row: Dict) -> Optional[int]:
    for key in ("device_id", "switch_id"):
        try:
            if row.get(key) not in (None, ""):
                return int(row.get(key))
        except Exception:
            pass
    return None


def _row_type(row: Dict) -> str:
    return str(row.get("backup_type") or row.get("type") or "").strip()


def _latest_success(rows: List[Dict], device_id: int, backup_type: str) -> Optional[Dict]:
    matches = []
    for row in rows:
        if not row.get("success"):
            continue
        if _row_device_id(row) != int(device_id):
            continue
        if _row_type(row) != backup_type:
            continue
        matches.append(row)
    matches.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return matches[0] if matches else None


class Command(BaseCommand):
    help = "Phase89: backup health report based on expected dynamic schedule coverage."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Return non-zero on missing or stale expected backups.")
        parser.add_argument("--stale-hours", type=float, default=None)
        parser.add_argument("--json-only", action="store_true")

    def handle(self, *args, **options):
        if load_all_backup_rows is None:
            raise SystemExit("backup_storage_tools.load_all_backup_rows unavailable")

        policy = load_policy(create=True)
        stale_hours = float(options.get("stale_hours") or policy.get("stale_hours") or 36)
        strict = bool(options.get("strict"))
        json_only = bool(options.get("json_only"))
        plan = schedule_candidates(policy)
        rows = load_all_backup_rows()
        now = timezone.now()

        expected: List[Tuple[str, int, str]] = []
        for sid in ids(plan["cisco"]):
            for typ in plan["cisco_types"]:
                expected.append(("cisco", sid, str(typ)))
        for sid in ids(plan["mikrotik_export"]):
            for typ in plan["mikrotik_export_types"]:
                expected.append(("mikrotik", sid, str(typ)))
        for sid in ids(plan["mikrotik_full"]):
            for typ in plan["mikrotik_full_types"]:
                expected.append(("mikrotik", sid, str(typ)))

        items = []
        missing = 0
        stale = 0
        ok = 0
        for family, sid, typ in expected:
            row = _latest_success(rows, sid, typ)
            status = "OK"
            age_hours = None
            created_at = None
            backup_id = None
            file_path = None
            if not row:
                status = "MISSING"
                missing += 1
            else:
                created = _parse_dt(row.get("created_at"))
                created_at = str(row.get("created_at") or "")
                backup_id = row.get("backup_id")
                file_path = row.get("file_path")
                if created:
                    age_hours = round((now - created).total_seconds() / 3600.0, 2)
                    if age_hours > stale_hours:
                        status = "STALE"
                        stale += 1
                    else:
                        ok += 1
                else:
                    status = "STALE"
                    stale += 1
            items.append({
                "family": family,
                "device_id": sid,
                "backup_type": typ,
                "status": status,
                "age_hours": age_hours,
                "created_at": created_at,
                "backup_id": backup_id,
                "file_path": file_path,
            })

        report = {
            "marker": PHASE89_HEALTH_MARKER,
            "generated_at": timezone.localtime().isoformat(),
            "stale_hours": stale_hours,
            "expected_count": len(expected),
            "ok_count": ok,
            "missing_count": missing,
            "stale_count": stale,
            "health_ok": missing == 0 and stale == 0,
            "items": items,
            "policy_path": str(plan["policy_path"]),
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        json_path = REPORT_DIR / f"backup_health_report_{stamp}.json"
        latest_json = REPORT_DIR / "backup_health_report_latest.json"
        txt_path = REPORT_DIR / "backup_health_report_latest.txt"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        latest_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "PHASE89_BACKUP_HEALTH_REPORT",
            f"GENERATED_AT={report['generated_at']}",
            f"HEALTH_OK={report['health_ok']}",
            f"EXPECTED={report['expected_count']}",
            f"OK={report['ok_count']}",
            f"MISSING={report['missing_count']}",
            f"STALE={report['stale_count']}",
            f"REPORT_JSON={latest_json}",
        ]
        for item in items:
            if item["status"] != "OK":
                lines.append(f"ISSUE family={item['family']} id={item['device_id']} type={item['backup_type']} status={item['status']} age_hours={item['age_hours']}")
        txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if not json_only:
            for line in lines:
                self.stdout.write(line)
        if strict and not report["health_ok"]:
            raise SystemExit(1)
