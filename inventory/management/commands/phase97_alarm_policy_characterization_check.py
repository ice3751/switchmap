from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand, CommandError


PHASE = "PHASE98"


@dataclass
class CaseResult:
    name: str
    ok: bool
    expected: Any
    actual: Any
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "expected": self.expected,
            "actual": self.actual,
            "detail": self.detail,
        }


def ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def port(**kwargs: Any) -> SimpleNamespace:
    defaults = dict(
        id=0,
        switch_id=None,
        interface_name="Gi1/0/1",
        status="down",
        snmp_admin_status="up",
        snmp_oper_status="down",
        description="",
        snmp_alias="",
        connected_device="",
        neighbor_device="",
        neighbor_ip=None,
        neighbor_port="",
        owner="",
        cable_label="",
        patch_panel="",
        patch_panel_port="",
        notes="",
        documentation_status="undocumented",
        prtg_url="",
        ip_address=None,
        mac_address="",
    )
    defaults.update(kwargs)
    return ns(**defaults)


def alarm(**kwargs: Any) -> SimpleNamespace:
    defaults = dict(
        id=0,
        title="",
        message="",
        details="",
        source="",
        fingerprint="",
        category="",
        switch_id=None,
        port=None,
    )
    defaults.update(kwargs)
    return ns(**defaults)


def add_case(results: List[CaseResult], name: str, expected: Any, actual: Any, detail: str = "") -> None:
    results.append(CaseResult(name=name, ok=(actual == expected), expected=expected, actual=actual, detail=detail))


def count_top_level_defs(source: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for match in re.finditer(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source, flags=re.MULTILINE):
        name = match.group(1)
        counts[name] = counts.get(name, 0) + 1
    return counts


def run_characterization() -> Dict[str, Any]:
    import inventory.alarm_policy as policy

    source_path = Path(inspect.getsourcefile(policy) or "")
    source = source_path.read_text(encoding="utf-8", errors="replace") if source_path.exists() else ""
    definition_counts = count_top_level_defs(source)

    original_latest_err_disabled = getattr(policy, "_phase83r5_has_latest_err_disabled", None)
    original_latest_sfp = getattr(policy, "_latest_sfp_snapshot_for_port", None)

    # In-memory monkeypatch only: prevents DB reads while characterizing policy logic.
    policy._phase83r5_has_latest_err_disabled = lambda _port: False  # type: ignore[attr-defined]
    policy._latest_sfp_snapshot_for_port = lambda _port: None  # type: ignore[attr-defined]

    results: List[CaseResult] = []
    try:
        # Source-level characterization: Phase98 canonical cleanup should leave one public definition per policy function.
        add_case(results, "source.count.alarm_is_false_positive", 1, definition_counts.get("alarm_is_false_positive", 0))
        add_case(results, "source.count.is_actionable_port_error", 1, definition_counts.get("is_actionable_port_error", 0))
        add_case(results, "source.count.is_actionable_interface_down", 1, definition_counts.get("is_actionable_interface_down", 0))
        add_case(results, "source.count.is_explicitly_critical_port", 1, definition_counts.get("is_explicitly_critical_port", 0))

        # Interface/topology down policy.
        ordinary_down = port(status="down", snmp_oper_status="down", notes="uplink trunk core")
        tagged_down = port(status="down", snmp_oper_status="down", notes="alarm:critical uplink to core")
        tagged_admin_down = port(status="disabled", snmp_admin_status="down", snmp_oper_status="down", notes="alarm:critical")
        add_case(results, "interface_down.ordinary_text_is_not_actionable", False, policy.is_actionable_interface_down(ordinary_down))
        add_case(results, "interface_down.explicit_alarm_tag_is_actionable", True, policy.is_actionable_interface_down(tagged_down))
        add_case(results, "interface_down.admin_down_is_not_actionable", False, policy.is_actionable_interface_down(tagged_admin_down))

        fp, reason = policy.alarm_is_false_positive(alarm(
            title="Uplink / Neighbor Down",
            fingerprint="uplink-down:Gi1/0/1",
            category="topology",
            message="Gi1/0/1 is down",
            port=ordinary_down,
        ))
        add_case(results, "alarm.topology_down_without_explicit_tag_is_false_positive", (True, "topology_down_requires_explicit_alarm_monitor_tag"), (fp, reason))

        fp, reason = policy.alarm_is_false_positive(alarm(
            title="Uplink / Neighbor Down",
            fingerprint="uplink-down:Gi1/0/1",
            category="topology",
            message="Gi1/0/1 is down",
            port=tagged_down,
        ))
        add_case(results, "alarm.topology_down_with_explicit_tag_is_real", (False, ""), (fp, reason))

        # Port error policy: generic Port.Status.ERROR is not enough; explicit fault evidence is required.
        generic_error = port(status="error", snmp_oper_status="up", notes="auto visual placeholder")
        fault_error = port(status="error", snmp_oper_status="up", notes="err-disabled detected")
        add_case(results, "port_error.generic_error_without_fault_not_actionable", False, policy.is_actionable_port_error(generic_error))
        add_case(results, "port_error.explicit_fault_token_actionable", True, policy.is_actionable_port_error(fault_error))

        fp, reason = policy.alarm_is_false_positive(alarm(
            title="Port Error",
            fingerprint="port-error:Gi1/0/1",
            category="port",
            message="Port status error",
            port=generic_error,
        ))
        add_case(results, "alarm.port_error_without_fault_is_false_positive", (True, "phase83r5_port_error_without_explicit_fault_evidence"), (fp, reason))

        fp, reason = policy.alarm_is_false_positive(alarm(
            title="Port Error",
            fingerprint="port-error:Gi1/0/2",
            category="port",
            message="err-disabled",
            port=fault_error,
        ))
        add_case(results, "alarm.port_error_with_fault_is_real", (False, ""), (fp, reason))

        fp, reason = policy.alarm_is_false_positive(alarm(
            title="Visual placeholder",
            fingerprint="visual:auto",
            category="port",
            message="auto visual placeholder",
            port=generic_error,
        ))
        add_case(results, "alarm.auto_visual_placeholder_is_false_positive", (True, "phase83r5_auto_visual_placeholder_not_alarm"), (fp, reason))

        # Cisco CRC delta policy.
        up_port = port(status="up", snmp_oper_status="up")
        down_port = port(status="down", snmp_oper_status="down")
        add_case(results, "cisco_crc.link_down_not_actionable", (False, "port_not_up"), policy.cisco_crc_alarm_is_actionable(down_port, {"fcs_delta": 50}))
        add_case(results, "cisco_crc.below_threshold_not_actionable", (False, "physical_delta_below_threshold"), policy.cisco_crc_alarm_is_actionable(up_port, {"fcs_delta": 9}))
        add_case(results, "cisco_crc.threshold_actionable", (True, "physical_error_delta"), policy.cisco_crc_alarm_is_actionable(up_port, {"fcs_delta": 10}))

        # SFP label extraction: counter/power checks only on live links; temperature sanity is independent.
        add_case(results, "sfp_labels.down_link_counter_ignored", [], policy.sfp_issue_labels_from_values({"link_status": "down", "fcs_delta": 100}))
        add_case(results, "sfp_labels.up_link_crc_detected", ["CRC Increased"], policy.sfp_issue_labels_from_values({"link_status": "up", "fcs_delta": 10}))
        add_case(results, "sfp_labels.up_link_rx_power_detected", ["Rx Power abnormal"], policy.sfp_issue_labels_from_values({"link_status": "up", "rx_power_dbm": "-30", "rx_min_dbm": "-20", "rx_max_dbm": "0"}))
        add_case(results, "sfp_labels.temperature_sanity_detected", ["Temperature abnormal"], policy.sfp_issue_labels_from_values({"link_status": "down", "temperature_c": "100"}))

        # Direct text/tag helpers.
        stale = port(notes="alarm:critical old-network retired")
        tagged = port(notes="switchmap-monitor uplink")
        add_case(results, "tag.stale_alarm_tag_rejected", False, policy.has_explicit_alarm_monitor_tag(stale))
        add_case(results, "tag.explicit_monitor_tag_detected", True, policy.has_explicit_alarm_monitor_tag(tagged))
    finally:
        if original_latest_err_disabled is not None:
            policy._phase83r5_has_latest_err_disabled = original_latest_err_disabled  # type: ignore[attr-defined]
        if original_latest_sfp is not None:
            policy._latest_sfp_snapshot_for_port = original_latest_sfp  # type: ignore[attr-defined]

    failures = [r for r in results if not r.ok]
    warnings: List[str] = []
    if definition_counts.get("alarm_is_false_positive", 0) > 1:
        warnings.append("alarm_policy_has_shadowed_alarm_is_false_positive_definitions")
    if definition_counts.get("is_actionable_port_error", 0) > 1:
        warnings.append("alarm_policy_has_shadowed_is_actionable_port_error_definitions")

    return {
        "phase": PHASE,
        "mode": "read_only_in_memory_characterization_no_db_write_no_network_no_ssh_no_restore_no_service",
        "source_path": str(source_path),
        "definition_counts": definition_counts,
        "cases": [r.as_dict() for r in results],
        "warning_count": len(warnings),
        "warnings": warnings,
        "fail_count": len(failures),
        "failures": [r.as_dict() for r in failures],
        "final_ok": len(failures) == 0,
        "db_mutation": "NO",
        "service_restart": "NO",
        "restore_enable_change": "NO",
        "ssh_execution": "NO",
        "backup_write": "NO",
        "visible_test_data_created": "NO",
    }


def write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Phase97 Alarm Policy Characterization Report")
    lines.append("")
    lines.append(f"- Final OK: {report.get('final_ok')}")
    lines.append(f"- Source: {report.get('source_path')}")
    lines.append(f"- Fail Count: {report.get('fail_count')}")
    lines.append(f"- Warning Count: {report.get('warning_count')}")
    lines.append("")
    lines.append("## Definition Counts")
    lines.append("")
    for key in sorted(report.get("definition_counts", {})):
        value = report["definition_counts"][key]
        if value > 1 or key in {"alarm_is_false_positive", "is_actionable_port_error", "is_actionable_interface_down", "is_explicitly_critical_port"}:
            lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.append("| Case | OK | Expected | Actual |")
    lines.append("|---|---:|---|---|")
    for case in report.get("cases", []):
        lines.append(f"| {case['name']} | {case['ok']} | `{case['expected']}` | `{case['actual']}` |")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    warnings = report.get("warnings", [])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("DB_MUTATION=NO")
    lines.append("SERVICE_RESTART=NO")
    lines.append("RESTORE_ENABLE_CHANGE=NO")
    lines.append("SSH_EXECUTION=NO")
    lines.append("BACKUP_WRITE=NO")
    lines.append("VISIBLE_TEST_DATA_CREATED=NO")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "Phase98 canonical alarm policy characterization tests."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        self.stdout.write("PHASE97_ALARM_POLICY_CHARACTERIZATION_CHECK_START")
        self.stdout.write("MODE=read_only_in_memory_no_db_write_no_network_no_ssh_no_restore_no_service")
        report = run_characterization()

        output = options.get("output") or ""
        report_json = Path(output) if output else None
        report_md = None
        if report_json:
            report_json.parent.mkdir(parents=True, exist_ok=True)
            report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report_md = report_json.with_suffix(".md")
            write_markdown(report_md, report)

        for case in report.get("cases", []):
            prefix = "OK" if case["ok"] else "FAIL"
            self.stdout.write(f"{prefix}=case:{case['name']}")
            if not case["ok"]:
                self.stdout.write(f"DETAIL={case['name']}:expected={case['expected']}:actual={case['actual']}")

        for warning in report.get("warnings", []):
            self.stdout.write(f"WARNING={warning}")

        if report_json:
            self.stdout.write(f"REPORT_JSON={report_json}")
        if report_md:
            self.stdout.write(f"REPORT_MD={report_md}")
        self.stdout.write(f"FINAL_WARNING_COUNT={report.get('warning_count')}")
        self.stdout.write(f"FINAL_FAIL_COUNT={report.get('fail_count')}")
        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("SERVICE_RESTART=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("BACKUP_WRITE=NO")
        self.stdout.write("VISIBLE_TEST_DATA_CREATED=NO")

        if report.get("fail_count", 0):
            self.stdout.write("PHASE97_ALARM_POLICY_CHARACTERIZATION_CHECK_FAIL")
            raise CommandError("Phase97 alarm policy characterization failed")
        self.stdout.write("PHASE97_ALARM_POLICY_CHARACTERIZATION_CHECK_OK")
