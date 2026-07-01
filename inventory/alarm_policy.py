from __future__ import annotations

# PHASE98_CANONICAL_ALARM_POLICY
# Canonical, behavior-preserving cleanup of Phase83R/83R2/83R4/83R5 policy layers.
# The historical shadowed definitions were collapsed into one public definition per policy function.

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

UP_LINK_STATES = {"up", "connected", "connect", "operational", "1"}
DOWN_LINK_STATES = {
    "down", "notconnect", "not connected", "inactive", "no carrier",
    "lowerlayerdown", "lower layer down", "2",
}
NOT_PRESENT_STATES = {"sfpabsent", "xcvrabsent", "notpresent", "not present", "missing", "absent", "6"}
ADMIN_DOWN_STATES = {"disabled", "admin-down", "admin down", "shutdown", "administratively down", "down admin"}
OPTICAL_POWER_TITLES = {"Rx Power abnormal", "Tx Power abnormal"}
SFP_COUNTER_TITLES = {"CRC Increased", "Input Error", "Output Error", "Out Discards"}

# Conservative floors; zero/one-off deltas are not operational alarms.
CRC_DELTA_WARNING = 10
INPUT_OUTPUT_DELTA_WARNING = 10
DISCARD_DELTA_WARNING = 0  # Discard-only is not an alarm source in Phase83.1.
SFP_TEMP_MIN_SANITY_C = Decimal("-40.00")
SFP_TEMP_MAX_SANITY_C = Decimal("85.00")

PLACEHOLDER_VALUES = {
    "", "-", "--", "---", "—", "_", ":", "::", "n/a", "na", "none", "null",
    "unknown", "unk", "neighbor", "neighbour", ":neighbor", "-:neighbor", "neighbor:",
    "not set", "not-set", "unused", "spare", "empty",
}

ACTIONABLE_KEYWORDS = (
    "uplink", "up-link", "up link", "core", "nexus", "router", "firewall", "wan",
    "server", "esxi", "vmware", "storage", "record", "rec", "prtg", "critical",
    "monitor", "trunk-to", "link-to", "to-", "backup", "internet", "isp", "mikrotik",
    "switch", "distribution", "aggregate", "aggregation", "san", "nas", "vcenter",
)

NETWORK_DEVICE_TYPES = {"switch", "uplink", "server", "access_point"}

STALE_OR_DECOMMISSIONED_KEYWORDS = (
    "old-network", "old network", "old_net", "old-net", "decommission",
    "decommissioned", "removed", "retired", "unused", "spare", "رزرو",
    "قدیمی", "حذف",
)

STRICT_ALARM_MONITOR_TAGS = (
    "alarm:critical",
    "alarm=critical",
    "alarm:uplink",
    "monitor:critical",
    "monitor=uplink",
    "monitor-critical",
    "switchmap-monitor",
    "switchmap:monitor",
    "critical-monitor",
    "مانیتور:critical",
)

# Backward-compatible alias for older helper names.
EXPLICIT_MONITORING_KEYWORDS = STRICT_ALARM_MONITOR_TAGS

PORT_ERROR_FAULT_TOKENS = (
    "err-disabled",
    "errdisabled",
    "error-disabled",
    "error disabled",
    "fault",
    "faulty",
    "failed",
    "failure",
    "xcvr invalid",
    "transceiver invalid",
    "sfp invalid",
    "gbic-invalid",
    "link-flap",
    "link flap",
)
PORT_ERROR_BENIGN_OPER_STATES = (
    "down",
    "notpresent",
    "not present",
    "dormant",
    "lowerlayerdown",
    "lower layer down",
    "unknown",
    "testing",
    "",
)

_PHASE83R5_AUTO_VISUAL = "auto visual placeholder"
_PHASE83R5_FAULT_TOKENS = (
    "err-disabled", "errdisabled", "error-disabled", "error disabled",
    "gbic-invalid", "sfp invalid", "xcvr invalid", "transceiver invalid",
    "fault", "faulty", "hardware failure", "failed", "failure",
    "link-flap", "link flap", "port-security", "bpduguard", "bpdu guard",
)
_PHASE83R5_BENIGN_OPER = {
    "", "down", "notconnect", "not connected", "notpresent", "not present",
    "lowerlayerdown", "lower layer down", "dormant", "unknown", "testing",
    "absent", "missing", "sfpabsent", "xcvrabsent",
}


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def compact_lower(value: Any) -> str:
    return compact(value).lower()


def is_meaningful_text(value: Any) -> bool:
    text = compact_lower(value)
    if text in PLACEHOLDER_VALUES:
        return False
    if not text:
        return False
    if not re.search(r"[a-z0-9آ-ی]", text, re.IGNORECASE):
        return False
    return True


def to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def to_decimal(value: Any):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def link_status_text_from_snapshot(item: Any) -> str:
    return norm(getattr(item, "link_status", ""))


def port_oper_text(port: Any) -> str:
    return norm(getattr(port, "snmp_oper_status", "") or getattr(port, "status", ""))


def port_admin_text(port: Any) -> str:
    return norm(getattr(port, "snmp_admin_status", ""))


def is_link_up_text(value: Any) -> bool:
    return norm(value) in UP_LINK_STATES


def is_not_present_text(value: Any) -> bool:
    return norm(value) in NOT_PRESENT_STATES


def is_link_down_or_unused_text(value: Any) -> bool:
    text = norm(value)
    return text in DOWN_LINK_STATES or text in ADMIN_DOWN_STATES or text in NOT_PRESENT_STATES


def is_admin_down_port(port: Any) -> bool:
    if not port:
        return False
    if norm(getattr(port, "status", "")) in {"disabled"}:
        return True
    admin = port_admin_text(port)
    return admin in ADMIN_DOWN_STATES or admin in {"2"}


def is_port_link_up(port: Any) -> bool:
    if not port:
        return False
    return is_link_up_text(getattr(port, "status", "")) or is_link_up_text(getattr(port, "snmp_oper_status", ""))


def is_port_link_down(port: Any) -> bool:
    if not port:
        return False
    status = norm(getattr(port, "status", ""))
    oper = port_oper_text(port)
    return status in {"down", "error"} or oper in DOWN_LINK_STATES or oper in NOT_PRESENT_STATES


def port_text_evidence(port: Any) -> str:
    fields = [
        getattr(port, "description", ""),
        getattr(port, "snmp_alias", ""),
        getattr(port, "connected_device", ""),
        getattr(port, "owner", ""),
        getattr(port, "cable_label", ""),
        getattr(port, "patch_panel", ""),
        getattr(port, "patch_panel_port", ""),
        getattr(port, "notes", ""),
    ]
    return " ".join(compact(v) for v in fields if is_meaningful_text(v))


def has_stale_or_decommissioned_text(port: Any) -> bool:
    text = compact_lower(port_text_evidence(port))
    return bool(text and any(token in text for token in STALE_OR_DECOMMISSIONED_KEYWORDS))


def has_explicit_alarm_monitor_tag(port: Any) -> bool:
    if not port or has_stale_or_decommissioned_text(port):
        return False
    fields = [
        getattr(port, "notes", ""),
        getattr(port, "description", ""),
        getattr(port, "connected_device", ""),
        getattr(port, "cable_label", ""),
    ]
    text = compact_lower(" ".join(str(v or "") for v in fields))
    return bool(text and any(tag in text for tag in STRICT_ALARM_MONITOR_TAGS))


def has_explicit_monitoring_tag(port: Any) -> bool:
    return has_explicit_alarm_monitor_tag(port)


def has_actionable_text_evidence(port: Any) -> bool:
    text = compact_lower(port_text_evidence(port))
    if not text or has_stale_or_decommissioned_text(port):
        return False
    return any(token in text for token in ACTIONABLE_KEYWORDS)


def has_confirmed_neighbor(port: Any) -> bool:
    if not port:
        return False
    # Remote port text alone is not evidence; stale parsers often store '-' or 'Neighbor'.
    if is_meaningful_text(getattr(port, "neighbor_device", "")):
        return True
    if getattr(port, "neighbor_ip", None):
        return True
    return False


def has_real_identity_evidence(port: Any) -> bool:
    if not port:
        return False
    if has_confirmed_neighbor(port):
        return True
    if is_meaningful_text(getattr(port, "connected_device", "")):
        return True
    if getattr(port, "ip_address", None):
        return True
    if is_meaningful_text(getattr(port, "mac_address", "")):
        return True
    return False


def is_explicitly_critical_port(port: Any) -> bool:
    return has_explicit_alarm_monitor_tag(port)


def is_actionable_interface_down(port: Any) -> bool:
    if not port:
        return False
    if not has_explicit_alarm_monitor_tag(port):
        return False
    if is_admin_down_port(port):
        return False
    if is_port_link_up(port):
        return False
    if not is_port_link_down(port):
        return False
    return True


def sfp_power_evaluation_allowed(values: Dict[str, Any]) -> bool:
    return norm(values.get("link_status")) in UP_LINK_STATES


def sfp_counter_evaluation_allowed(values: Dict[str, Any]) -> bool:
    # Counter alarms require a live link. Unknown/down/module-only counters are kept as history only.
    return norm(values.get("link_status")) in UP_LINK_STATES


def decimal_outside(value: Any, minimum: Decimal, maximum: Decimal) -> bool:
    decimal_value = to_decimal(value)
    if decimal_value is None:
        return False
    return decimal_value < minimum or decimal_value > maximum


def threshold_pair_is_real(minimum: Any, maximum: Any) -> bool:
    lo = to_decimal(minimum)
    hi = to_decimal(maximum)
    return lo is not None and hi is not None and lo < hi


def physical_error_delta(values: Dict[str, Any]) -> int:
    return (
        to_int(values.get("align_delta"))
        + to_int(values.get("fcs_delta"))
        + to_int(values.get("input_error_delta"))
        + to_int(values.get("output_error_delta"))
        + to_int(values.get("rcv_delta"))
        + to_int(values.get("xmit_delta"))
    )


def is_probable_sfp_port(port: Any) -> bool:
    """Return True only when the port is likely an optical/SFP uplink.

    This intentionally excludes ordinary access copper ports so Cisco CRC alarms do
    not become noisy. Explicit fiber/SFP text is accepted for 1G SFP ports.
    """
    if not port:
        return False
    iface = compact_lower(getattr(port, "interface_name", "") or getattr(port, "snmp_raw_name", ""))
    switch = getattr(port, "switch", None)
    switch_text = compact_lower(" ".join([
        getattr(switch, "vendor", "") if switch else "",
        getattr(switch, "device_family", "") if switch else "",
        getattr(switch, "model", "") if switch else "",
        getattr(switch, "name", "") if switch else "",
    ]))
    port_text = compact_lower(" ".join([
        getattr(port, "interface_name", ""),
        getattr(port, "snmp_raw_name", ""),
        getattr(port, "cable_type", ""),
        getattr(port, "description", ""),
        getattr(port, "notes", ""),
    ]))

    if re.match(r"^(te|tengigabitethernet|fo|fortygigabitethernet|hu|hundredgig|twe|twentyfivegig)", iface):
        return True
    if iface.startswith("ethernet") and "nexus" in switch_text:
        return True
    if any(token in port_text for token in ("sfp", "fiber", "fibre", "optic", "transceiver", "uplink fiber")):
        return True
    return False


def cisco_crc_alarm_is_actionable(
    port: Any,
    deltas: Dict[str, Any],
    *,
    fresh_link_up: Optional[bool] = None,
    fresh_sfp_target: Optional[bool] = None,
    require_port: bool = True,
) -> Tuple[bool, str]:
    """Return whether Cisco CRC/Input/Output deltas should become an alarm.

    The SSH background monitor has fresh link/media evidence. When fresh_* is
    provided, stale DB Port status must not suppress a real current SFP/fiber
    physical error. Generic cleanup calls keep conservative DB-based defaults.
    """
    if not port and require_port:
        return False, "no_port_mapping"

    if fresh_sfp_target is None:
        if not is_probable_sfp_port(port):
            return False, "not_sfp_port"
    elif not fresh_sfp_target:
        return False, "not_sfp_port"

    if fresh_link_up is None:
        if not is_port_link_up(port):
            return False, "port_not_up"
    elif not fresh_link_up:
        return False, "port_not_up"

    physical = physical_error_delta(deltas)
    if physical < CRC_DELTA_WARNING:
        return False, "physical_delta_below_threshold"
    return True, "sfp_physical_error_delta"

def sfp_issue_labels_from_values(values: Dict[str, Any]) -> List[str]:
    labels: List[str] = []

    if values.get("err_disabled"):
        labels.append("Err-disabled")

    if sfp_counter_evaluation_allowed(values):
        if to_int(values.get("fcs_delta")) >= CRC_DELTA_WARNING or to_int(values.get("align_delta")) >= CRC_DELTA_WARNING:
            labels.append("CRC Increased")
        if to_int(values.get("input_error_delta")) >= INPUT_OUTPUT_DELTA_WARNING or to_int(values.get("rcv_delta")) >= INPUT_OUTPUT_DELTA_WARNING:
            labels.append("Input Error")
        if to_int(values.get("output_error_delta")) >= INPUT_OUTPUT_DELTA_WARNING or to_int(values.get("xmit_delta")) >= INPUT_OUTPUT_DELTA_WARNING:
            labels.append("Output Error")
        # outDiscards alone is congestion/queueing context, not CRC/physical alarm.

    if sfp_power_evaluation_allowed(values):
        rx_min = values.get("rx_min_dbm")
        rx_max = values.get("rx_max_dbm")
        tx_min = values.get("tx_min_dbm")
        tx_max = values.get("tx_max_dbm")
        if threshold_pair_is_real(rx_min, rx_max) and decimal_outside(values.get("rx_power_dbm"), to_decimal(rx_min), to_decimal(rx_max)):
            labels.append("Rx Power abnormal")
        if threshold_pair_is_real(tx_min, tx_max) and decimal_outside(values.get("tx_power_dbm"), to_decimal(tx_min), to_decimal(tx_max)):
            labels.append("Tx Power abnormal")

    if decimal_outside(values.get("temperature_c"), SFP_TEMP_MIN_SANITY_C, SFP_TEMP_MAX_SANITY_C):
        labels.append("Temperature abnormal")

    return labels


def _deltas_from_alarm_details(details: Any) -> Dict[str, int]:
    text = str(details or "")
    aliases = {
        "align": "align_delta",
        "fcs": "fcs_delta",
        "input": "input_error_delta",
        "output": "output_error_delta",
        "rcv": "rcv_delta",
        "xmit": "xmit_delta",
        "outdiscard": "out_discard_delta",
    }
    result: Dict[str, int] = {}
    for raw_key, value in re.findall(r"([A-Za-z]+)Δ\s*=\s*(-?\d+)", text):
        key = aliases.get(raw_key.lower())
        if key:
            result[key] = to_int(value)
    return result


def _latest_sfp_snapshot_for_port(port: Any):
    if not port:
        return None
    try:
        from .models import SfpMonitorSnapshot
        return SfpMonitorSnapshot.objects.filter(
            switch_id=getattr(port, "switch_id", None),
            interface_name=getattr(port, "interface_name", ""),
        ).order_by("-poll_time", "-id").first()
    except Exception:
        return None


def port_has_explicit_fault_evidence(port: Any, alarm: Any = None) -> bool:
    fields = []
    if port:
        fields.extend([
            getattr(port, "status", ""),
            getattr(port, "snmp_admin_status", ""),
            getattr(port, "snmp_oper_status", ""),
            getattr(port, "description", ""),
            getattr(port, "snmp_alias", ""),
            getattr(port, "notes", ""),
        ])
    if alarm:
        fields.extend([
            getattr(alarm, "title", ""),
            getattr(alarm, "message", ""),
            getattr(alarm, "details", ""),
            getattr(alarm, "source", ""),
        ])
    text = compact_lower(" ".join(str(v or "") for v in fields))
    if any(token in text for token in PORT_ERROR_FAULT_TOKENS):
        return True
    snap = _latest_sfp_snapshot_for_port(port)
    if snap and bool(getattr(snap, "err_disabled", False)):
        return True
    return False


def _phase83r5_text(*values):
    return " ".join(str(v or "") for v in values).strip().lower()


def _phase83r5_port_text(port):
    if not port:
        return ""
    return _phase83r5_text(
        getattr(port, "interface_name", ""),
        getattr(port, "status", ""),
        getattr(port, "snmp_admin_status", ""),
        getattr(port, "snmp_oper_status", ""),
        getattr(port, "description", ""),
        getattr(port, "snmp_alias", ""),
        getattr(port, "connected_device", ""),
        getattr(port, "neighbor_device", ""),
        getattr(port, "neighbor_port", ""),
        getattr(port, "notes", ""),
    )


def _phase83r5_alarm_text(alarm):
    return _phase83r5_text(
        getattr(alarm, "title", ""),
        getattr(alarm, "message", ""),
        getattr(alarm, "details", ""),
        getattr(alarm, "source", ""),
        _phase83r5_port_text(getattr(alarm, "port", None)),
    )


def _phase83r5_has_latest_err_disabled(port):
    if not port:
        return False
    try:
        from .models import SfpMonitorSnapshot
        snap = SfpMonitorSnapshot.objects.filter(
            switch_id=getattr(port, "switch_id", None),
            interface_name=getattr(port, "interface_name", ""),
        ).order_by("-poll_time", "-id").first()
        return bool(snap and getattr(snap, "err_disabled", False))
    except Exception:
        return False


def is_actionable_port_error(port, alarm=None):
    text = _phase83r5_alarm_text(alarm) if alarm is not None else _phase83r5_port_text(port)
    if _PHASE83R5_AUTO_VISUAL in text:
        return False
    if any(token in text for token in _PHASE83R5_FAULT_TOKENS):
        return True
    if _phase83r5_has_latest_err_disabled(port):
        return True
    return False


def alarm_is_false_positive(alarm: Any) -> Tuple[bool, str]:
    title = compact(getattr(alarm, "title", ""))
    title_lower = compact_lower(getattr(alarm, "title", ""))
    message_lower = compact_lower(getattr(alarm, "message", ""))
    fp = compact(getattr(alarm, "fingerprint", ""))
    fp_lower = compact_lower(getattr(alarm, "fingerprint", ""))
    port = getattr(alarm, "port", None)
    category = norm(getattr(alarm, "category", ""))
    text = _phase83r5_alarm_text(alarm)

    # Phase83R5: generic Port.Status.ERROR and auto-visual placeholders are noise unless explicit fault evidence exists.
    if title_lower == "port error" or fp_lower.startswith("port-error:"):
        if not is_actionable_port_error(port, alarm):
            return True, "phase83r5_port_error_without_explicit_fault_evidence"

    if _PHASE83R5_AUTO_VISUAL in text:
        return True, "phase83r5_auto_visual_placeholder_not_alarm"

    # Phase83R2: topology/uplink-down requires an explicit alarm-monitor tag.
    if fp_lower.startswith("uplink-down:") or category == "topology" and (
        "uplink" in title_lower or "neighbor down" in title_lower or " is down" in message_lower or " is down" in title_lower
    ):
        if not is_actionable_interface_down(port):
            return True, "topology_down_requires_explicit_alarm_monitor_tag"

    # Base Phase83R policy: retain original title-only Uplink/Neighbor behavior when category is not topology.
    if title == "Uplink / Neighbor Down":
        if not is_actionable_interface_down(port):
            return True, "not_actionable_interface_down"

    if fp.startswith("cisco-crc:") or title == "Cisco CRC/Input/Output Error Increased":
        deltas = _deltas_from_alarm_details(getattr(alarm, "details", "") or getattr(alarm, "message", ""))
        actionable, reason = cisco_crc_alarm_is_actionable(port, deltas)
        if not actionable:
            return True, f"cisco_crc_{reason}"

    if category == "sfp" and title in OPTICAL_POWER_TITLES:
        try:
            from .models import SfpMonitorSnapshot
            switch_id = getattr(alarm, "switch_id", None)
            iface = getattr(port, "interface_name", "") if port else ""
            snap = None
            if switch_id and iface:
                snap = SfpMonitorSnapshot.objects.filter(switch_id=switch_id, interface_name=iface).order_by("-poll_time", "-id").first()
            if not snap or not sfp_power_evaluation_allowed({"link_status": getattr(snap, "link_status", "")}):
                return True, "sfp_power_without_link_up"
        except Exception:
            pass

    if category == "sfp" and title in SFP_COUNTER_TITLES:
        try:
            from .models import SfpMonitorSnapshot
            switch_id = getattr(alarm, "switch_id", None)
            iface = getattr(port, "interface_name", "") if port else ""
            snap = None
            if switch_id and iface:
                snap = SfpMonitorSnapshot.objects.filter(switch_id=switch_id, interface_name=iface).order_by("-poll_time", "-id").first()
            if not snap or not sfp_counter_evaluation_allowed({"link_status": getattr(snap, "link_status", "")}):
                return True, "sfp_counter_without_link_up"
            values = {
                "link_status": getattr(snap, "link_status", ""),
                "align_delta": getattr(snap, "align_delta", 0),
                "fcs_delta": getattr(snap, "fcs_delta", 0),
                "input_error_delta": getattr(snap, "input_error_delta", 0),
                "output_error_delta": getattr(snap, "output_error_delta", 0),
                "rcv_delta": getattr(snap, "rcv_delta", 0),
                "xmit_delta": getattr(snap, "xmit_delta", 0),
            }
            if physical_error_delta(values) < CRC_DELTA_WARNING:
                return True, "sfp_counter_delta_below_threshold"
        except Exception:
            pass

    if category == "sfp" and title == "Temperature abnormal":
        try:
            from .models import SfpMonitorSnapshot
            switch_id = getattr(alarm, "switch_id", None)
            iface = getattr(port, "interface_name", "") if port else ""
            snap = None
            if switch_id and iface:
                snap = SfpMonitorSnapshot.objects.filter(switch_id=switch_id, interface_name=iface).order_by("-poll_time", "-id").first()
            temp = to_decimal(getattr(snap, "temperature_c", None) if snap else None)
            if temp is not None and SFP_TEMP_MIN_SANITY_C <= temp <= SFP_TEMP_MAX_SANITY_C:
                return True, "generic_temperature_threshold_false_positive"
        except Exception:
            pass

    return False, ""
