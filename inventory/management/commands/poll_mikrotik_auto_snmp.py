from __future__ import annotations

import re
from typing import Iterable

from django.core.management.base import BaseCommand

from inventory.models import RouterHealthSnapshot, Switch
from inventory.snmp_tools import test_snmp_connection


MIKROTIK_AUTO_SNMP_MARKER = "Phase 60 Auto SNMP Monitoring"

MIKROTIK_NAME_HINTS = (
    "mikrotik",
    "routeros",
    "rb5009",
    "rb2011",
    "rb450",
    "hex",
    "hex-s",
    "crs",
    "ax3",
    "hap",
    "cap",
    "chr",
    "vps",
)

SWITCHMAP_TEST_DEVICE_TOKENS = (
    "smoke",
    "test",
    "phase41",
    "phase42",
    "phase43",
    "phase48",
    "phase50",
    "phase55",
    "switchmap-phase",
    "switchmap_phase",
)


def _text_blob(switch: Switch) -> str:
    return " ".join(
        [
            switch.name or "",
            switch.model or "",
            switch.location or "",
            switch.site or "",
            str(switch.management_ip or ""),
            switch.notes or "",
            getattr(switch, "vendor", "") or "",
            getattr(switch, "device_family", "") or "",
        ]
    ).lower()


def _is_switchmap_test_device(switch: Switch) -> bool:
    blob = _text_blob(switch)
    return any(token in blob for token in SWITCHMAP_TEST_DEVICE_TOKENS)


def _is_mikrotik_candidate(switch: Switch) -> bool:
    if _is_switchmap_test_device(switch):
        return False
    if getattr(switch, "vendor", "") == Switch.Vendor.MIKROTIK:
        return True
    blob = _text_blob(switch)
    return any(token.lower() in blob for token in MIKROTIK_NAME_HINTS)


def _routeros_version_from_sysdescr(value: str) -> str:
    text = str(value or "")
    patterns = [
        r"RouterOS\s+([0-9][^\s,;)]*)",
        r"version\s+([0-9][^\s,;)]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _candidate_queryset(include_inactive: bool = False) -> Iterable[Switch]:
    queryset = Switch.objects.all().order_by("topology_position", "name")
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return [switch for switch in queryset if _is_mikrotik_candidate(switch)]


class Command(BaseCommand):
    help = "Phase 60: run read-only automatic SNMP baseline polling for MikroTik devices."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--include-inactive", action="store_true")

    def handle(self, *args, **options):
        limit = max(0, int(options.get("limit") or 0))
        quiet = bool(options.get("quiet"))
        switches = list(_candidate_queryset(include_inactive=bool(options.get("include_inactive"))))
        if limit:
            switches = switches[:limit]

        counters = {
            "devices": len(switches),
            "pollable": 0,
            "up": 0,
            "down": 0,
            "skipped": 0,
        }

        for switch in switches:
            if not switch.snmp_enabled or not str(switch.snmp_community or "").strip():
                counters["skipped"] += 1
                continue

            counters["pollable"] += 1
            try:
                result = test_snmp_connection(switch)
            except Exception as exc:
                result = {"ok": False, "error": str(exc), "value": ""}

            ok = bool(result.get("ok"))
            status = RouterHealthSnapshot.HealthStatus.UP if ok else RouterHealthSnapshot.HealthStatus.DOWN
            if ok:
                counters["up"] += 1
            else:
                counters["down"] += 1

            raw_value = str(result.get("value") or result.get("error") or result.get("message") or "")
            RouterHealthSnapshot.objects.create(
                switch=switch,
                status=status,
                source=RouterHealthSnapshot.Source.SNMP,
                routeros_version=_routeros_version_from_sysdescr(raw_value),
                raw_summary=raw_value[:2000],
                notes="AUTO_SNMP_OK" if ok else f"AUTO_SNMP_FAILED: {raw_value[:500]}",
            )

        summary = (
            "PHASE60_AUTO_SNMP_POLL "
            f"devices={counters['devices']} "
            f"pollable={counters['pollable']} "
            f"up={counters['up']} "
            f"down={counters['down']} "
            f"skipped={counters['skipped']}"
        )
        if not quiet:
            self.stdout.write(summary)
        return summary
