from __future__ import annotations

import csv
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.db import OperationalError, connection, close_old_connections, transaction
from django.utils import timezone

from inventory.models import EndpointObservation, NetworkEndpoint, Port, Switch
from inventory.snmp_tools import (
    DOT1D_BASE_PORT_IFINDEX,
    DOT1D_TP_FDB_PORT,
    DOT1D_TP_FDB_STATUS,
    IP_NET_TO_MEDIA_PHYS_ADDRESS,
    SnmpError,
    build_ifindex_port_map,
    format_mac,
    format_mac_value,
    ipv4_from_index_parts,
    make_client,
)

MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
REPORT_DIR = Path(settings.BASE_DIR) / "reports"

SQLITE_BUSY_TIMEOUT_MS = 60000
DB_WRITE_RETRY_ATTEMPTS = 8
DB_WRITE_RETRY_BASE_SLEEP = 0.35


def configure_sqlite_busy_timeout(ms: int = SQLITE_BUSY_TIMEOUT_MS) -> None:
    """Best-effort SQLite busy timeout for scheduled endpoint writes."""
    try:
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute(f"PRAGMA busy_timeout={int(ms)}")
    except Exception:
        return


def is_database_locked_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def run_with_db_retry(func, *, attempts: int = DB_WRITE_RETRY_ATTEMPTS, base_sleep: float = DB_WRITE_RETRY_BASE_SLEEP):
    last_exc = None
    for attempt in range(1, attempts + 1):
        close_old_connections()
        configure_sqlite_busy_timeout()
        try:
            return func()
        except OperationalError as exc:
            last_exc = exc
            if not is_database_locked_error(exc) or attempt >= attempts:
                raise
            time.sleep(base_sleep * attempt)
    if last_exc:
        raise last_exc
    return None



@dataclass(frozen=True)
class EndpointCandidate:
    source: str
    mac_address: str
    ip_address: str = ""
    vlan: int | None = None
    switch_id: int | None = None
    switch_name: str = ""
    port_id: int | None = None
    interface_name: str = ""
    connection_type: str = "unknown"
    confidence: int = 50
    via_device_name: str = ""
    source_detail: str = ""
    raw_data: str = ""

    @property
    def identity_key(self) -> str:
        return make_identity_key(self.mac_address, self.ip_address, self.vlan)


def normalize_mac(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", ":").replace(".", "")
    if ":" not in text and len(text) == 12:
        text = ":".join(text[i:i + 2] for i in range(0, 12, 2))
    text = re.sub(r"[^0-9a-f:]", "", text)
    if MAC_RE.match(text):
        return text
    return ""


def make_identity_key(mac: str, ip: str | None, vlan: int | None) -> str:
    return "|".join([normalize_mac(mac), str(ip or ""), str(vlan or "")])


def split_mac_lines(value: str) -> list[str]:
    seen = []
    for raw in re.split(r"[\s,;]+", value or ""):
        mac = normalize_mac(raw)
        if mac and mac not in seen:
            seen.append(mac)
    return seen


def is_ap_port(port: Port | None) -> bool:
    if not port:
        return False
    text = " ".join([
        port.device_type or "",
        port.connected_device or "",
        port.description or "",
        port.snmp_alias or "",
        port.neighbor_device or "",
        port.neighbor_port or "",
    ]).lower()
    return any(token in text for token in ["access_point", "access point", "ap", "cap", "wifi", "wireless"])


def is_network_device_port(port: Port | None) -> bool:
    if not port:
        return False
    if port.neighbor_device:
        return True
    if port.device_type in {Port.DeviceType.SWITCH, Port.DeviceType.UPLINK, Port.DeviceType.ACCESS_POINT}:
        return True
    text = " ".join([
        port.connected_device or "",
        port.description or "",
        port.snmp_alias or "",
        port.neighbor_device or "",
    ]).lower()
    return any(token in text for token in ["switch", "nexus", "mikrotik", "router", "uplink", "trunk", "ap", "cap"])


def classify_port_connection(port: Port | None, mac_count_hint: int = 0) -> tuple[str, int]:
    if not port:
        return "behind_router", 60
    if is_ap_port(port):
        return "behind_ap", 75
    if port.port_mode == Port.PortMode.TRUNK or port.device_type == Port.DeviceType.UPLINK:
        return "behind_trunk", 55
    if is_network_device_port(port):
        return "behind_network_device", 60
    if mac_count_hint > 1 or (port.mac_count or 0) > 1:
        return "behind_trunk", 50
    if port.port_mode == Port.PortMode.ACCESS or not port.port_mode or port.port_mode == Port.PortMode.UNKNOWN:
        return "direct_port", 95
    return "unknown", 40


def infer_vlan_from_ip(ip_address: str | None) -> int | None:
    text = str(ip_address or "").strip()
    if text.startswith("192.168.0."):
        return 1
    if text.startswith("172.16.25."):
        return 101
    if text.startswith("172.16.23."):
        return 100
    return None


def infer_vlan(port: Port | None, fallback: int | None = None, ip_address: str | None = None) -> int | None:
    if fallback is not None:
        return fallback
    if port:
        value = port.access_vlan or port.vlan or port.native_vlan
        if value is not None:
            return value
    return infer_vlan_from_ip(ip_address)


def candidate_from_port_identity(port: Port, now) -> Iterable[EndpointCandidate]:
    macs = split_mac_lines(port.mac_addresses)
    primary = normalize_mac(port.mac_address)
    if primary and primary not in macs:
        macs.insert(0, primary)
    if not macs:
        return []
    conn_type, confidence = classify_port_connection(port, len(macs))
    items = []
    for mac in macs:
        ip = str(port.ip_address or "") if len(macs) == 1 else ""
        items.append(EndpointCandidate(
            source="db_port_identity",
            mac_address=mac,
            ip_address=ip,
            vlan=infer_vlan(port, ip_address=ip),
            switch_id=port.switch_id,
            switch_name=port.switch.name,
            port_id=port.id,
            interface_name=port.interface_name,
            connection_type=conn_type,
            confidence=confidence,
            via_device_name=port.neighbor_device or port.connected_device or "",
            source_detail="Port.mac_address/mac_addresses/ip_address",
            raw_data=json.dumps({
                "port_mode": port.port_mode,
                "mac_count": port.mac_count,
                "neighbor_device": port.neighbor_device,
                "connected_device": port.connected_device,
            }, ensure_ascii=False),
        ))
    return items


def optional_walk(client, label: str, oid, *, indexed=False, raw=False, max_steps=10000):
    try:
        if indexed:
            return client.walk_indexed(oid, max_steps=max_steps, raw=raw)
        if raw:
            return client.walk_raw(oid, max_steps=max_steps)
        return client.walk(oid, max_steps=max_steps)
    except Exception as exc:
        return {"__error__": str(exc), "__label__": label}


def collect_snmp_candidates(switch: Switch, now) -> tuple[list[EndpointCandidate], list[str]]:
    errors: list[str] = []
    candidates: list[EndpointCandidate] = []
    client = make_client(switch, retries=1)
    try:
        by_ifindex, _by_interface, _raw, _aliases = build_ifindex_port_map(switch, client)
    except Exception as exc:
        raise SnmpError(str(exc)) from exc

    dot1d_base_port = optional_walk(client, "DOT1D_BASE_PORT_IFINDEX", DOT1D_BASE_PORT_IFINDEX)
    dot1d_fdb_port = optional_walk(client, "DOT1D_TP_FDB_PORT", DOT1D_TP_FDB_PORT, indexed=True)
    dot1d_fdb_status = optional_walk(client, "DOT1D_TP_FDB_STATUS", DOT1D_TP_FDB_STATUS, indexed=True)
    arp_mac_raw = optional_walk(client, "IP_NET_TO_MEDIA_PHYS_ADDRESS", IP_NET_TO_MEDIA_PHYS_ADDRESS, indexed=True, raw=True)

    for table in [dot1d_base_port, dot1d_fdb_port, dot1d_fdb_status, arp_mac_raw]:
        if isinstance(table, dict) and "__error__" in table:
            errors.append(f"{table.get('__label__')}={table.get('__error__')}")

    if "__error__" in dot1d_base_port:
        dot1d_base_port = {}
    if "__error__" in dot1d_fdb_port:
        dot1d_fdb_port = {}
    if "__error__" in dot1d_fdb_status:
        dot1d_fdb_status = {}
    if "__error__" in arp_mac_raw:
        arp_mac_raw = {}

    arp_ips_by_mac: dict[str, set[str]] = defaultdict(set)
    arp_ifindexes_by_mac: dict[str, set[int]] = defaultdict(set)
    for index, raw_mac in arp_mac_raw.items():
        if len(index) < 5:
            continue
        try:
            if_index = int(index[0])
        except Exception:
            continue
        ip_address = ipv4_from_index_parts(index[-4:])
        mac = normalize_mac(format_mac_value(raw_mac))
        if not ip_address or not mac:
            continue
        arp_ips_by_mac[mac].add(ip_address)
        arp_ifindexes_by_mac[mac].add(if_index)

    seen_fdb_macs = set()
    for mac_index, bridge_port in dot1d_fdb_port.items():
        status = dot1d_fdb_status.get(mac_index)
        if status not in (None, 3):
            continue
        try:
            bridge_port_int = int(bridge_port or 0)
            if_index = int(dot1d_base_port.get(bridge_port_int) or 0)
        except Exception:
            continue
        port = by_ifindex.get(if_index)
        mac = normalize_mac(format_mac(mac_index))
        if not mac:
            continue
        seen_fdb_macs.add(mac)
        ips = sorted(arp_ips_by_mac.get(mac) or [""])
        conn_type, confidence = classify_port_connection(port, len(ips))
        for ip in ips:
            candidates.append(EndpointCandidate(
                source="snmp_fdb_arp",
                mac_address=mac,
                ip_address=ip,
                vlan=infer_vlan(port, ip_address=ip),
                switch_id=switch.id,
                switch_name=switch.name,
                port_id=port.id if port else None,
                interface_name=port.interface_name if port else "",
                connection_type=conn_type,
                confidence=confidence,
                via_device_name=(port.neighbor_device if port else "") or "",
                source_detail="FDB mapped to port; ARP joined by MAC when available",
                raw_data=json.dumps({"bridge_port": bridge_port, "if_index": if_index}, ensure_ascii=False),
            ))

    for mac, ips in arp_ips_by_mac.items():
        if mac in seen_fdb_macs:
            continue
        for ip in sorted(ips):
            ifindexes = sorted(arp_ifindexes_by_mac.get(mac) or [])
            mapped_ports = [by_ifindex.get(ifindex) for ifindex in ifindexes if by_ifindex.get(ifindex)]
            port = mapped_ports[0] if len(mapped_ports) == 1 else None
            conn_type, confidence = classify_port_connection(port, len(ips))
            if port is None:
                conn_type, confidence = "behind_router", 60
            candidates.append(EndpointCandidate(
                source="snmp_arp",
                mac_address=mac,
                ip_address=ip,
                vlan=infer_vlan(port, ip_address=ip),
                switch_id=switch.id,
                switch_name=switch.name,
                port_id=port.id if port else None,
                interface_name=port.interface_name if port else "",
                connection_type=conn_type,
                confidence=confidence,
                via_device_name=(port.neighbor_device if port else "") or "",
                source_detail="ARP table entry" + (" mapped by ifIndex" if port else " without physical port mapping"),
                raw_data=json.dumps({"ifindexes": ifindexes}, ensure_ascii=False),
            ))
    return candidates, errors


def collect_candidates(*, include_db=True, include_snmp=True, switch_name: str = "") -> tuple[list[EndpointCandidate], dict]:
    now = timezone.now()
    candidates: list[EndpointCandidate] = []
    errors: list[dict] = []
    devices_scanned = 0

    if include_db:
        ports = Port.objects.select_related("switch").filter(switch__is_active=True)
        if switch_name:
            ports = ports.filter(switch__name=switch_name)
        for port in ports.iterator():
            candidates.extend(candidate_from_port_identity(port, now))

    if include_snmp:
        switches = Switch.objects.filter(is_active=True, snmp_enabled=True).order_by("topology_position", "name")
        if switch_name:
            switches = switches.filter(name=switch_name)
        for switch in switches:
            devices_scanned += 1
            try:
                switch_candidates, switch_errors = collect_snmp_candidates(switch, now)
                candidates.extend(switch_candidates)
                if switch_errors:
                    errors.append({"switch": switch.name, "errors": switch_errors})
            except Exception as exc:
                errors.append({"switch": switch.name, "errors": [str(exc)]})

    meta = {"devices_scanned": devices_scanned, "device_errors": errors, "collected_at": now.isoformat()}
    return candidates, meta


def choose_best_candidates(candidates: list[EndpointCandidate]) -> dict[str, EndpointCandidate]:
    best: dict[str, EndpointCandidate] = {}
    for cand in candidates:
        if not cand.mac_address:
            continue
        prev = best.get(cand.identity_key)
        if prev is None or (cand.confidence, bool(cand.ip_address), cand.source) > (prev.confidence, bool(prev.ip_address), prev.source):
            best[cand.identity_key] = cand
    return best


def write_candidate_csv(candidates: Iterable[EndpointCandidate], filename: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / filename
    fields = [
        "source", "mac_address", "ip_address", "vlan", "connection_type", "confidence",
        "switch_name", "interface_name", "via_device_name", "source_detail", "identity_key",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for cand in candidates:
            writer.writerow({field: getattr(cand, field, "") if field != "identity_key" else cand.identity_key for field in fields})
    return path


def summarize(candidates: list[EndpointCandidate], best: dict[str, EndpointCandidate], meta: dict) -> dict:
    return {
        "observations_total": len(candidates),
        "unique_endpoint_candidates": len(best),
        "devices_scanned": meta.get("devices_scanned", 0),
        "device_error_count": len(meta.get("device_errors", [])),
        "by_vlan": dict(Counter(str(c.vlan if c.vlan is not None else "unknown") for c in best.values())),
        "by_connection_type": dict(Counter(c.connection_type for c in best.values())),
        "by_source": dict(Counter(c.source for c in candidates)),
    }


def upsert_endpoints(best: dict[str, EndpointCandidate], *, write_observations=True) -> dict:
    """Upsert endpoints with short transactions and SQLite lock retry."""
    now = timezone.now()
    updated = 0
    created = 0
    observations_created = 0
    lock_skipped = 0
    db_write_errors = 0
    configure_sqlite_busy_timeout()

    for key, cand in best.items():
        def write_one():
            switch = Switch.objects.filter(id=cand.switch_id).first() if cand.switch_id else None
            port = Port.objects.filter(id=cand.port_id).first() if cand.port_id else None
            with transaction.atomic():
                endpoint, was_created = NetworkEndpoint.objects.update_or_create(
                    identity_key=key,
                    defaults={
                        "mac_address": cand.mac_address,
                        "ip_address": cand.ip_address or None,
                        "vlan": cand.vlan,
                        "connection_type": cand.connection_type,
                        "status": NetworkEndpoint.Status.ACTIVE,
                        "confidence": cand.confidence,
                        "last_seen_switch": switch,
                        "last_seen_port": port,
                        "via_device_name": cand.via_device_name or "",
                        "sources": cand.source,
                        "evidence_summary": cand.source_detail,
                        "last_seen": now,
                        "is_active": True,
                    },
                )
                observation_created = False
                if write_observations:
                    EndpointObservation.objects.create(
                        endpoint=endpoint,
                        switch=switch,
                        port=port,
                        source=cand.source,
                        mac_address=cand.mac_address,
                        ip_address=cand.ip_address or None,
                        vlan=cand.vlan,
                        connection_type=cand.connection_type,
                        confidence=cand.confidence,
                        source_device_name=cand.switch_name,
                        source_interface=cand.interface_name,
                        source_detail=cand.source_detail,
                        raw_data=cand.raw_data,
                        is_selected=True,
                    )
                    observation_created = True
                return was_created, observation_created

        try:
            was_created, observation_created = run_with_db_retry(write_one)
        except OperationalError as exc:
            if is_database_locked_error(exc):
                lock_skipped += 1
                continue
            db_write_errors += 1
            continue
        if was_created:
            created += 1
        else:
            updated += 1
        if observation_created:
            observations_created += 1

    return {
        "created": created,
        "updated": updated,
        "observations_created": observations_created,
        "lock_skipped": lock_skipped,
        "db_write_errors": db_write_errors,
        "write_observations": bool(write_observations),
        "busy_timeout_ms": SQLITE_BUSY_TIMEOUT_MS,
        "retry_attempts": DB_WRITE_RETRY_ATTEMPTS,
    }
