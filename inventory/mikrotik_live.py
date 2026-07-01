from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from django.utils import timezone

from .models import RouterHealthSnapshot, Switch


READ_ONLY_ROUTEROS_COMMANDS = (
    "/system resource print",
    "/system identity print",
    "/interface print terse",
    "/interface wireguard peers print terse",
)

TUNNEL_KEYWORDS = (
    "wireguard",
    "l2tp",
    "eoip",
    "gre",
    "ovpn",
    "pptp",
    "sstp",
    "vpn",
)


@dataclass
class RouterOSLivePollResult:
    ok: bool
    status: str
    message: str
    cpu_load: int | None = None
    memory_free_mb: int | None = None
    uptime: str = ""
    routeros_version: str = ""
    tunnel_count: int = 0
    active_tunnel_count: int = 0
    raw_summary: str = ""
    snapshot: RouterHealthSnapshot | None = None


def _parse_percent(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*%", str(text or ""))
    if not match:
        return None
    value = int(match.group(1))
    return max(0, min(value, 100))


def _memory_to_mb(value: str) -> int | None:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return None
    match = re.match(r"([0-9]+(?:\.[0-9]+)?)(kib|kb|mib|mb|gib|gb)?", text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or ""
    if unit in {"kib", "kb"}:
        return int(round(number / 1024))
    if unit in {"gib", "gb"}:
        return int(round(number * 1024))
    return int(round(number))


def _extract_resource_field(resource_text: str, field_name: str) -> str:
    pattern = rf"(?:^|\n)\s*{re.escape(field_name)}\s*:\s*([^\n\r]+)"
    match = re.search(pattern, resource_text or "", flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _is_tunnel_line(line: str) -> bool:
    lower = str(line or "").lower()
    return any(keyword in lower for keyword in TUNNEL_KEYWORDS)


def _is_running_line(line: str) -> bool:
    lower = str(line or "").lower()
    return (
        " running=yes" in lower
        or " disabled=no" in lower and "running" in lower
        or lower.startswith("r ")
        or " flags=r" in lower
        or " r " in lower[:8]
    )


def _count_tunnels(interface_text: str) -> tuple[int, int]:
    tunnel_lines = [line.strip() for line in str(interface_text or "").splitlines() if _is_tunnel_line(line)]
    active_lines = [line for line in tunnel_lines if _is_running_line(line)]
    return len(tunnel_lines), len(active_lines)


def parse_routeros_health(resource_text: str, identity_text: str, interface_text: str, wireguard_peer_text: str = "") -> dict:
    cpu_load = _parse_percent(_extract_resource_field(resource_text, "cpu-load"))
    memory_free_mb = _memory_to_mb(_extract_resource_field(resource_text, "free-memory"))
    uptime = _extract_resource_field(resource_text, "uptime")
    routeros_version = _extract_resource_field(resource_text, "version")
    tunnel_count, active_tunnel_count = _count_tunnels(interface_text)

    if wireguard_peer_text:
        wg_peer_lines = [line for line in wireguard_peer_text.splitlines() if line.strip() and not line.strip().startswith("#")]
        if wg_peer_lines:
            tunnel_count = max(tunnel_count, len(wg_peer_lines))
            active_tunnel_count = max(active_tunnel_count, sum(1 for line in wg_peer_lines if "disabled=no" in line.lower() or "last-handshake" in line.lower()))

    return {
        "cpu_load": cpu_load,
        "memory_free_mb": memory_free_mb,
        "uptime": uptime,
        "routeros_version": routeros_version,
        "tunnel_count": tunnel_count,
        "active_tunnel_count": active_tunnel_count,
        "identity": identity_text.strip(),
    }


def _safe_raw_summary(parts: Iterable[tuple[str, str]]) -> str:
    chunks = []
    for title, body in parts:
        chunks.append(f"===== {title} =====")
        chunks.append(str(body or "").strip()[:4000])
    return "\n".join(chunks)[:12000]


def save_router_health_snapshot(switch: Switch, source: str, status: str, parsed: dict, raw_summary: str, notes: str = "") -> RouterHealthSnapshot:
    return RouterHealthSnapshot.objects.create(
        switch=switch,
        status=status,
        source=source,
        cpu_load=parsed.get("cpu_load"),
        memory_free_mb=parsed.get("memory_free_mb"),
        uptime=parsed.get("uptime", "") or "",
        routeros_version=parsed.get("routeros_version", "") or "",
        tunnel_count=int(parsed.get("tunnel_count") or 0),
        active_tunnel_count=int(parsed.get("active_tunnel_count") or 0),
        raw_summary=raw_summary,
        notes=notes,
    )


def poll_routeros_health_ssh(switch: Switch, username: str, password: str, timeout: int = 12) -> RouterOSLivePollResult:
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return RouterOSLivePollResult(ok=False, status=RouterHealthSnapshot.HealthStatus.WARNING, message="Username و Password لازم است.")

    try:
        from netmiko import ConnectHandler
    except Exception as exc:
        parsed = {}
        snapshot = save_router_health_snapshot(
            switch=switch,
            source=RouterHealthSnapshot.Source.SSH,
            status=RouterHealthSnapshot.HealthStatus.WARNING,
            parsed=parsed,
            raw_summary=f"Netmiko import failed: {exc}",
            notes="Live poll failed before connection.",
        )
        return RouterOSLivePollResult(ok=False, status=snapshot.status, message=f"Netmiko آماده نیست: {exc}", snapshot=snapshot)

    host = str(switch.management_ip)
    port = int(switch.ssh_port or 22)
    device = {
        "device_type": "mikrotik_routeros",
        "host": host,
        "username": username,
        "password": password,
        "port": port,
        "timeout": int(timeout or 12),
        "conn_timeout": int(timeout or 12),
        "banner_timeout": int(timeout or 12),
        "auth_timeout": int(timeout or 12),
    }

    outputs = {}
    try:
        connection = ConnectHandler(**device)
        try:
            for command in READ_ONLY_ROUTEROS_COMMANDS:
                try:
                    outputs[command] = connection.send_command(command, read_timeout=timeout)
                except Exception as command_exc:
                    outputs[command] = f"COMMAND_ERROR: {command_exc}"
        finally:
            connection.disconnect()

        parsed = parse_routeros_health(
            resource_text=outputs.get("/system resource print", ""),
            identity_text=outputs.get("/system identity print", ""),
            interface_text=outputs.get("/interface print terse", ""),
            wireguard_peer_text=outputs.get("/interface wireguard peers print terse", ""),
        )
        raw_summary = _safe_raw_summary(outputs.items())
        snapshot = save_router_health_snapshot(
            switch=switch,
            source=RouterHealthSnapshot.Source.SSH,
            status=RouterHealthSnapshot.HealthStatus.UP,
            parsed=parsed,
            raw_summary=raw_summary,
            notes="Phase 57 read-only SSH poll. No RouterOS configuration command was executed.",
        )
        return RouterOSLivePollResult(
            ok=True,
            status=snapshot.status,
            message=f"Live read-only poll OK for {switch.name}",
            cpu_load=snapshot.cpu_load,
            memory_free_mb=snapshot.memory_free_mb,
            uptime=snapshot.uptime,
            routeros_version=snapshot.routeros_version,
            tunnel_count=snapshot.tunnel_count,
            active_tunnel_count=snapshot.active_tunnel_count,
            raw_summary=raw_summary,
            snapshot=snapshot,
        )
    except Exception as exc:
        raw_summary = f"SSH poll failed for {switch.name} {host}:{port}\n{exc}"
        snapshot = save_router_health_snapshot(
            switch=switch,
            source=RouterHealthSnapshot.Source.SSH,
            status=RouterHealthSnapshot.HealthStatus.DOWN,
            parsed={},
            raw_summary=raw_summary,
            notes="Phase 57 read-only SSH poll failed. No RouterOS configuration command was executed.",
        )
        return RouterOSLivePollResult(ok=False, status=snapshot.status, message=f"Live poll failed: {exc}", raw_summary=raw_summary, snapshot=snapshot)
