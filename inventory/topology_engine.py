from __future__ import annotations

# PHASE81_83_TOPOLOGY_DRILLDOWN_ENGINE

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.urls import reverse
from django.utils import timezone

from .models import AlarmNotification, Port, PortConnectionHistory, SfpMonitorSnapshot, Switch
from .snmp_tools import is_visible_switchmap_interface
from .alarm_policy import is_actionable_interface_down, norm

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_PARTIAL = "partial"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_STALE = "stale"
CONFIDENCE_UNKNOWN = "unknown"

STALE_HOURS = 48


def normalize_interface(value: Any) -> str:
    value = str(value or "").strip()
    replacements = [
        (r"^TenGigabitEthernet", "Te"),
        (r"^GigabitEthernet", "Gi"),
        (r"^FastEthernet", "Fa"),
        (r"^FortyGigabitEthernet", "Fo"),
        (r"^TwentyFiveGigE", "Twe"),
        (r"^TwoGigabitEthernet", "Tw"),
        (r"^Ethernet", "Eth"),
    ]
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", value)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def status_is_parent_down(switch: Optional[Switch]) -> bool:
    if not switch:
        return False
    return bool(getattr(switch, "snmp_enabled", False) and clean_text(getattr(switch, "snmp_last_error", "")))


def port_state(port: Optional[Port]) -> Tuple[str, str]:
    if not port:
        return "unknown", "Unknown"
    admin = norm(getattr(port, "snmp_admin_status", ""))
    oper = norm(getattr(port, "snmp_oper_status", ""))
    status = norm(getattr(port, "status", ""))
    text = " ".join([
        status,
        admin,
        oper,
        norm(getattr(port, "description", "")),
        norm(getattr(port, "snmp_alias", "")),
    ])
    if admin in {"2", "down", "disabled", "admin down", "administratively down", "shutdown"} or status == "disabled":
        return "admin_down", "Admin Down"
    if "err" in text or "fault" in text or status == "error":
        return "error", "Error"
    if status == "up" or oper in {"1", "up", "connected", "operational"}:
        return "up", "Up"
    if oper in {"notpresent", "not present", "sfpabsent", "xcvrabsent"}:
        return "not_present", "Not Present"
    if status == "down" or oper in {"2", "down", "notconnect", "not connected", "lowerlayerdown", "lower layer down"}:
        return "down", "Down"
    return "unknown", "Unknown"


def _latest_port_history(port: Optional[Port]):
    if not port:
        return None
    try:
        return PortConnectionHistory.objects.filter(port=port).order_by("-observed_at", "-id").first()
    except Exception:
        return None


def _latest_sfp(port: Optional[Port]):
    if not port:
        return None
    try:
        return SfpMonitorSnapshot.objects.filter(switch_id=port.switch_id, interface_name=port.interface_name).order_by("-poll_time", "-id").first()
    except Exception:
        return None


def _age_is_stale(dt: Any, hours: int = STALE_HOURS) -> bool:
    if not dt:
        return False
    try:
        return (timezone.now() - dt).total_seconds() > hours * 3600
    except Exception:
        return False


def evidence_for_port(port: Optional[Port]) -> List[Dict[str, str]]:
    if not port:
        return []
    items: List[Dict[str, str]] = []
    if clean_text(getattr(port, "neighbor_device", "")):
        source = clean_text(getattr(port, "neighbor_source", "")) or "Discovery"
        items.append({"source": source, "value": clean_text(f"{port.neighbor_device} {port.neighbor_port or ''}")})
    if clean_text(getattr(port, "connected_device", "")):
        items.append({"source": "Manual/Asset", "value": clean_text(getattr(port, "connected_device", ""))})
    if clean_text(getattr(port, "ip_address", "")):
        items.append({"source": "ARP/IP", "value": clean_text(getattr(port, "ip_address", ""))})
    if clean_text(getattr(port, "mac_address", "")):
        items.append({"source": "MAC", "value": clean_text(getattr(port, "mac_address", ""))})
    if int(getattr(port, "mac_count", 0) or 0) > 0:
        items.append({"source": "MAC Table", "value": f"{int(getattr(port, 'mac_count', 0) or 0)} learned MAC"})
    if clean_text(getattr(port, "description", "")):
        items.append({"source": "Description", "value": clean_text(getattr(port, "description", ""))})
    if clean_text(getattr(port, "snmp_alias", "")) and clean_text(getattr(port, "snmp_alias", "")) != clean_text(getattr(port, "description", "")):
        items.append({"source": "SNMP Alias", "value": clean_text(getattr(port, "snmp_alias", ""))})
    hist = _latest_port_history(port)
    if hist:
        value_parts = [clean_text(getattr(hist, "connected_device", "")), clean_text(getattr(hist, "neighbor_device", "")), clean_text(getattr(hist, "ip_address", "")), clean_text(getattr(hist, "mac_address", ""))]
        value = " ".join([v for v in value_parts if v])
        if value:
            items.append({"source": "Port History", "value": value})
    return items


def _discovery_source_rank(source: str) -> int:
    source = norm(source)
    if source in {"cdp", "lldp", "mndp"}:
        return 3
    if source:
        return 2
    return 0


def classify_edge(source_port: Port, matched_switch: Optional[Switch], matched_port: Optional[Port], matched_by: str = "") -> Dict[str, Any]:
    source_state, source_label = port_state(source_port)
    target_state, target_label = port_state(matched_port)
    parent_down = status_is_parent_down(getattr(source_port, "switch", None)) or status_is_parent_down(matched_switch)
    source_evidence = evidence_for_port(source_port)
    target_evidence = evidence_for_port(matched_port)
    evidence = source_evidence + target_evidence

    source_name = norm(getattr(source_port, "neighbor_source", ""))
    discovery_rank = _discovery_source_rank(source_name)

    if parent_down:
        confidence = CONFIDENCE_STALE
        health = "suppressed"
        health_label = "Suppressed by parent SNMP timeout"
        severity = "info"
        reason = "Parent device has SNMP timeout; child topology warnings are suppressed."
    elif matched_switch and matched_port:
        confidence = CONFIDENCE_CONFIRMED
        if source_state in {"error"} or target_state in {"error"}:
            health, severity, reason = "down", "critical", "Confirmed link has interface error."
            health_label = "Confirmed / Error"
        elif source_state == "up" and target_state == "up":
            health, severity, reason = "up", "ok", "Both sides are up."
            health_label = "Confirmed / Up"
        elif is_actionable_interface_down(source_port) or is_actionable_interface_down(matched_port):
            health, severity, reason = "down", "warning", "Confirmed link is down on an actionable documented/neighbor port."
            health_label = "Confirmed / Down"
        else:
            health, severity, reason = "partial", "info", "Confirmed edge exists, but down state is not actionable."
            health_label = "Confirmed / Non-actionable Down"
    elif matched_switch:
        confidence = CONFIDENCE_PARTIAL
        if is_actionable_interface_down(source_port):
            health, severity, reason = "partial", "warning", "One side maps to a known device; remote port is not confirmed."
            health_label = "Partial / One-way"
        else:
            health, severity, reason = "partial", "info", "One-way or incomplete neighbor data; not critical."
            health_label = "Partial / Unknown"
    elif discovery_rank:
        confidence = CONFIDENCE_PARTIAL
        health, severity = "partial", "info"
        health_label = "External / Partial"
        reason = "Discovery reported a neighbor, but it is not matched to a managed device."
    elif evidence:
        confidence = CONFIDENCE_INFERRED
        health, severity = "inferred", "info"
        health_label = "Inferred"
        reason = "Edge inferred from MAC/IP/asset/history evidence."
    else:
        confidence = CONFIDENCE_UNKNOWN
        health, severity = "unknown", "info"
        health_label = "No Evidence"
        reason = "No topology evidence."

    last_seen_candidates = [getattr(source_port, "discovery_last_poll", None), getattr(source_port, "snmp_last_poll", None), getattr(source_port, "updated_at", None)]
    if matched_port:
        last_seen_candidates += [getattr(matched_port, "discovery_last_poll", None), getattr(matched_port, "snmp_last_poll", None), getattr(matched_port, "updated_at", None)]
    hist = _latest_port_history(source_port)
    if hist:
        last_seen_candidates.append(getattr(hist, "last_verified_at", None) or getattr(hist, "observed_at", None))
    last_seen = max([dt for dt in last_seen_candidates if dt], default=None)
    first_seen = getattr(hist, "observed_at", None) if hist else None
    if _age_is_stale(last_seen) and confidence in {CONFIDENCE_CONFIRMED, CONFIDENCE_PARTIAL}:
        confidence = CONFIDENCE_STALE
        if health == "up":
            health = "stale"
            severity = "warning"
            health_label = "Stale"
            reason = "Topology evidence is stale."

    edge_id = f"edge-{source_port.id}"
    return {
        "edge_id": edge_id,
        "confidence": confidence,
        "health": health,
        "health_label": health_label,
        "severity": severity,
        "reason": reason,
        "source_state": source_state,
        "source_state_label": source_label,
        "target_state": target_state,
        "target_state_label": target_label,
        "evidence": evidence,
        "evidence_count": len(evidence),
        "parent_down": parent_down,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "matched_by": matched_by or "-",
        "detail_url": reverse("inventory:topology_edge_detail", args=[source_port.id]),
        "source_url": reverse("inventory:switch_detail", args=[source_port.switch_id]) + f"?port={source_port.id}",
    }


def edge_warning_allowed(edge: Dict[str, Any]) -> bool:
    if edge.get("parent_down"):
        return False
    return edge.get("severity") in {"warning", "critical"} and edge.get("confidence") in {CONFIDENCE_CONFIRMED, CONFIDENCE_PARTIAL, CONFIDENCE_STALE}


def topology_alarm_should_exist(port: Optional[Port]) -> bool:
    if not port:
        return False
    if status_is_parent_down(getattr(port, "switch", None)):
        return False
    return is_actionable_interface_down(port)


def build_alarm_evidence(alarm: AlarmNotification) -> Dict[str, Any]:
    port = getattr(alarm, "port", None)
    switch = getattr(alarm, "switch", None)
    latest_sfp = _latest_sfp(port) if port else None
    evidence: List[Dict[str, str]] = []
    if clean_text(getattr(alarm, "details", "")):
        evidence.append({"source": "Alarm Details", "value": clean_text(alarm.details)})
    if clean_text(getattr(alarm, "message", "")):
        evidence.append({"source": "Alarm Message", "value": clean_text(alarm.message)})
    if port:
        evidence += evidence_for_port(port)
        p_state, p_state_label = port_state(port)
    else:
        p_state = p_state_label = "-"
    if latest_sfp:
        evidence.append({"source": "SFP Latest Poll", "value": clean_text(f"status={latest_sfp.link_status or '-'} rx={latest_sfp.rx_power_dbm or '-'} tx={latest_sfp.tx_power_dbm or '-'} temp={latest_sfp.temperature_c or '-'} health={latest_sfp.health_state}")})
    return {
        "alarm": alarm,
        "switch": switch,
        "port": port,
        "port_state": p_state,
        "port_state_label": p_state_label,
        "latest_sfp": latest_sfp,
        "evidence": evidence,
        "device_url": reverse("inventory:switch_detail", args=[switch.id]) if switch else "",
        "port_url": reverse("inventory:switch_detail", args=[switch.id]) + f"?port={port.id}" if switch and port else "",
        "topology_url": reverse("inventory:topology_edge_detail", args=[port.id]) if port and alarm.category == AlarmNotification.Category.TOPOLOGY else "",
        "sfp_url": reverse("inventory:sfp_monitor") + (f"?switch={switch.id}&port={port.interface_name}" if switch and port else ""),
    }
