from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from inventory.models import Switch
from inventory.secure_credentials import SecureCredentialError, load_ssh_monitor_credentials
from inventory.ssh_tools import run_switch_show_commands

try:
    from inventory.cisco_backup_tools import cisco_switches
except Exception:  # pragma: no cover
    cisco_switches = None

try:
    from inventory.mikrotik_backup_tools import mikrotik_switches, run_routeros_command
except Exception:  # pragma: no cover
    mikrotik_switches = None
    run_routeros_command = None

PHASE88_MARKER = "PHASE88_BACKUP_COVERAGE_AUDIT_REVIEWED"
REPORT_DIR = Path(settings.BASE_DIR) / "logs"
MAX_REASON_LEN = 700


def _clean_reason(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"(?i)(password\s*[=:]\s*)\S+", r"\1<MASKED>", text)
    text = re.sub(r"(?i)(secret\s*[=:]\s*)\S+", r"\1<MASKED>", text)
    return text[:MAX_REASON_LEN]


def _text(switch: Switch) -> str:
    parts = []
    for field in ("vendor", "device_family", "model", "name", "notes"):
        try:
            parts.append(str(getattr(switch, field, "") or ""))
        except Exception:
            pass
    return " ".join(parts).lower()


def _is_cisco(switch: Switch) -> bool:
    text = _text(switch)
    if any(token in text for token in ("mikrotik", "routeros", "routerboard")):
        return False
    return any(token in text for token in ("cisco", "catalyst", "nexus", "ios", "nx-os", "nxos", "3850", "2960", "3750", "9300", "9500"))


def _is_mikrotik(switch: Switch) -> bool:
    text = _text(switch)
    if "cisco" in text:
        return False
    return any(token in text for token in ("mikrotik", "routeros", "routerboard", "rb5009", "rb2011", "crs", "hap", "hex", "cap-", "chr"))


def _cisco_candidates() -> List[Switch]:
    if cisco_switches is not None:
        return list(cisco_switches())
    return [sw for sw in Switch.objects.filter(is_active=True).order_by("topology_position", "name") if _is_cisco(sw)]


def _mikrotik_candidates() -> List[Switch]:
    if mikrotik_switches is not None:
        return list(mikrotik_switches())
    return [sw for sw in Switch.objects.filter(is_active=True).order_by("topology_position", "name") if _is_mikrotik(sw)]


def _device_row(switch: Switch, profile: str) -> Dict:
    return {
        "profile": profile,
        "id": int(switch.id),
        "name": str(switch.name or ""),
        "management_ip": str(switch.management_ip or ""),
        "vendor": str(getattr(switch, "vendor", "") or ""),
        "device_family": str(getattr(switch, "device_family", "") or ""),
        "model": str(getattr(switch, "model", "") or ""),
        "is_active": bool(getattr(switch, "is_active", False)),
        "ssh_enabled": bool(getattr(switch, "ssh_enabled", False)),
        "ssh_port": int(getattr(switch, "ssh_port", 22) or 22),
        "status": "UNKNOWN",
        "reason": "",
        "tested_at": timezone.localtime().isoformat(),
        "duration_sec": 0.0,
    }


def _test_cisco(switch: Switch, credential: Dict) -> Dict:
    row = _device_row(switch, "cisco")
    if not row["ssh_enabled"]:
        row["status"] = "SKIP"
        row["reason"] = "SSH disabled"
        return row
    start = time.time()
    try:
        run_switch_show_commands(
            switch=switch,
            username=credential.get("username", ""),
            password=credential.get("password", ""),
            enable_password=credential.get("enable_password", ""),
            commands=["show clock"],
            command_wait=1.0,
        )
        row["status"] = "READY"
        row["reason"] = "SSH credential OK"
    except Exception as exc:
        row["status"] = "FAIL"
        row["reason"] = _clean_reason(exc)
    finally:
        row["duration_sec"] = round(time.time() - start, 2)
    return row


def _test_mikrotik(switch: Switch, credential: Dict) -> Dict:
    row = _device_row(switch, "mikrotik")
    if not row["ssh_enabled"]:
        row["status"] = "SKIP"
        row["reason"] = "SSH disabled"
        return row
    if run_routeros_command is None:
        row["status"] = "FAIL"
        row["reason"] = "mikrotik_backup_tools.run_routeros_command unavailable"
        return row
    start = time.time()
    try:
        run_routeros_command(
            switch,
            username=credential.get("username", ""),
            password=credential.get("password", ""),
            command="/system identity print",
            timeout=25,
        )
        row["status"] = "READY"
        row["reason"] = "SSH credential OK for RouterOS export test"
    except Exception as exc:
        row["status"] = "FAIL"
        row["reason"] = _clean_reason(exc)
    finally:
        row["duration_sec"] = round(time.time() - start, 2)
    return row


def _ids(rows: List[Dict], profile: str, status: str) -> List[int]:
    return [int(row["id"]) for row in rows if row["profile"] == profile and row["status"] == status]


class Command(BaseCommand):
    help = "Phase88: audit backup coverage candidates and SSH credential readiness without changing scheduled backup."

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=["all", "cisco", "mikrotik"], default="all")
        parser.add_argument("--candidate-only", action="store_true", help="Only list candidates; do not open SSH sessions.")
        parser.add_argument("--no-report", action="store_true", help="Do not write JSON report.")
        parser.add_argument("--fail-on-device-fail", action="store_true", help="Return non-zero if any tested device fails.")

    def handle(self, *args, **options):
        profile = options.get("profile") or "all"
        candidate_only = bool(options.get("candidate_only"))
        fail_on_device_fail = bool(options.get("fail_on_device_fail"))
        self.stdout.write("PHASE88_BACKUP_COVERAGE_AUDIT_START")
        self.stdout.write(f"MODE={'candidate-only' if candidate_only else 'credential-test'}")

        all_rows: List[Dict] = []
        credential_cache: Dict[str, Dict] = {}

        def get_credential(name: str) -> Dict:
            if name not in credential_cache:
                credential_cache[name] = load_ssh_monitor_credentials(profile=name)
            return credential_cache[name]

        if profile in {"all", "cisco"}:
            devices = _cisco_candidates()
            self.stdout.write(f"CISCO_CANDIDATES={len(devices)}")
            if candidate_only:
                rows = [_device_row(sw, "cisco") for sw in devices]
                for row in rows:
                    row["status"] = "CANDIDATE"
                    row["reason"] = "not tested"
            else:
                try:
                    cred = get_credential("cisco")
                    rows = [_test_cisco(sw, cred) for sw in devices]
                except SecureCredentialError as exc:
                    rows = []
                    self.stdout.write(f"CISCO_CREDENTIAL_FAIL={_clean_reason(exc)}")
                    for sw in devices:
                        row = _device_row(sw, "cisco")
                        row["status"] = "FAIL"
                        row["reason"] = f"Credential error: {_clean_reason(exc)}"
                        rows.append(row)
            all_rows.extend(rows)

        if profile in {"all", "mikrotik"}:
            devices = _mikrotik_candidates()
            self.stdout.write(f"MIKROTIK_CANDIDATES={len(devices)}")
            if candidate_only:
                rows = [_device_row(sw, "mikrotik") for sw in devices]
                for row in rows:
                    row["status"] = "CANDIDATE"
                    row["reason"] = "not tested"
            else:
                try:
                    cred = get_credential("mikrotik")
                    rows = [_test_mikrotik(sw, cred) for sw in devices]
                except SecureCredentialError as exc:
                    rows = []
                    self.stdout.write(f"MIKROTIK_CREDENTIAL_FAIL={_clean_reason(exc)}")
                    for sw in devices:
                        row = _device_row(sw, "mikrotik")
                        row["status"] = "FAIL"
                        row["reason"] = f"Credential error: {_clean_reason(exc)}"
                        rows.append(row)
            all_rows.extend(rows)

        cisco_candidate = _ids(all_rows, "cisco", "CANDIDATE")
        mt_candidate = _ids(all_rows, "mikrotik", "CANDIDATE")
        cisco_ready = _ids(all_rows, "cisco", "READY")
        cisco_fail = _ids(all_rows, "cisco", "FAIL")
        cisco_skip = _ids(all_rows, "cisco", "SKIP")
        mt_ready = _ids(all_rows, "mikrotik", "READY")
        mt_fail = _ids(all_rows, "mikrotik", "FAIL")
        mt_skip = _ids(all_rows, "mikrotik", "SKIP")

        for row in all_rows:
            self.stdout.write(
                "DEVICE "
                f"profile={row['profile']} id={row['id']} name={row['name']} ip={row['management_ip']} "
                f"ssh={row['ssh_enabled']} status={row['status']} reason={row['reason']}"
            )

        self.stdout.write("CISCO_CANDIDATE_IDS=" + ",".join(str(x) for x in cisco_candidate))
        self.stdout.write("MIKROTIK_CANDIDATE_IDS=" + ",".join(str(x) for x in mt_candidate))
        self.stdout.write("CISCO_READY_IDS=" + ",".join(str(x) for x in cisco_ready))
        self.stdout.write("CISCO_FAIL_IDS=" + ",".join(str(x) for x in cisco_fail))
        self.stdout.write("CISCO_SKIP_IDS=" + ",".join(str(x) for x in cisco_skip))
        self.stdout.write("MIKROTIK_READY_EXPORT_IDS=" + ",".join(str(x) for x in mt_ready))
        self.stdout.write("MIKROTIK_FAIL_IDS=" + ",".join(str(x) for x in mt_fail))
        self.stdout.write("MIKROTIK_SKIP_IDS=" + ",".join(str(x) for x in mt_skip))
        total_ready = len(cisco_ready) + len(mt_ready)
        total_fail = len(cisco_fail) + len(mt_fail)
        total_skip = len(cisco_skip) + len(mt_skip)
        total_candidate = len(cisco_candidate) + len(mt_candidate)
        self.stdout.write(f"TOTAL_CANDIDATE={total_candidate}")
        self.stdout.write(f"TOTAL_READY={total_ready}")
        self.stdout.write(f"TOTAL_FAIL={total_fail}")
        self.stdout.write(f"TOTAL_SKIP={total_skip}")

        if not options.get("no_report", False):
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
            report = {
                "marker": PHASE88_MARKER,
                "created_at": timezone.localtime().isoformat(),
                "mode": "candidate-only" if candidate_only else "credential-test",
                "summary": {
                    "cisco_candidate_ids": cisco_candidate,
                    "mikrotik_candidate_ids": mt_candidate,
                    "cisco_ready_ids": cisco_ready,
                    "cisco_fail_ids": cisco_fail,
                    "cisco_skip_ids": cisco_skip,
                    "mikrotik_ready_export_ids": mt_ready,
                    "mikrotik_fail_ids": mt_fail,
                    "mikrotik_skip_ids": mt_skip,
                    "total_candidate": total_candidate,
                    "total_ready": total_ready,
                    "total_fail": total_fail,
                    "total_skip": total_skip,
                },
                "devices": all_rows,
            }
            json_text = json.dumps(report, ensure_ascii=False, indent=2)
            json_path = REPORT_DIR / f"phase88_backup_coverage_audit_{stamp}.json"
            json_path.write_text(json_text, encoding="utf-8")
            latest_path = REPORT_DIR / "phase88_backup_coverage_audit_latest.json"
            latest_path.write_text(json_text, encoding="utf-8")
            self.stdout.write(f"REPORT={json_path}")
            self.stdout.write(f"REPORT_LATEST={latest_path}")

        self.stdout.write("PHASE88_BACKUP_COVERAGE_AUDIT_DONE")
        if fail_on_device_fail and total_fail:
            raise CommandError(f"PHASE88_BACKUP_COVERAGE_AUDIT_DEVICE_FAIL total_fail={total_fail}")
