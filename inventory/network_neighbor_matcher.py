"""SwitchMap Phase109R17.1 safe neighbor classification helper.

This module preserves the existing Phase109R15 matching behavior and adds only
exact R17/R17.1 contextual classifications for known remaining neighbors.
No UI, Search, Static, Poller, Discovery, database, or service behavior is
changed by this helper alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple


def text(value: Any) -> str:
    return str(value or "").strip()


def norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", text(value).lower())


def norm_ip(value: Any) -> str:
    value = text(value)
    match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", value)
    return match.group(1) if match else ""


def strip_serial_and_domain(value: Any) -> str:
    raw = text(value)
    raw = re.sub(r"\([^)]*\)", "", raw).strip()
    raw = re.sub(r"\.winac-co\.com\.?$", "", raw, flags=re.I).strip()
    return raw


def canonical_neighbor_key(value: Any) -> str:
    return norm_key(strip_serial_and_domain(value))


def norm_interface(value: Any) -> str:
    v = text(value).lower().strip()
    v = re.sub(r"\([^)]*\)", "", v)
    replacements = [
        (r"^tengigabitethernet", "te"),
        (r"^ten-gigabitethernet", "te"),
        (r"^gigabitethernet", "gi"),
        (r"^fastethernet", "fa"),
        (r"^ethernet", "eth"),
        (r"^ether", "ether"),
        (r"^sfp-sfpplus", "sfp"),
        (r"^sfpplus", "sfp"),
    ]
    for pattern, repl in replacements:
        v = re.sub(pattern, repl, v)
    return re.sub(r"[^a-z0-9]+", "", v)


def is_endpoint_neighbor(name: Any, remote_port: Any = "") -> Tuple[bool, str]:
    raw = text(name)
    key = norm_key(raw)
    rport = text(remote_port).lower()
    if re.match(r"^sep[0-9a-f]{12}$", key, flags=re.I):
        return True, "CISCO_PHONE_ENDPOINT"
    if key.startswith("sep") and len(key) >= 10:
        return True, "CISCO_PHONE_ENDPOINT"
    if key.startswith("polycom") or "polycom" in key or "vvx" in key:
        return True, "POLYCOM_PHONE_ENDPOINT"
    if re.match(r"^w[0-9a-f]{12,}$", key, flags=re.I) or "wan port" in rport:
        return True, "PHONE_OR_WIRELESS_ENDPOINT"
    return False, ""


def is_unmanaged_edge(name: Any) -> Tuple[bool, str]:
    key = norm_key(name)
    if key.startswith("haplite") or key.startswith("hap"):
        return True, "UNMANAGED_MIKROTIK_AP_EDGE"
    if key == "rbaudiencewifi" or key.startswith("rbaudiencewifi"):
        return True, "UNMANAGED_WIFI_EDGE"
    if key == "rb1000" or key.startswith("rb1000"):
        return True, "EXTERNAL_ISP_ROUTER_EDGE"
    return False, ""


def _ip_candidates(*values: Any) -> set:
    return {ip for ip in (norm_ip(v) for v in values) if ip}


def is_r17_client_endpoint(local_switch: Any, local_port: Any, local_ip: Any = "", neighbor_ip: Any = "") -> Tuple[bool, str]:
    """Exact R17 client/DHCP endpoint exception.

    Scope is intentionally narrow: only AliHome ether2 with 192.168.2.250 is
    classified as an endpoint. Both local ip_address and neighbor_ip are checked
    so the result is stable regardless of where the observed IP is stored.
    """
    sw = norm_key(local_switch)
    iface = norm_interface(local_port)
    if sw == "alihome" and iface == "ether2" and "192.168.2.250" in _ip_candidates(local_ip, neighbor_ip):
        return True, "CLIENT_DHCP_ENDPOINT"
    return False, ""


def is_r17_single_mac_access_endpoint(local_switch: Any, local_port: Any, local_ip: Any = "", neighbor_ip: Any = "") -> Tuple[bool, str]:
    """Exact R17.1 single-host access endpoint exception.

    Confirmed live evidence: RB2011-Iranmall ether9 is an access port with one
    MAC address and observed IP 192.168.101.17. It has no CDP/LLDP neighbor
    device/port and no matching managed Switch inventory record, so it is not a
    network neighbor topology error. The rule is intentionally exact to avoid
    hiding real unknown network devices elsewhere.
    """
    sw = norm_key(local_switch)
    iface = norm_interface(local_port)
    if sw == "rb2011iranmall" and iface == "ether9" and "192.168.101.17" in _ip_candidates(local_ip, neighbor_ip):
        return True, "SINGLE_MAC_ACCESS_ENDPOINT"
    return False, ""


def is_r17_unmanaged_ap_endpoint(local_switch: Any, local_port: Any, neighbor_device: Any = "") -> Tuple[bool, str]:
    """Exact R17 unmanaged AP exception.

    This intentionally does not make every RB-CAP-* globally unmanaged. The
    confirmed R17 scope is Salon-Sharghi-PATROL Gi1/0/37 -> RB-CAP-Patrol.
    """
    sw = norm_key(local_switch)
    iface = norm_interface(local_port)
    neighbor = canonical_neighbor_key(neighbor_device)
    if sw == "salonsharghipatrol" and iface == "gi1037":
        if neighbor in {"rbcappatrol", "cappatrol", "rbpatrolcap"}:
            return True, "UNMANAGED_AP_ENDPOINT"
        if neighbor.startswith("rbcap") and "patrol" in neighbor:
            return True, "UNMANAGED_AP_ENDPOINT"
    return False, ""


def is_r17_pending_network_device(
    local_switch: Any,
    local_port: Any,
    neighbor_device: Any = "",
    neighbor_ip: Any = "",
    neighbor_port: Any = "",
) -> Tuple[bool, str]:
    """Exact R17 pending-network-device exceptions.

    These are not endpoints and are not topology errors. They remain visible in
    audit output as pending review/configuration items.
    """
    sw = norm_key(local_switch)
    iface = norm_interface(local_port)
    neighbor = canonical_neighbor_key(neighbor_device)
    n_ip = norm_ip(neighbor_ip)

    if sw == "rb2011iranmall" and iface == "ether1" and neighbor == "7o8iranmalledge" and n_ip == "172.16.1.1":
        return True, "PENDING_REVIEW_NETWORK_DEVICE"

    if sw == "salongharbi" and iface == "te111" and neighbor == "salontolid":
        return True, "PENDING_NETWORK_DEVICE_CONFIG"

    return False, ""


def classify_r17_context(
    local_switch: Any = "",
    local_port: Any = "",
    neighbor_device: Any = "",
    neighbor_ip: Any = "",
    neighbor_port: Any = "",
    local_ip: Any = "",
) -> Tuple[str, str]:
    """Return (classification_kind, classification_code) for exact R17 cases."""
    endpoint, endpoint_type = is_r17_client_endpoint(local_switch, local_port, local_ip, neighbor_ip)
    if endpoint:
        return "endpoint", endpoint_type

    single_mac_endpoint, single_mac_type = is_r17_single_mac_access_endpoint(local_switch, local_port, local_ip, neighbor_ip)
    if single_mac_endpoint:
        return "endpoint", single_mac_type

    pending, pending_type = is_r17_pending_network_device(
        local_switch, local_port, neighbor_device, neighbor_ip, neighbor_port
    )
    if pending:
        return "pending_network_device", pending_type

    ap_endpoint, ap_type = is_r17_unmanaged_ap_endpoint(local_switch, local_port, neighbor_device)
    if ap_endpoint:
        return "unmanaged_edge", ap_type

    unmanaged, unmanaged_type = is_unmanaged_edge(neighbor_device)
    if unmanaged:
        return "unmanaged_edge", unmanaged_type

    return "", ""


@dataclass(frozen=True)
class MatchResult:
    target: Optional[Any]
    method: str
    flags: Tuple[str, ...]
    endpoint_type: str = ""


DEFAULT_ALIAS_PAIRS = {
    "SwitchCore-Factory": "CRS354",
    "RB_Core_Ghazvin": "RB5009",
    "N3K-Core-SW": "NEXUS",
    "N3K-Core-SW.winac-co.com": "NEXUS",
    "N3K-Core-SW.winac-co.com(FOC1916R26A)": "NEXUS",
    "CAP-XL-Managment": "Cap-Managment",
    "CAP-XL-Management": "Cap-Managment",
    "CAP-XL-Tolid": "Cap-Tolid",
    "CAP-XL-EDARI": "Cap-Edari",
    "PPS-(CORE)Tehran-IranMall": "RB2011-Iranmall",

    # Phase109R15 confirmed distribution / edge identity overrides
    "Salon-Sharghi-PATROL.winac-co.com": "Salon-Sharghi-PATROL",
    "Salon-Sharghi-PATROL": "Salon-Sharghi-PATROL",
    "Salon-jonobi.winac-co.com": "Salon-jonobi",
    "Salon-jonobi": "Salon-jonobi",
    "Salon-Edari-Fiber.winac-co.com": "Salon-Edari-Fiber",
    "Salon-Edari-Fiber": "Salon-Edari-Fiber",
    "Salon-Gharbi.winac-co.com": "Salon-Gharbi",
    "Salon-Gharbi": "Salon-Gharbi",
    "Salon-Shomali.winac-co.com": "Salon-Shomali",
    "Salon-Shomali": "Salon-Shomali",
    "RB-Edgge-Factory": "Hex-S",
    "RB-Edge-Factory": "Hex-S",
}


def build_switch_indexes(switches: Iterable[Any], alias_pairs: Optional[Dict[str, str]] = None):
    alias_pairs = dict(DEFAULT_ALIAS_PAIRS if alias_pairs is None else alias_pairs)
    name_map: Dict[str, Any] = {}
    simple_name_map: Dict[str, Any] = {}
    ip_map: Dict[str, Any] = {}
    alias_map: Dict[str, Any] = {}
    aliases_for_target: Dict[int, set] = {}

    for sw in switches:
        sw_name = text(getattr(sw, "name", ""))
        name_map[norm_key(sw_name)] = sw
        simple_name_map[canonical_neighbor_key(sw_name)] = sw
        ip = norm_ip(getattr(sw, "management_ip", ""))
        if ip:
            ip_map[ip] = sw

    for alias, canonical in alias_pairs.items():
        target = name_map.get(norm_key(canonical)) or simple_name_map.get(canonical_neighbor_key(canonical))
        if target:
            alias_map[norm_key(alias)] = target
            alias_map[canonical_neighbor_key(alias)] = target

    for sw in switches:
        aliases_for_target.setdefault(sw.id, set()).add(norm_key(getattr(sw, "name", "")))
        aliases_for_target.setdefault(sw.id, set()).add(canonical_neighbor_key(getattr(sw, "name", "")))
    for alias_key, sw in alias_map.items():
        aliases_for_target.setdefault(sw.id, set()).add(alias_key)

    return {
        "name_map": name_map,
        "simple_name_map": simple_name_map,
        "ip_map": ip_map,
        "alias_map": alias_map,
        "aliases_for_target": aliases_for_target,
    }


def resolve_target(
    neighbor_device: Any,
    neighbor_ip: Any,
    indexes: Dict[str, Dict],
    local_switch: Any = "",
    local_port: Any = "",
    local_ip: Any = "",
    remote_port: Any = "",
) -> MatchResult:
    nd = text(neighbor_device)
    nip = norm_ip(neighbor_ip)
    flags = []

    r17_kind, r17_type = classify_r17_context(local_switch, local_port, nd, nip, remote_port, local_ip)
    if r17_kind == "endpoint":
        return MatchResult(None, "endpoint", (r17_type,), r17_type)
    if r17_kind == "pending_network_device":
        return MatchResult(None, "pending_network_device", (r17_type,), "")
    if r17_kind == "unmanaged_edge":
        return MatchResult(None, "unmanaged_edge", (r17_type,), r17_type)

    endpoint, endpoint_type = is_endpoint_neighbor(nd)
    if endpoint:
        return MatchResult(None, "endpoint", (endpoint_type,), endpoint_type)

    unmanaged, unmanaged_type = is_unmanaged_edge(nd)
    if unmanaged:
        return MatchResult(None, "unmanaged_edge", (unmanaged_type,), unmanaged_type)

    name_key = norm_key(nd)
    simple_key = canonical_neighbor_key(nd)
    ip_target = indexes["ip_map"].get(nip) if nip else None
    name_target = None
    method = ""

    if simple_key in indexes["alias_map"]:
        name_target = indexes["alias_map"][simple_key]
        method = "alias_normalized"
    elif name_key in indexes["alias_map"]:
        name_target = indexes["alias_map"][name_key]
        method = "alias"
    elif simple_key in indexes["simple_name_map"]:
        name_target = indexes["simple_name_map"][simple_key]
        method = "name_normalized"
    elif name_key in indexes["name_map"]:
        name_target = indexes["name_map"][name_key]
        method = "name"
    else:
        for key, sw in indexes["simple_name_map"].items():
            if simple_key and key and (simple_key == key or simple_key.startswith(key) or key.startswith(simple_key)):
                name_target = sw
                method = "name_partial_normalized"
                break

    # Safe special case: Cisco CDP may report N3K SVI/IP as 172.20.1.1 while the managed Nexus record is 172.20.1.12.
    # Only use this when the neighbor name also resolves to NEXUS by alias/name.
    if name_target and text(getattr(name_target, "name", "")).upper() == "NEXUS" and nip == "172.20.1.1":
        flags.append("NEXUS_CDP_MANAGEMENT_IP_ALIAS_172_20_1_1")
        return MatchResult(name_target, method or "nexus_alias", tuple(flags))

    if ip_target and name_target and getattr(ip_target, "id", None) != getattr(name_target, "id", None):
        flags.append("IP_NAME_TARGET_MISMATCH_NAME_PREFERRED")
        return MatchResult(name_target, method or "name_preferred", tuple(flags))
    if ip_target:
        return MatchResult(ip_target, "ip", tuple(flags))
    if name_target:
        return MatchResult(name_target, method, tuple(flags))
    return MatchResult(None, "unresolved", tuple(flags))


def alias_identifies_switch(value: Any, sw: Any, indexes: Dict[str, Dict]) -> bool:
    key = norm_key(value)
    simple = canonical_neighbor_key(value)
    aliases = indexes.get("aliases_for_target", {}).get(getattr(sw, "id", None), set())
    for alias in aliases:
        if not alias:
            continue
        if key == alias or simple == alias or alias in key or key in alias or alias in simple or simple in alias:
            return True
    return False


def reciprocal_match(local_sw: Any, local_port: Any, target_sw: Any, target_ports: Iterable[Any], indexes: Dict[str, Dict]) -> Tuple[bool, str]:
    if not local_sw or not target_sw:
        return False, ""
    local_ip = norm_ip(getattr(local_sw, "management_ip", ""))
    local_port_name = norm_interface(getattr(local_port, "interface_name", ""))
    local_remote_port = norm_interface(getattr(local_port, "neighbor_port", ""))

    for remote in target_ports:
        remote_local_port = norm_interface(getattr(remote, "interface_name", ""))
        remote_neighbor_port = norm_interface(getattr(remote, "neighbor_port", ""))
        remote_neighbor_ip = norm_ip(getattr(remote, "neighbor_ip", ""))
        remote_neighbor_dev = getattr(remote, "neighbor_device", "")

        port_cross_ok = True
        if local_remote_port and remote_local_port and local_remote_port != remote_local_port:
            port_cross_ok = False
        if local_port_name and remote_neighbor_port and local_port_name != remote_neighbor_port:
            # Do not make port mismatch fatal when IP/name identifies peer, because MikroTik bridge/EOIP names differ.
            pass

        if local_ip and remote_neighbor_ip == local_ip:
            return True, "reciprocal_ip"
        if alias_identifies_switch(remote_neighbor_dev, local_sw, indexes):
            if port_cross_ok:
                return True, "reciprocal_alias_port"
            return True, "reciprocal_alias"

    return False, ""
