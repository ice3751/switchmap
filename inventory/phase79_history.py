from __future__ import annotations

import hashlib
import re
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from .models import Port, PortConnectionHistory

IDENTITY_FIELDS = (
    "connected_device",
    "neighbor_source",
    "neighbor_device",
    "neighbor_port",
    "neighbor_ip",
    "ip_address",
    "mac_address",
    "mac_addresses",
    "mac_count",
    "device_type",
    "owner",
)


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()



def _identity_clean(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value in ("", "-", "None", "none", "null", "Null", "NULL"):
        return ""
    if value.lower() in ("unknown", "نامشخص"):
        return ""
    return value


def _first_mac(value):
    value = _identity_clean(value)
    if not value:
        return ""
    for part in re.split(r"[\\s,;]+", value):
        part = _identity_clean(part)
        if part:
            return part
    return ""


def port_has_identity_data(port: Port) -> bool:
    # Phase79.2.5: only real endpoint evidence counts as connected-device history.
    # Poll timestamps, VLAN, status, neighbor_source, mac_count and default device_type=unknown
    # are not enough; they caused fake Last Connected records on empty SFP ports.
    if _identity_clean(getattr(port, "connected_device", "")):
        return True
    if _identity_clean(getattr(port, "neighbor_device", "")) or _identity_clean(getattr(port, "neighbor_port", "")):
        return True
    if _identity_clean(getattr(port, "neighbor_ip", "")) or _identity_clean(getattr(port, "ip_address", "")):
        return True
    if _identity_clean(getattr(port, "mac_address", "")) or _first_mac(getattr(port, "mac_addresses", "")):
        return True
    return False


def port_identity_hash(port: Port) -> str:
    parts = [
        f"connected_device={_identity_clean(getattr(port, 'connected_device', ''))}",
        f"neighbor_device={_identity_clean(getattr(port, 'neighbor_device', ''))}",
        f"neighbor_port={_identity_clean(getattr(port, 'neighbor_port', ''))}",
        f"neighbor_ip={_identity_clean(getattr(port, 'neighbor_ip', ''))}",
        f"ip_address={_identity_clean(getattr(port, 'ip_address', ''))}",
        f"mac_address={_identity_clean(getattr(port, 'mac_address', ''))}",
        f"mac_addresses={_first_mac(getattr(port, 'mac_addresses', ''))}",
        f"vlan={_identity_clean(getattr(port, 'access_vlan', None) or getattr(port, 'vlan', None))}",
        f"mode={_identity_clean(getattr(port, 'port_mode', ''))}",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _history_kwargs(port: Port, *, event_type: str, source: str, observed_at, previous_status: str = "", note: str = "") -> dict:
    return {
        "port": port,
        "switch": port.switch,
        "interface_name": port.interface_name,
        "event_type": event_type,
        "status_before": previous_status or "",
        "status_after": port.status or "",
        "observed_at": observed_at or timezone.now(),
        "last_verified_at": observed_at or timezone.now(),
        "neighbor_source": port.neighbor_source or "",
        "neighbor_device": port.neighbor_device or "",
        "neighbor_port": port.neighbor_port or "",
        "neighbor_ip": port.neighbor_ip,
        "connected_device": port.connected_device or "",
        "device_type": port.device_type or "",
        "owner": port.owner or "",
        "ip_address": port.ip_address,
        "mac_address": port.mac_address or "",
        "mac_addresses": port.mac_addresses or "",
        "mac_count": int(port.mac_count or 0),
        "description": port.description or "",
        "snmp_alias": port.snmp_alias or "",
        "vlan": port.vlan,
        "port_mode": port.port_mode or "",
        "access_vlan": port.access_vlan,
        "native_vlan": port.native_vlan,
        "voice_vlan": port.voice_vlan,
        "trunk_vlans": port.trunk_vlans or "",
        "source": source or "",
        "note": note or "",
        "identity_hash": port_identity_hash(port),
    }




def history_has_identity_data(history) -> bool:
    # Phase79.2.6: compatibility helper for views/imports and strict UI truth guard.
    # Do not count poll timestamps, VLAN, status, mode, neighbor_source or mac_count alone
    # as endpoint identity. Only real endpoint/device evidence is accepted.
    if history is None:
        return False
    if _identity_clean(getattr(history, "connected_device", "")):
        return True
    if _identity_clean(getattr(history, "neighbor_device", "")) or _identity_clean(getattr(history, "neighbor_port", "")):
        return True
    if _identity_clean(getattr(history, "neighbor_ip", "")) or _identity_clean(getattr(history, "ip_address", "")):
        return True
    if _identity_clean(getattr(history, "mac_address", "")) or _first_mac(getattr(history, "mac_addresses", "")):
        return True
    device_type = _identity_clean(getattr(history, "device_type", ""))
    if device_type and device_type.lower() not in ("unknown", "نامشخص"):
        return True
    if _identity_clean(getattr(history, "owner", "")):
        return True
    return False


def record_port_identity_snapshot(port: Port, *, source: str = "discovery", observed_at=None, force: bool = False, note: str = "") -> Optional[PortConnectionHistory]:
    if not force and not port_has_identity_data(port):
        return None

    observed_at = observed_at or timezone.now()
    identity_hash = port_identity_hash(port)
    latest = PortConnectionHistory.objects.filter(port=port).order_by("-observed_at", "-id").first()

    if latest and latest.event_type == PortConnectionHistory.EventType.SEEN and latest.identity_hash == identity_hash:
        latest.last_verified_at = observed_at
        latest.occurrence_count = int(latest.occurrence_count or 0) + 1
        latest.status_after = port.status or ""
        latest.save(update_fields=["last_verified_at", "occurrence_count", "status_after"])
        return latest

    return PortConnectionHistory.objects.create(**_history_kwargs(
        port,
        event_type=PortConnectionHistory.EventType.SEEN,
        source=source,
        observed_at=observed_at,
        note=note,
    ))


def record_port_connection_event(port: Port, *, event_type: str, source: str = "snmp_status", observed_at=None, previous_status: str = "", note: str = "") -> Optional[PortConnectionHistory]:
    if not port_has_identity_data(port):
        latest_identity = PortConnectionHistory.objects.filter(port=port).exclude(identity_hash="").order_by("-observed_at", "-id").first()
        if latest_identity:
            return PortConnectionHistory.objects.create(
                port=port,
                switch=port.switch,
                interface_name=port.interface_name,
                event_type=event_type,
                status_before=previous_status or "",
                status_after=port.status or "",
                observed_at=observed_at or timezone.now(),
                last_verified_at=observed_at or timezone.now(),
                neighbor_source=latest_identity.neighbor_source,
                neighbor_device=latest_identity.neighbor_device,
                neighbor_port=latest_identity.neighbor_port,
                neighbor_ip=latest_identity.neighbor_ip,
                connected_device=latest_identity.connected_device,
                device_type=latest_identity.device_type,
                owner=latest_identity.owner,
                ip_address=latest_identity.ip_address,
                mac_address=latest_identity.mac_address,
                mac_addresses=latest_identity.mac_addresses,
                mac_count=latest_identity.mac_count,
                description=latest_identity.description,
                snmp_alias=latest_identity.snmp_alias,
                vlan=latest_identity.vlan,
                port_mode=latest_identity.port_mode,
                access_vlan=latest_identity.access_vlan,
                native_vlan=latest_identity.native_vlan,
                voice_vlan=latest_identity.voice_vlan,
                trunk_vlans=latest_identity.trunk_vlans,
                source=source or "",
                note=note or "copied from latest identity snapshot",
                identity_hash=latest_identity.identity_hash,
            )
        return None

    return PortConnectionHistory.objects.create(**_history_kwargs(
        port,
        event_type=event_type,
        source=source,
        observed_at=observed_at or timezone.now(),
        previous_status=previous_status,
        note=note,
    ))


def latest_port_connection(port: Port) -> Optional[PortConnectionHistory]:
    # Phase79.2.6: return only records that contain real endpoint identity.
    # Old empty snapshots may have non-empty identity_hash because VLAN/mode existed.
    qs = PortConnectionHistory.objects.filter(port=port).order_by("-observed_at", "-id")[:50]
    for item in qs:
        if history_has_identity_data(item):
            return item
    return None