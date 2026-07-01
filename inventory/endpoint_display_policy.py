"""Display-only classification for the port modal's connected-device card.

This module does not poll, mutate models, or write history.  It converts the
evidence already stored on a Port (or PortConnectionHistory) into a truthful
display classification.  Raw LLDP/CDP evidence remains available separately.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict


TRUSTED_NEIGHBOR_SOURCES = {"CDP", "LLDP", "MNDP"}
EXACT_GATEWAY_IPS = {"172.16.25.1"}
LINK_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(trunk|uplink|downlink|port[ -]?channel|etherchannel|"
    r"core|fiber|sfp|qsfp)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)
AP_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(access[ -]?point|wireless|wifi|wlan|cap)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "-" or text.lower() in {"none", "null", "unknown", "undefined"}:
        return ""
    return text


def _first_mac(value: Any) -> str:
    for part in re.split(r"[\s,;]+", _clean(value)):
        part = _clean(part)
        if part:
            return part
    return ""


def _mac_count(evidence: Any) -> int:
    try:
        stored = int(getattr(evidence, "mac_count", 0) or 0)
    except (TypeError, ValueError):
        stored = 0
    learned = [part for part in re.split(r"[\s,;]+", _clean(getattr(evidence, "mac_addresses", ""))) if _clean(part)]
    return max(stored, len(learned))


def _neighbor_label(evidence: Any) -> str:
    return " / ".join(filter(None, [
        _clean(getattr(evidence, "neighbor_device", "")),
        _clean(getattr(evidence, "neighbor_port", "")),
    ]))


def _switch_context(evidence: Any) -> str:
    switch = getattr(evidence, "switch", None)
    return " ".join(filter(None, [
        _clean(getattr(switch, "name", "")),
        _clean(getattr(switch, "model", "")),
        _clean(getattr(switch, "device_family", "")),
        _clean(getattr(switch, "device_role", "")),
    ])).lower()


def _local_ap_context(evidence: Any) -> bool:
    switch = getattr(evidence, "switch", None)
    role = _clean(getattr(switch, "device_role", "")).lower()
    family = _clean(getattr(switch, "device_family", "")).lower()
    if role == "access_point" or family in {"mikrotik_ap", "access_point"}:
        return True
    port_text = " ".join(filter(None, [
        _clean(getattr(evidence, "device_type", "")),
        _clean(getattr(evidence, "connected_device", "")),
        _clean(getattr(evidence, "description", "")),
        _clean(getattr(evidence, "snmp_alias", "")),
    ]))
    return bool(AP_PATTERN.search(port_text))


def _link_context(evidence: Any) -> bool:
    mode = _clean(getattr(evidence, "port_mode", "")).lower()
    device_type = _clean(getattr(evidence, "device_type", "")).lower()
    if mode == "trunk" or device_type in {"uplink", "switch"}:
        return True
    port_text = " ".join(filter(None, [
        _clean(getattr(evidence, "interface_name", "")),
        _clean(getattr(evidence, "description", "")),
        _clean(getattr(evidence, "snmp_alias", "")),
        _clean(getattr(evidence, "connected_device", "")),
    ]))
    return bool(LINK_PATTERN.search(port_text))


def _is_dot_one(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.version == 4 and str(ip).split(".")[-1] == "1"


def classify_port_connection_display(evidence: Any) -> Dict[str, Any]:
    """Return final display fields plus raw evidence for audit/verification."""
    count = _mac_count(evidence)
    connected = _clean(getattr(evidence, "connected_device", ""))
    neighbor = _neighbor_label(evidence)
    neighbor_source = _clean(getattr(evidence, "neighbor_source", "")).upper()
    port_ip = _clean(getattr(evidence, "ip_address", ""))
    neighbor_ip = _clean(getattr(evidence, "neighbor_ip", ""))
    raw_ip = port_ip or neighbor_ip
    raw_mac = _clean(getattr(evidence, "mac_address", "")) or _first_mac(getattr(evidence, "mac_addresses", ""))
    vlan = _clean(
        getattr(evidence, "access_vlan", None)
        or getattr(evidence, "vlan", None)
        or getattr(evidence, "native_vlan", None)
    )
    trusted_neighbor = bool(neighbor and neighbor_source in TRUSTED_NEIGHBOR_SOURCES)
    exact_gateway = raw_ip in EXACT_GATEWAY_IPS
    gateway_like = exact_gateway or (count > 1 and _is_dot_one(raw_ip))
    ap_context = _local_ap_context(evidence)
    link_context = _link_context(evidence)

    classification = "no_current_evidence"
    label = ""
    source = ""
    display_ip = ""
    display_mac = ""
    direct = False
    confidence = 0
    reason = "No endpoint, neighbor, MAC, IP, or aggregate evidence is available."

    if ap_context and count > 1:
        classification = "behind_ap"
        label = f"Behind AP / Multi-MAC ({count})"
        source = "AP context / FDB-ARP aggregate"
        confidence = 98
        reason = "The local device is an access point and multiple MAC addresses are learned behind this port."
    elif gateway_like:
        classification = "gateway_arp_observed"
        label = "Gateway ARP observed / Behind network"
        source = "ARP gateway observation"
        confidence = 98 if exact_gateway else 95
        reason = "A gateway-like address cannot identify a direct endpoint on this evidence."
    elif trusted_neighbor and count <= 2:
        classification = "physical_neighbor"
        label = neighbor
        source = neighbor_source
        display_ip = neighbor_ip or port_ip
        direct = True
        confidence = 98
        reason = "Trusted physical-neighbor evidence is limited to at most two learned MAC addresses."
    elif trusted_neighbor and count > 2:
        classification = "physical_neighbor_conflict"
        label = f"Network neighbor evidence / Aggregate behind link ({count} MACs)"
        source = f"{neighbor_source} / aggregate conflict"
        confidence = 98
        reason = "A trusted neighbor exists, but the high MAC count proves aggregate devices are also behind the link."
    elif link_context and count > 1:
        classification = "behind_trunk"
        label = f"Behind trunk/uplink ({count} MACs)"
        source = "Link context / FDB-ARP aggregate"
        confidence = 96
        reason = "Trunk/uplink/downlink evidence and multiple learned MAC addresses indicate an aggregate link."
    elif count > 1:
        classification = "multi_mac_aggregate"
        label = f"Aggregate / Multi-MAC ({count})"
        source = "FDB/ARP aggregate"
        confidence = 95
        reason = "Multiple learned MAC addresses cannot be represented as one directly connected device."
    elif trusted_neighbor:
        classification = "physical_neighbor"
        label = neighbor
        source = neighbor_source
        display_ip = neighbor_ip or port_ip
        direct = True
        confidence = 96
        reason = "Trusted LLDP/CDP/MNDP physical-neighbor evidence is present."
    elif connected or raw_mac or raw_ip:
        classification = "direct_endpoint"
        label = connected or raw_mac or raw_ip
        source = "current-db / direct evidence"
        display_ip = raw_ip
        display_mac = raw_mac
        direct = True
        confidence = 92 if count == 1 else 85
        reason = "Single-endpoint evidence is present without gateway, AP, trunk, or aggregate conflict."

    available = bool(label)
    return {
        "available": available,
        "classification": classification,
        "display_label": label,
        "display_source": source,
        "display_ip": display_ip,
        "display_mac": display_mac,
        "display_vlan": vlan,
        "direct": direct,
        "confidence": confidence,
        "reason": reason,
        "raw_evidence": {
            "connected_device": connected,
            "neighbor": neighbor,
            "neighbor_source": neighbor_source,
            "port_ip": port_ip,
            "neighbor_ip": neighbor_ip,
            "mac": raw_mac,
            "mac_count": count,
            "vlan": vlan,
            "local_ap_context": ap_context,
            "link_context": link_context,
            "switch_context": _switch_context(evidence),
        },
    }
