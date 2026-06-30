from __future__ import annotations

import re
from datetime import timedelta
from dataclasses import dataclass
from typing import Iterable

from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from .models import Port, RouterHealthSnapshot, RouterTunnel, RoutingPolicy, Site, Switch, WanLink
from .mikrotik_live import RouterOSLivePollResult, poll_routeros_health_ssh
from .views import VISIBLE_PORT_PREFETCH, is_visible_switchmap_interface


MIKROTIK_NAME_HINTS = (
    "mikrotik",
    "routeros",
    "rb5009",
    "rb2011",
    "rb450",
    "hex",
    "hex-s",
    "hEX",
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


@dataclass(frozen=True)
class MikroTikRelationshipHint:
    tunnel_type: str
    relation: str
    local_ip: str
    remote_ip: str
    routed_networks: str
    policy_hint: str
    confidence: str = "inferred"


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9آ-ی]+", "", text)


def _text_blob(switch: Switch) -> str:
    return " ".join(
        [
            switch.name or "",
            switch.model or "",
            switch.location or "",
            switch.site or "",
            str(switch.management_ip or ""),
            switch.notes or "",
        ]
    ).lower()


def _is_switchmap_test_device(switch: Switch | None) -> bool:
    if switch is None:
        return False
    blob = _text_blob(switch)
    return any(token in blob for token in SWITCHMAP_TEST_DEVICE_TOKENS)


def _is_mikrotik_candidate(switch: Switch) -> bool:
    if _is_switchmap_test_device(switch):
        return False
    if getattr(switch, "vendor", "") == Switch.Vendor.MIKROTIK:
        return True
    blob = _text_blob(switch)
    return any(token.lower() in blob for token in MIKROTIK_NAME_HINTS)


def _device_role_key(switch: Switch) -> str:
    role = getattr(switch, "device_role", "") or ""
    family = getattr(switch, "device_family", "") or ""
    blob = _text_blob(switch)

    if role == Switch.DeviceRole.CORE_ROUTER or "rb5009" in blob:
        return "core_router"
    if role == Switch.DeviceRole.EDGE_ROUTER or "hex" in blob:
        return "edge_router"
    if role == Switch.DeviceRole.REMOTE_OFFICE or any(token in blob for token in ("rb2011", "iranmall", "alihome", "karaj", "vps", "germany", "chr")):
        return "remote_router"
    if role == Switch.DeviceRole.ACCESS_POINT or family == Switch.DeviceFamily.MIKROTIK_AP or "cap" in blob or "ap" in blob:
        return "access_point"
    if family == Switch.DeviceFamily.MIKROTIK_SWITCH or "crs" in blob:
        return "routeros_switch"
    return "routeros_device"


def _role_label(role_key: str) -> str:
    return {
        "core_router": "Core Router",
        "edge_router": "Edge / Transit Router",
        "remote_router": "Remote Router",
        "access_point": "AP / CAP",
        "routeros_switch": "RouterOS Switch",
        "routeros_device": "RouterOS Device",
    }.get(role_key, "RouterOS Device")


def _device_site(switch: Switch) -> str:
    if switch.site:
        return switch.site
    blob = _text_blob(switch)
    if "iranmall" in blob or "tehran" in blob or "2011" in blob:
        return "Tehran / Iranmall"
    if "karaj" in blob or "ax3" in blob:
        return "Karaj"
    if "alihome" in blob or "ali home" in blob or "192.168.2" in blob:
        return "Ali Home"
    if "germany" in blob or "vps" in blob or "213.183" in blob:
        return "Germany VPS"
    if "cap" in blob or "172.16.25" in blob:
        return "Qazvin / Wireless"
    return "Qazvin"


def _wan_hint(switch: Switch) -> str:
    blob = _text_blob(switch)
    if "rb5009" in blob:
        return "Starlink + Rasana/Pishtaz"
    if "karaj" in blob or "ax3" in blob:
        return "Local Fiber/SIM + WG backhaul"
    if "alihome" in blob or "192.168.2" in blob:
        return "Home ISP + L2TP/IPsec"
    if "germany" in blob or "vps" in blob:
        return "VPS Public Internet"
    if "hex" in blob or "192.168.0.253" in blob:
        return "Local LAN / Transit"
    if "cap" in blob:
        return "CAP management VLAN"
    return "Unknown / not documented"


def _health_from_switch(switch: Switch) -> tuple[str, str]:
    if not switch.is_active:
        return "down", "Inactive"
    if switch.snmp_enabled and switch.snmp_last_error:
        return "warning", "SNMP error"
    if switch.snmp_enabled and switch.snmp_last_poll:
        return "up", "SNMP polled"
    if switch.discovery_last_error:
        return "warning", "Discovery error"
    return "unknown", "No live poll"


def _time_text(value) -> str:
    if not value:
        return "-"
    try:
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def _is_hub_candidate(switch: Switch) -> bool:
    blob = _text_blob(switch)
    return (
        getattr(switch, "device_role", "") == Switch.DeviceRole.CORE_ROUTER
        or "rb5009" in blob
        or str(switch.management_ip) == "192.168.0.234"
    )


def _find_hub(devices: list[dict]) -> dict | None:
    for device in devices:
        if _is_hub_candidate(device["switch"]):
            return device
    for device in devices:
        if device["role_key"] == "core_router":
            return device
    return devices[0] if devices else None


def _relationship_hint(switch: Switch) -> MikroTikRelationshipHint:
    blob = _text_blob(switch)
    ip = str(switch.management_ip or "")

    if "rb5009" in blob or ip == "192.168.0.234":
        return MikroTikRelationshipHint(
            tunnel_type="Core",
            relation="HQ hub",
            local_ip="192.168.0.234",
            remote_ip="-",
            routed_networks="192.168.0.0/24 + VPN spokes",
            policy_hint="Iran traffic via Rasana/Pishtaz; foreign traffic via Starlink.",
            confidence="documented",
        )
    if "rb2011" in blob or "iranmall" in blob or ip.startswith("172.20.20."):
        return MikroTikRelationshipHint(
            tunnel_type="WireGuard",
            relation="Tehran / Iranmall spoke",
            local_ip="172.16.11.1",
            remote_ip="172.16.11.2",
            routed_networks="192.168.101.0/24 ↔ 192.168.0.0/24",
            policy_hint="Primary site-to-site route; EoIP remains backup when documented.",
            confidence="documented",
        )
    if "alihome" in blob or "ali home" in blob or ip.startswith("192.168.2."):
        return MikroTikRelationshipHint(
            tunnel_type="L2TP/IPsec",
            relation="Ali Home spoke",
            local_ip="10.255.20.1",
            remote_ip="10.255.20.2",
            routed_networks="192.168.2.0/24 ↔ HQ",
            policy_hint="Foreign traffic can return through HQ/Starlink; local Iran traffic stays local.",
            confidence="documented",
        )
    if "ax3" in blob or "karaj" in blob or ip.startswith("192.168.102."):
        return MikroTikRelationshipHint(
            tunnel_type="WireGuard",
            relation="Karaj spoke",
            local_ip="10.255.30.1",
            remote_ip="10.255.30.2",
            routed_networks="192.168.102.0/24 ↔ HQ",
            policy_hint="Iran traffic local WAN; foreign traffic via WG to HQ/Starlink.",
            confidence="documented",
        )
    if "vps" in blob or "germany" in blob or "chr" in blob or ip.startswith("213.183."):
        return MikroTikRelationshipHint(
            tunnel_type="VPN Endpoint",
            relation="Germany VPS / external endpoint",
            local_ip="HQ/VPN side",
            remote_ip=ip or "VPS public IP",
            routed_networks="VPN / external services",
            policy_hint="Use as remote endpoint; verify live peer status before operational decisions.",
            confidence="inferred",
        )
    if "hex" in blob or ip == "192.168.0.253":
        return MikroTikRelationshipHint(
            tunnel_type="Local Transit",
            relation="Qazvin edge/transit",
            local_ip="192.168.0.253",
            remote_ip="192.168.0.234",
            routed_networks="Local LAN / internet handoff",
            policy_hint="Treat as local transit; do not mix with switch uplink topology.",
            confidence="documented",
        )
    if "cap" in blob or "172.16.25" in blob:
        return MikroTikRelationshipHint(
            tunnel_type="CAP / AP",
            relation="Wireless management",
            local_ip=ip,
            remote_ip="CAPsMAN / management VLAN",
            routed_networks="Wireless management only",
            policy_hint="Monitor as AP, not as routing hub.",
            confidence="inferred",
        )
    return MikroTikRelationshipHint(
        tunnel_type="Unknown",
        relation="Needs review",
        local_ip=ip,
        remote_ip="-",
        routed_networks="-",
        policy_hint="Set vendor, role, site and tunnel notes for better mapping.",
        confidence="needs_review",
    )


def _port_summary(switch: Switch) -> dict:
    ports = [port for port in switch.ports.all() if is_visible_switchmap_interface(port.interface_name)]
    tunnels = [
        port for port in ports
        if any(token in " ".join([port.interface_name, port.description, port.snmp_alias, port.neighbor_device]).lower() for token in ("wg", "wireguard", "l2tp", "eoip", "gre", "ovpn", "vpn", "tunnel"))
    ]
    uplinks = [
        port for port in ports
        if port.neighbor_device or port.port_mode == Port.PortMode.TRUNK or str(port.device_type) in (Port.DeviceType.SWITCH, Port.DeviceType.UPLINK)
    ]
    errors = [port for port in ports if port.status == Port.Status.ERROR or "err" in " ".join([port.description, port.snmp_alias, port.snmp_oper_status]).lower()]
    return {
        "visible": len(ports),
        "tunnels": len(tunnels),
        "uplinks": len(uplinks),
        "errors": len(errors),
    }


def _device_payload(switch: Switch) -> dict:
    role_key = _device_role_key(switch)
    health_key, health_label = _health_from_switch(switch)
    hint = _relationship_hint(switch)
    ports = _port_summary(switch)
    return {
        "switch": switch,
        "role_key": role_key,
        "role_label": _role_label(role_key),
        "site": _device_site(switch),
        "wan_hint": _wan_hint(switch),
        "health_key": health_key,
        "health_label": health_label,
        "last_poll_text": _time_text(switch.snmp_last_poll or switch.discovery_last_poll),
        "hint": hint,
        "port_summary": ports,
        "is_router": role_key in {"core_router", "edge_router", "remote_router"},
    }


def _relationship_status(device: dict) -> tuple[str, str]:
    if device["hint"].confidence == "documented":
        if device["health_key"] == "up":
            return "up", "Documented / SNMP polled"
        return "warning", "Documented / needs live poll"
    if device["hint"].confidence == "inferred":
        return "unknown", "Inferred"
    return "warning", "Needs review"


def _build_relationships(devices: list[dict], hub: dict | None) -> list[dict]:
    relationships = []
    if not hub:
        return relationships
    for device in devices:
        if device is hub:
            continue
        hint = device["hint"]
        status_key, status_label = _relationship_status(device)
        relationships.append(
            {
                "hub": hub,
                "device": device,
                "tunnel_type": hint.tunnel_type,
                "relation": hint.relation,
                "local_ip": hint.local_ip,
                "remote_ip": hint.remote_ip,
                "routed_networks": hint.routed_networks,
                "policy_hint": hint.policy_hint,
                "confidence": hint.confidence,
                "status_key": status_key,
                "status_label": status_label,
            }
        )
    return relationships


def _routing_policies(devices: list[dict]) -> list[dict]:
    policies = []
    for device in devices:
        hint = device["hint"]
        policies.append(
            {
                "device": device,
                "site": device["site"],
                "wan": device["wan_hint"],
                "tunnel": hint.tunnel_type,
                "routed_networks": hint.routed_networks,
                "policy_hint": hint.policy_hint,
                "confidence": hint.confidence,
            }
        )
    return policies


def _ip_text(value) -> str:
    if not value:
        return "-"
    return str(value)


def _switch_label(switch: Switch | None, fallback: str = "-") -> str:
    if switch:
        return switch.name
    return fallback


def _latest_health_by_switch() -> dict[int, RouterHealthSnapshot]:
    latest = {}
    rows = RouterHealthSnapshot.objects.select_related("switch").order_by("switch_id", "-collected_at")
    for row in rows:
        if row.switch_id not in latest:
            latest[row.switch_id] = row
    return latest


def _live_poll_meta() -> dict:
    latest_ssh = RouterHealthSnapshot.objects.filter(source=RouterHealthSnapshot.Source.SSH).order_by("-collected_at").first()
    return {
        "live_poll_count": RouterHealthSnapshot.objects.filter(source=RouterHealthSnapshot.Source.SSH).count(),
        "latest_live_poll": latest_ssh,
        "latest_live_poll_text": _time_text(latest_ssh.collected_at) if latest_ssh else "-",
    }




def _snapshot_message(row: RouterHealthSnapshot) -> str:
    raw = (row.notes or row.raw_summary or "").strip()
    if not raw:
        return "-"
    first_line = raw.replace("\r", "").split("\n", 1)[0].strip()
    if len(first_line) > 180:
        first_line = first_line[:177] + "..."
    return first_line or "-"


def _latest_live_poll_rows(limit: int = 8) -> list[dict]:
    rows = (
        RouterHealthSnapshot.objects.filter(source=RouterHealthSnapshot.Source.SSH)
        .select_related("switch")
        .order_by("-collected_at")[:limit]
    )
    results = []
    for row in rows:
        if _is_switchmap_test_device(row.switch):
            continue
        results.append({
            "snapshot": row,
            "switch": row.switch,
            "device_name": row.switch.name,
            "device_ip": str(row.switch.management_ip),
            "status": row.status,
            "status_label": row.get_status_display(),
            "collected_at": _time_text(row.collected_at),
            "cpu": row.cpu_load if row.cpu_load is not None else "-",
            "memory": row.memory_free_mb if row.memory_free_mb is not None else "-",
            "uptime": row.uptime or "-",
            "version": row.routeros_version or "-",
            "tunnels": row.tunnel_count,
            "active_tunnels": row.active_tunnel_count,
            "tunnel_ratio": f"{row.active_tunnel_count}/{row.tunnel_count}",
            "message": _snapshot_message(row),
            "url": _switch_detail_url(row.switch),
        })
    return results


def _live_poll_candidates(devices: list[dict]) -> list[dict]:
    return [device for device in devices if device.get("role_key") in {"core_router", "edge_router", "remote_router", "routeros_device"}]


def _percent(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round((part / total) * 100)))


def _device_has_auto_snmp(device: dict) -> bool:
    switch = device.get("switch")
    return bool(
        switch
        and getattr(switch, "snmp_enabled", False)
        and str(getattr(switch, "snmp_community", "") or "").strip()
    )


def _freshness_label(collected_at, now=None) -> tuple[str, str]:
    if not collected_at:
        return "stale", "No health data"
    now = now or timezone.now()
    if collected_at < now - timedelta(hours=2):
        return "stale", "Stale"
    return "fresh", "Fresh"


def _build_action_items(devices: list[dict], health_rows: list[dict], tunnel_rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    now = timezone.now()

    for row in health_rows:
        device = row.get("device") or {}
        switch = device.get("switch")
        if not switch or _is_switchmap_test_device(switch):
            continue
        status = row.get("status") or "unknown"
        freshness_key, freshness_text = _freshness_label(row.get("collected_raw"), now=now)
        url = _switch_detail_url(switch)

        if status == RouterHealthSnapshot.HealthStatus.DOWN:
            items.append({
                "severity": "critical",
                "title": f"{switch.name}: Router Down",
                "message": "آخرین Health Snapshot وضعیت Down ثبت کرده است.",
                "target": switch.name,
                "url": url,
            })
        elif status == RouterHealthSnapshot.HealthStatus.WARNING:
            items.append({
                "severity": "warning",
                "title": f"{switch.name}: Warning",
                "message": "آخرین Health Snapshot هشدار دارد و باید بررسی شود.",
                "target": switch.name,
                "url": url,
            })
        elif status in {RouterHealthSnapshot.HealthStatus.UNKNOWN, "unknown"}:
            items.append({
                "severity": "warning",
                "title": f"{switch.name}: Unknown Health",
                "message": "برای این Router هنوز وضعیت قابل اتکا ثبت نشده است.",
                "target": switch.name,
                "url": url,
            })

        if freshness_key == "stale":
            items.append({
                "severity": "warning",
                "title": f"{switch.name}: {freshness_text}",
                "message": "داده Health جدید نیست؛ Auto SNMP Poll باید اجرا یا بررسی شود.",
                "target": switch.name,
                "url": url,
            })

        if not _device_has_auto_snmp(device) and device.get("is_router"):
            items.append({
                "severity": "info",
                "title": f"{switch.name}: SNMP not ready",
                "message": "برای Poll خودکار پایه، SNMP Read Only روی این دستگاه در SwitchMap کامل نیست.",
                "target": switch.name,
                "url": url,
            })

    for row in tunnel_rows:
        status = row.get("status_key") or "unknown"
        if status in {RouterTunnel.Status.DOWN, RouterTunnel.Status.WARNING}:
            severity = "critical" if status == RouterTunnel.Status.DOWN else "warning"
            items.append({
                "severity": severity,
                "title": f"Tunnel: {row.get('source')} → {row.get('destination')}",
                "message": f"وضعیت مدل‌شده Tunnel برابر {row.get('status_label', status)} است.",
                "target": row.get("type", "Tunnel"),
                "url": _switch_detail_url(row.get("destination_switch")),
            })
        elif status in {RouterTunnel.Status.UNKNOWN, "unknown"} and row.get("confidence") == RouterTunnel.Confidence.DOCUMENTED:
            items.append({
                "severity": "warning",
                "title": f"Tunnel Unknown: {row.get('destination')}",
                "message": "Tunnel مستند است، ولی وضعیت Live قابل تصمیم‌گیری نیست.",
                "target": row.get("type", "Tunnel"),
                "url": _switch_detail_url(row.get("destination_switch")),
            })

    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    deduped = []
    seen = set()
    for item in sorted(items, key=lambda item: severity_rank.get(item.get("severity"), 9)):
        key = (item.get("severity"), item.get("title"), item.get("target"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:10]


def _build_monitoring_summary(devices: list[dict], foundation: dict, latest_live_poll_rows: list[dict]) -> dict:
    health_rows = foundation.get("health_rows", [])
    tunnel_rows = foundation.get("tunnel_rows", [])
    now = timezone.now()

    router_status = {"up": 0, "warning": 0, "down": 0, "unknown": 0}
    fresh_count = 0
    stale_count = 0
    for row in health_rows:
        status = row.get("status") or "unknown"
        if status not in router_status:
            status = "unknown"
        router_status[status] += 1
        freshness_key, _ = _freshness_label(row.get("collected_raw"), now=now)
        if freshness_key == "fresh":
            fresh_count += 1
        else:
            stale_count += 1

    tunnel_status = {"up": 0, "warning": 0, "down": 0, "unknown": 0}
    for row in tunnel_rows:
        status = row.get("status_key") or "unknown"
        if status not in tunnel_status:
            status = "unknown"
        tunnel_status[status] += 1

    total_devices = len(devices)
    total_tunnels = len(tunnel_rows)
    auto_ready = sum(1 for device in devices if _device_has_auto_snmp(device))
    action_items = _build_action_items(devices, health_rows, tunnel_rows)
    critical_count = sum(1 for item in action_items if item.get("severity") == "critical")
    warning_count = sum(1 for item in action_items if item.get("severity") == "warning")

    if critical_count:
        overall_status = "critical"
        overall_label = "Critical"
        focus_text = "مشکل مهم وجود دارد؛ اول Critical Items را بررسی کن."
    elif warning_count:
        overall_status = "warning"
        overall_label = "Warning"
        focus_text = "چند مورد نیازمند بررسی وجود دارد."
    elif total_devices and router_status["up"] == total_devices:
        overall_status = "up"
        overall_label = "Healthy"
        focus_text = "همه Router های شناخته‌شده وضعیت سالم دارند."
    else:
        overall_status = "unknown"
        overall_label = "Needs baseline"
        focus_text = "برای بعضی Router ها هنوز داده قابل تصمیم‌گیری کافی نیست."

    router_chart = [
        {"label": "Up", "key": "up", "count": router_status["up"], "pct": _percent(router_status["up"], total_devices), "class": "up"},
        {"label": "Warning", "key": "warning", "count": router_status["warning"], "pct": _percent(router_status["warning"], total_devices), "class": "warning"},
        {"label": "Down", "key": "down", "count": router_status["down"], "pct": _percent(router_status["down"], total_devices), "class": "down"},
        {"label": "Unknown", "key": "unknown", "count": router_status["unknown"], "pct": _percent(router_status["unknown"], total_devices), "class": "unknown"},
    ]
    tunnel_chart = [
        {"label": "Up", "key": "up", "count": tunnel_status["up"], "pct": _percent(tunnel_status["up"], total_tunnels), "class": "up"},
        {"label": "Warning", "key": "warning", "count": tunnel_status["warning"], "pct": _percent(tunnel_status["warning"], total_tunnels), "class": "warning"},
        {"label": "Down", "key": "down", "count": tunnel_status["down"], "pct": _percent(tunnel_status["down"], total_tunnels), "class": "down"},
        {"label": "Unknown", "key": "unknown", "count": tunnel_status["unknown"], "pct": _percent(tunnel_status["unknown"], total_tunnels), "class": "unknown"},
    ]

    return {
        "overall_status": overall_status,
        "overall_label": overall_label,
        "focus_text": focus_text,
        "total_devices": total_devices,
        "auto_ready": auto_ready,
        "auto_ready_pct": _percent(auto_ready, total_devices),
        "fresh_count": fresh_count,
        "stale_count": stale_count,
        "fresh_pct": _percent(fresh_count, total_devices),
        "router_status": router_status,
        "tunnel_status": tunnel_status,
        "router_chart": router_chart,
        "tunnel_chart": tunnel_chart,
        "total_tunnels": total_tunnels,
        "action_items": action_items,
        "action_count": len(action_items),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "auto_poll_command": "python manage.py poll_mikrotik_auto_snmp",
        "auto_task_name": "SwitchMap MikroTik Auto SNMP Poll",
    }



def _age_text(value, now=None) -> str:
    if not value:
        return "ثبت نشده"
    now = now or timezone.now()
    try:
        delta = now - value
        minutes = max(0, int(delta.total_seconds() // 60))
    except Exception:
        return "نامشخص"
    if minutes < 1:
        return "کمتر از یک دقیقه قبل"
    if minutes < 60:
        return f"{minutes} دقیقه قبل"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت قبل"
    days = hours // 24
    return f"{days} روز قبل"


def _short_snmp_error(error: str) -> str:
    text = str(error or "").strip()
    if not text:
        return "-"
    low = text.lower()
    if "timed out" in low or "timeout" in low or "unreachable" in low:
        return "SNMP پاسخ نمی‌دهد یا مسیر UDP 161 بسته است."
    if "authentication" in low or "community" in low:
        return "Community یا تنظیمات SNMP معتبر نیست."
    if "no such" in low:
        return "OID مورد انتظار پاسخ معتبر نداده است."
    if len(text) > 140:
        return text[:137] + "..."
    return text


def _device_monitoring_insight(device: dict, now=None) -> dict:
    now = now or timezone.now()
    switch = device["switch"]
    pollable = _device_has_auto_snmp(device)
    last_poll = getattr(switch, "snmp_last_poll", None)
    error = (getattr(switch, "snmp_last_error", "") or "").strip()
    fresh_limit = now - timedelta(minutes=30)
    is_stale = not last_poll or last_poll < fresh_limit
    snmp_port = getattr(switch, "snmp_port", 161)
    ip = str(getattr(switch, "management_ip", "") or "")

    if not pollable:
        state = "not_monitored"
        severity = "info"
        status_title = "خارج از پوشش خودکار"
        result = "این دستگاه در جمع‌آوری خودکار SNMP لحاظ نمی‌شود."
        recommended = "اگر باید مانیتور شود، SNMP Read Only و Community را در SwitchMap کامل کن؛ اگر عمدی است، نادیده بگیر."
        action_summary = "خارج از پوشش Auto SNMP است."
        priority = 40
    elif is_stale:
        state = "stale"
        severity = "warning"
        status_title = "داده قدیمی"
        result = "آخرین بررسی تازه نیست؛ نتیجه این دستگاه برای تصمیم‌گیری معتبر نیست."
        recommended = "وضعیت Scheduled Task و لاگ Auto SNMP Poll را بررسی کن."
        action_summary = "داده تازه ندارد."
        priority = 20
    elif error:
        state = "failed"
        severity = "warning"
        status_title = "مانیتورینگ بی‌پاسخ"
        result = _short_snmp_error(error)
        recommended = f"اگر دستگاه روشن است، دسترسی SNMP از VM به {ip}:{snmp_port}، Community و Firewall را بررسی کن؛ اگر خاموش است، فعلاً زمان نگذار."
        action_summary = "SNMP پاسخ نمی‌دهد؛ احتمال خاموش بودن یا بسته بودن UDP 161 وجود دارد."
        priority = 10
    else:
        state = "healthy"
        severity = "ok"
        status_title = "قابل اتکا"
        result = "آخرین بررسی خودکار تازه و بدون خطا است."
        recommended = "اقدامی لازم نیست."
        action_summary = "سالم و قابل اتکا است."
        priority = 90

    return {
        "switch": switch,
        "device": device,
        "name": switch.name,
        "ip": ip,
        "role": device.get("role_label", "RouterOS Device"),
        "site": device.get("site", "-"),
        "state": state,
        "severity": severity,
        "status_title": status_title,
        "result": result,
        "recommended_action": recommended,
        "action_summary": action_summary,
        "last_poll": last_poll,
        "last_poll_text": _time_text(last_poll),
        "age_text": _age_text(last_poll, now=now),
        "snmp_port": snmp_port,
        "pollable": pollable,
        "priority": priority,
        "url": _switch_detail_url(switch),
    }

def _count_state(rows: list[dict], state: str) -> int:
    return sum(1 for row in rows if row.get("state") == state)


def _plural_fa(count: int, label: str) -> str:
    return f"{count} {label}"


def _build_insight_dashboard(devices: list[dict], foundation: dict) -> dict:
    # Phase 61/62 markers: Data Reliability, Network Health, Recommended Action, Auto Data Collection
    now = timezone.now()
    insights = [_device_monitoring_insight(device, now=now) for device in devices]
    total = len(insights)
    healthy = _count_state(insights, "healthy")
    failed = _count_state(insights, "failed")
    stale = _count_state(insights, "stale")
    not_monitored = _count_state(insights, "not_monitored")
    pollable = total - not_monitored

    reliability_pct = _percent(healthy, total)
    coverage_pct = _percent(pollable, total)

    if failed:
        overall_state = "warning" if failed <= max(2, total // 4) else "critical"
        headline = f"{failed} دستگاه پاسخ مانیتورینگ نمی‌دهند"
        conclusion = "این الزاماً خرابی شبکه نیست؛ ممکن است دستگاه خاموش باشد. فقط اگر دستگاه باید روشن باشد، مسیر SNMP و UDP 161 را بررسی کن."
        primary_next = "اول فقط دستگاه‌هایی را بررسی کن که باید روشن و در دسترس باشند."
    elif stale:
        overall_state = "warning"
        headline = f"{stale} دستگاه داده تازه ندارند"
        conclusion = "جمع‌آوری خودکار باید اجرا شود؛ نتیجه قدیمی برای تصمیم‌گیری قابل اتکا نیست."
        primary_next = "Scheduled Task و لاگ Auto Poll را بررسی کن."
    elif not_monitored and healthy:
        overall_state = "info"
        headline = "دستگاه‌های تحت پوشش سالم هستند"
        conclusion = f"{not_monitored} دستگاه خارج از پوشش خودکار است و در نتیجه سلامت لحاظ نشده است."
        primary_next = "اگر آن دستگاه‌ها مهم هستند، SNMP Read Only را برایشان کامل کن."
    elif total and healthy == total:
        overall_state = "healthy"
        headline = "شبکه MikroTik در وضعیت قابل اتکا است"
        conclusion = "همه دستگاه‌های شناسایی‌شده داده تازه و بدون خطا دارند."
        primary_next = "اقدام فوری لازم نیست."
    else:
        overall_state = "unknown"
        headline = "داده کافی برای تحلیل وجود ندارد"
        conclusion = "اول Inventory، SNMP Read Only و Auto Poll را کامل کن."
        primary_next = "پوشش مانیتورینگ را کامل کن."

    state_cards = [
        {"key": "healthy", "label": "قابل اتکا", "count": healthy, "hint": "داده تازه و بدون خطا", "class": "healthy", "pct": _percent(healthy, total)},
        {"key": "failed", "label": "بی‌پاسخ", "count": failed, "hint": "SNMP جواب نداده", "class": "failed", "pct": _percent(failed, total)},
        {"key": "stale", "label": "قدیمی", "count": stale, "hint": "Poll تازه نیست", "class": "stale", "pct": _percent(stale, total)},
        {"key": "not_monitored", "label": "خارج از پوشش", "count": not_monitored, "hint": "SNMP تعریف نشده", "class": "not-monitored", "pct": _percent(not_monitored, total)},
    ]

    action_items = [row for row in insights if row["state"] in {"failed", "stale"}]
    # Not monitored devices are lower priority; do not mix them with actual failures unless they are routers.
    action_items.extend(row for row in insights if row["state"] == "not_monitored" and row["device"].get("is_router"))
    action_items.sort(key=lambda row: (row["priority"], row["name"]))

    blocking_items = [row for row in action_items if row["state"] in {"failed", "stale"}]
    low_priority_items = [row for row in action_items if row["state"] == "not_monitored"]

    tunnel_rows = foundation.get("tunnel_rows", [])
    tunnel_total = len(tunnel_rows)
    tunnel_unknown = sum(1 for row in tunnel_rows if (row.get("status_key") or "unknown") == "unknown")
    tunnel_down = sum(1 for row in tunnel_rows if (row.get("status_key") or "") == "down")
    tunnel_up = sum(1 for row in tunnel_rows if (row.get("status_key") or "") == "up")
    tunnel_live_ready = bool(tunnel_total and (tunnel_up or tunnel_down) and tunnel_unknown < tunnel_total)
    if not tunnel_total:
        tunnel_conclusion = "Tunnel مدل‌شده‌ای برای تحلیل وجود ندارد."
    elif not tunnel_live_ready:
        tunnel_conclusion = "Tunnel هنوز منبع Live قابل اتکا ندارد؛ در تصمیم روزمره استفاده نشود."
    else:
        tunnel_conclusion = f"از {tunnel_total} Tunnel مدل‌شده، {tunnel_up} مورد Up و {tunnel_down} مورد Down ثبت شده است."

    return {
        "overall_state": overall_state,
        "headline": headline,
        "conclusion": conclusion,
        "primary_next": primary_next,
        "total_devices": total,
        "healthy_count": healthy,
        "failed_count": failed,
        "stale_count": stale,
        "not_monitored_count": not_monitored,
        "pollable_count": pollable,
        "reliability_pct": reliability_pct,
        "coverage_pct": coverage_pct,
        "state_cards": state_cards,
        "device_insights": insights,
        "action_items": action_items[:8],
        "blocking_items": blocking_items[:5],
        "low_priority_items": low_priority_items[:5],
        "action_count": len(blocking_items),
        "primary_result": f"{healthy} از {total} دستگاه داده قابل اتکا دارند" if total else "داده‌ای ثبت نشده است",
        "coverage_result": f"{pollable} از {total} دستگاه تحت پوشش Auto SNMP هستند" if total else "پوشش مانیتورینگ تعریف نشده است",
        "last_generated": _time_text(now),
        "tunnel_total": tunnel_total,
        "tunnel_unknown": tunnel_unknown,
        "tunnel_live_ready": tunnel_live_ready,
        "tunnel_conclusion": tunnel_conclusion,
        "dashboard_mode": "automatic_insight",
        "auto_refresh_seconds": 60,
    }

def _foundation_payload(devices: list[dict], fallback_relationships: list[dict], fallback_policies: list[dict]) -> dict:
    tunnels = list(
        RouterTunnel.objects.filter(is_active=True)
        .select_related("source_switch", "destination_switch", "source_site", "destination_site")
        .order_by("failover_priority", "name")
    )
    tunnels = [
        tunnel for tunnel in tunnels
        if not _is_switchmap_test_device(tunnel.source_switch)
        and not _is_switchmap_test_device(tunnel.destination_switch)
    ]
    wan_links = list(
        WanLink.objects.filter(is_active=True)
        .select_related("switch", "site")
        .order_by("site__name", "switch__name", "name")
    )
    wan_links = [wan for wan in wan_links if not _is_switchmap_test_device(wan.switch)]
    routing_policies = list(
        RoutingPolicy.objects.filter(is_active=True)
        .select_related("switch", "site")
        .order_by("site__name", "switch__name", "policy_type", "name")
    )
    routing_policies = [policy for policy in routing_policies if not _is_switchmap_test_device(policy.switch)]
    sites = list(Site.objects.filter(is_active=True).order_by("kind", "name"))
    latest_health = _latest_health_by_switch()

    tunnel_rows = []
    for tunnel in tunnels:
        tunnel_rows.append(
            {
                "source": _switch_label(tunnel.source_switch, tunnel.source_site.name if tunnel.source_site else "-"),
                "destination": _switch_label(tunnel.destination_switch, tunnel.destination_site.name if tunnel.destination_site else "-"),
                "destination_switch": tunnel.destination_switch,
                "type": tunnel.get_tunnel_type_display(),
                "local_ip": _ip_text(tunnel.local_tunnel_ip),
                "remote_ip": _ip_text(tunnel.remote_tunnel_ip),
                "routed_networks": tunnel.routed_networks or "-",
                "status_key": tunnel.status,
                "status_label": tunnel.get_status_display(),
                "confidence": tunnel.confidence,
                "priority": tunnel.failover_priority,
                "notes": tunnel.notes,
            }
        )

    if not tunnel_rows:
        for relation in fallback_relationships:
            tunnel_rows.append(
                {
                    "source": relation["hub"]["switch"].name,
                    "destination": relation["device"]["switch"].name,
                    "destination_switch": relation["device"]["switch"],
                    "type": relation["tunnel_type"],
                    "local_ip": relation["local_ip"],
                    "remote_ip": relation["remote_ip"],
                    "routed_networks": relation["routed_networks"],
                    "status_key": relation["status_key"],
                    "status_label": relation["status_label"],
                    "confidence": relation["confidence"],
                    "priority": "-",
                    "notes": relation["policy_hint"],
                }
            )

    policy_rows = []
    for policy in routing_policies:
        policy_rows.append(
            {
                "device": {"switch": policy.switch} if policy.switch else None,
                "switch": policy.switch,
                "name": policy.name,
                "site": policy.site.name if policy.site else "-",
                "wan": policy.preferred_path or "-",
                "tunnel": policy.get_policy_type_display(),
                "routed_networks": " → ".join(item for item in [policy.source_zone, policy.destination_zone] if item) or "-",
                "policy_hint": policy.description or policy.preferred_path or "-",
                "confidence": policy.confidence,
                "backup_path": policy.backup_path or "-",
                "routing_table": policy.routing_table or "-",
                "address_list": policy.address_list or "-",
            }
        )

    if not policy_rows:
        policy_rows = fallback_policies

    health_rows = []
    for device in devices:
        switch = device["switch"]
        latest = latest_health.get(switch.id)
        if latest:
            health_rows.append(
                {
                    "device": device,
                    "snapshot": latest,
                    "collected_raw": latest.collected_at,
                    "status": latest.status,
                    "status_label": latest.get_status_display(),
                    "source": latest.get_source_display(),
                    "collected_at": _time_text(latest.collected_at),
                    "cpu": latest.cpu_load if latest.cpu_load is not None else "-",
                    "memory": latest.memory_free_mb if latest.memory_free_mb is not None else "-",
                    "version": latest.routeros_version or "-",
                    "tunnels": latest.tunnel_count,
                    "active_tunnels": latest.active_tunnel_count,
                }
            )
        else:
            health_rows.append(
                {
                    "device": device,
                    "snapshot": None,
                    "collected_raw": None,
                    "status": device["health_key"],
                    "status_label": device["health_label"],
                    "source": "SwitchMap metadata",
                    "collected_at": device["last_poll_text"],
                    "cpu": "-",
                    "memory": "-",
                    "version": "-",
                    "tunnels": device["port_summary"].get("tunnels", 0),
                    "active_tunnels": 0,
                }
            )

    return {
        "sites": sites,
        "wan_links": wan_links,
        "tunnel_rows": tunnel_rows,
        "policy_rows": policy_rows,
        "health_rows": health_rows,
        "foundation_counts": {
            "sites": len(sites),
            "wan_links": len(wan_links),
            "tunnels": len(tunnels),
            "routing_policies": len(routing_policies),
            "health_snapshots": len(latest_health),
        },
        "foundation_active": bool(sites or tunnels or wan_links or routing_policies),
    }


def _switch_detail_url(switch: Switch | None) -> str:
    if not switch:
        return ""
    try:
        return reverse("inventory:switch_detail", args=[switch.id])
    except Exception:
        return ""


def _build_review_items(devices: list[dict], tunnel_rows: list[dict], wan_links: list[WanLink], policy_rows: list[dict]) -> list[dict]:
    items = []
    for device in devices:
        switch = device["switch"]
        if device["health_key"] in {"unknown", "warning", "down"}:
            items.append({
                "severity": "warning" if device["health_key"] != "down" else "critical",
                "title": f"{switch.name}: live health needs review",
                "message": f"Status is {device['health_label']}; enable a real live poll phase before operational decisions.",
                "target": switch.name,
                "url": _switch_detail_url(switch),
            })
        if device["port_summary"].get("visible", 0) == 0 and device["role_key"] != "remote_router":
            items.append({
                "severity": "info",
                "title": f"{switch.name}: no visible RouterOS interfaces",
                "message": "No visible interface data is mapped for this RouterOS device.",
                "target": switch.name,
                "url": _switch_detail_url(switch),
            })
        if switch.needs_review or device["hint"].confidence == "needs_review":
            items.append({
                "severity": "warning",
                "title": f"{switch.name}: inventory classification needs review",
                "message": "Role, site, tunnel or WAN metadata should be checked.",
                "target": switch.name,
                "url": _switch_detail_url(switch),
            })

    for tunnel in tunnel_rows:
        if tunnel.get("confidence") != "documented" or tunnel.get("status_key") in {"unknown", "warning", "down"}:
            items.append({
                "severity": "warning" if tunnel.get("status_key") != "down" else "critical",
                "title": f"Tunnel: {tunnel.get('source', '-')} → {tunnel.get('destination', '-')}",
                "message": f"{tunnel.get('type', '-')} is {tunnel.get('status_label', '-')}; confidence={tunnel.get('confidence', '-')}",
                "target": tunnel.get("destination", "-"),
                "url": _switch_detail_url(tunnel.get("destination_switch")),
            })

    for wan in wan_links:
        if not wan.switch_id or not wan.site_id:
            items.append({
                "severity": "warning",
                "title": f"WAN link needs mapping: {wan.name}",
                "message": "WAN/Transit row is missing device or site relation.",
                "target": wan.name,
                "url": _switch_detail_url(wan.switch),
            })

    if not policy_rows:
        items.append({
            "severity": "info",
            "title": "No routing policy rows",
            "message": "Routing policy baseline is empty or filtered out.",
            "target": "Routing Policy",
            "url": "",
        })

    return items[:30]




def _serialize_live_poll_row(row: dict | None) -> dict:
    if not row:
        return {}
    return {
        "device": row.get("device_name"),
        "ip": row.get("device_ip"),
        "status": row.get("status"),
        "status_label": row.get("status_label"),
        "collected_at": row.get("collected_at"),
        "cpu": row.get("cpu"),
        "memory_free_mb": row.get("memory"),
        "uptime": row.get("uptime"),
        "routeros_version": row.get("version"),
        "tunnels": row.get("tunnels"),
        "active_tunnels": row.get("active_tunnels"),
        "tunnel_ratio": row.get("tunnel_ratio"),
        "message": row.get("message"),
        "url": row.get("url"),
    }



def _json_safe_mikrotik_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return timezone.localtime(value).isoformat()
        except Exception:
            try:
                return value.isoformat()
            except Exception:
                return str(value)
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if key in {"switch", "device"}:
                continue
            clean[str(key)] = _json_safe_mikrotik_value(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_mikrotik_value(item) for item in value]
    if hasattr(value, "_meta") and hasattr(value, "pk"):
        label = getattr(value, "name", None) or str(value)
        return {"id": value.pk, "label": str(label)}
    return str(value)


def _serialize_insight_row(row: dict) -> dict:
    return {
        "name": row.get("name"),
        "ip": row.get("ip"),
        "site": row.get("site"),
        "role": row.get("role"),
        "state": row.get("state"),
        "severity": row.get("severity"),
        "status_title": row.get("status_title"),
        "result": row.get("result"),
        "recommended_action": row.get("recommended_action"),
        "action_summary": row.get("action_summary"),
        "last_poll": row.get("last_poll_text"),
        "age": row.get("age_text"),
        "snmp_port": row.get("snmp_port"),
        "pollable": row.get("pollable"),
        "priority": row.get("priority"),
        "url": row.get("url"),
    }


def _serialize_insight_dashboard_for_json(insight: dict) -> dict:
    if not isinstance(insight, dict):
        return {}
    clean = _json_safe_mikrotik_value(insight)
    clean["device_insights"] = [
        _serialize_insight_row(row)
        for row in insight.get("device_insights", [])
        if isinstance(row, dict)
    ]
    clean["action_items"] = [
        _serialize_insight_row(row)
        for row in insight.get("action_items", [])
        if isinstance(row, dict)
    ]
    clean["blocking_items"] = [
        _serialize_insight_row(row)
        for row in insight.get("blocking_items", [])
        if isinstance(row, dict)
    ]
    clean["low_priority_items"] = [
        _serialize_insight_row(row)
        for row in insight.get("low_priority_items", [])
        if isinstance(row, dict)
    ]
    return clean

def _serialize_mikrotik_payload(payload: dict) -> dict:
    return {
        "generated_at": timezone.localtime(timezone.now()).isoformat(),
        "counts": {
            "devices": payload.get("device_count", 0),
            "relationships": payload.get("relationship_count", 0),
            "documented_relationships": payload.get("documented_relationship_count", 0),
            "needs_review": payload.get("needs_review_count", 0),
            **payload.get("foundation_counts", {}),
            "live_ssh_polls": payload.get("live_poll_count", 0),
        },
        "devices": [
            {
                "id": device["switch"].id,
                "name": device["switch"].name,
                "ip": str(device["switch"].management_ip),
                "winbox_port": device["switch"].winbox_port,
                "ssh_port": device["switch"].ssh_port,
                "role": device["role_label"],
                "role_key": device["role_key"],
                "site": device["site"],
                "health": device["health_key"],
                "health_label": device["health_label"],
                "url": _switch_detail_url(device["switch"]),
            }
            for device in payload.get("devices", [])
        ],
        "tunnels": [
            {
                "source": row.get("source"),
                "destination": row.get("destination"),
                "type": row.get("type"),
                "local_ip": row.get("local_ip"),
                "remote_ip": row.get("remote_ip"),
                "routed_networks": row.get("routed_networks"),
                "status": row.get("status_key"),
                "status_label": row.get("status_label"),
                "confidence": row.get("confidence"),
            }
            for row in payload.get("tunnel_rows", [])
        ],
        "wan_links": [
            {
                "name": wan.name,
                "device": wan.switch.name if wan.switch else "",
                "site": wan.site.name if wan.site else "",
                "type": wan.get_link_type_display(),
                "provider": wan.provider,
                "interface": wan.interface_name,
                "purpose": wan.purpose,
            }
            for wan in payload.get("wan_links", [])
        ],
        "latest_live_poll": _serialize_live_poll_row(payload.get("latest_live_poll_result")),
        "latest_live_poll_rows": [
            _serialize_live_poll_row(row) for row in payload.get("latest_live_poll_rows", [])
        ],
        "monitoring_summary": payload.get("monitoring_summary", {}),
        "insight_dashboard": _serialize_insight_dashboard_for_json(payload.get("insight_dashboard", {})),
        "device_insights": [
            {
                "name": row.get("name"),
                "ip": row.get("ip"),
                "site": row.get("site"),
                "state": row.get("state"),
                "status_title": row.get("status_title"),
                "result": row.get("result"),
                "recommended_action": row.get("recommended_action"),
                "last_poll": row.get("last_poll_text"),
                "age": row.get("age_text"),
                "url": row.get("url"),
            }
            for row in payload.get("insight_dashboard", {}).get("device_insights", [])
        ],
        "action_items": _json_safe_mikrotik_value(payload.get("action_items", [])),
        "auto_snmp": {
            "task_name": payload.get("monitoring_summary", {}).get("auto_task_name"),
            "command": payload.get("monitoring_summary", {}).get("auto_poll_command"),
            "ready_devices": payload.get("monitoring_summary", {}).get("auto_ready"),
            "total_devices": payload.get("monitoring_summary", {}).get("total_devices"),
        },
        "review_items": payload.get("review_items", []),
    }


def _build_mikrotik_payload() -> dict:
    switches = list(
        Switch.objects.filter(is_active=True)
        .prefetch_related(VISIBLE_PORT_PREFETCH)
        .order_by("topology_position", "name")
    )
    mikrotik_switches = [switch for switch in switches if _is_mikrotik_candidate(switch)]
    devices = [_device_payload(switch) for switch in mikrotik_switches]
    devices.sort(key=lambda item: (item["role_key"] != "core_router", item["site"], item["switch"].topology_position, item["switch"].name))
    hub = _find_hub(devices)
    relationships = _build_relationships(devices, hub)

    role_groups = []
    for key, title in [
        ("core_router", "Core Router"),
        ("edge_router", "Edge / Transit"),
        ("remote_router", "Remote Routers"),
        ("access_point", "AP / CAP"),
        ("routeros_switch", "RouterOS Switch"),
        ("routeros_device", "Needs Review"),
    ]:
        items = [device for device in devices if device["role_key"] == key]
        role_groups.append({"key": key, "title": title, "items": items, "count": len(items)})

    health_counts = {
        "up": sum(1 for device in devices if device["health_key"] == "up"),
        "warning": sum(1 for device in devices if device["health_key"] == "warning"),
        "down": sum(1 for device in devices if device["health_key"] == "down"),
        "unknown": sum(1 for device in devices if device["health_key"] == "unknown"),
    }

    fallback_policies = _routing_policies(devices)
    foundation = _foundation_payload(devices, relationships, fallback_policies)

    review_items = _build_review_items(
        devices=devices,
        tunnel_rows=foundation["tunnel_rows"],
        wan_links=foundation["wan_links"],
        policy_rows=foundation["policy_rows"],
    )
    live_poll_meta = _live_poll_meta()
    latest_live_poll_rows = _latest_live_poll_rows()
    monitoring_summary = _build_monitoring_summary(devices, foundation, latest_live_poll_rows)
    insight_dashboard = _build_insight_dashboard(devices, foundation)

    return {
        "devices": devices,
        "hub": hub,
        "relationships": relationships,
        "role_groups": role_groups,
        "routing_policies": foundation["policy_rows"],
        "tunnel_rows": foundation["tunnel_rows"],
        "health_rows": foundation["health_rows"],
        "sites": foundation["sites"],
        "wan_links": foundation["wan_links"],
        "foundation_counts": foundation["foundation_counts"],
        "foundation_active": foundation["foundation_active"],
        "review_items": review_items,
        "live_poll_candidates": _live_poll_candidates(devices),
        "live_poll_count": live_poll_meta["live_poll_count"],
        "latest_live_poll": live_poll_meta["latest_live_poll"],
        "latest_live_poll_text": live_poll_meta["latest_live_poll_text"],
        "latest_live_poll_rows": latest_live_poll_rows,
        "latest_live_poll_result": latest_live_poll_rows[0] if latest_live_poll_rows else None,
        "monitoring_summary": monitoring_summary,
        "insight_dashboard": insight_dashboard,
        "action_items": insight_dashboard["action_items"],
        "data_endpoint_name": "inventory:mikrotik_center_data",
        "data_generated_at": _time_text(timezone.now()),
        "device_count": len(devices),
        "relationship_count": len(foundation["tunnel_rows"]),
        "documented_relationship_count": sum(1 for item in foundation["tunnel_rows"] if item["confidence"] == "documented"),
        "needs_review_count": sum(1 for device in devices if device["hint"].confidence == "needs_review" or device["switch"].needs_review),
        "health_counts": health_counts,
    }


def mikrotik_center_view(request):
    payload = _build_mikrotik_payload()
    return render(request, "inventory/mikrotik_center.html", payload)


def mikrotik_center_data_view(request):
    payload = _build_mikrotik_payload()
    return JsonResponse(_serialize_mikrotik_payload(payload))


@require_POST
def mikrotik_auto_snmp_poll_view(request):
    try:
        call_command("poll_mikrotik_auto_snmp", quiet=True)
        messages.success(request, "Auto SNMP Poll اجرا شد. صفحه فقط داده‌های Read Only را خلاصه می‌کند.")
    except Exception as exc:
        messages.error(request, f"Auto SNMP Poll خطا داد: {exc}")
    return redirect("inventory:mikrotik_center")


@require_POST
def mikrotik_live_poll_view(request):
    switch_id = request.POST.get("switch_id")
    username = (request.POST.get("ssh_username") or "").strip()
    password = request.POST.get("ssh_password") or ""
    try:
        timeout = int(request.POST.get("timeout") or 12)
    except (TypeError, ValueError):
        timeout = 12
    timeout = max(5, min(timeout, 30))

    switch = get_object_or_404(Switch, pk=switch_id, is_active=True)
    if not _is_mikrotik_candidate(switch):
        messages.error(request, "این دستگاه در MikroTik Center قابل Poll نیست.")
        return redirect("inventory:mikrotik_center")

    result: RouterOSLivePollResult = poll_routeros_health_ssh(
        switch=switch,
        username=username,
        password=password,
        timeout=timeout,
    )
    if result.ok:
        messages.success(
            request,
            f"Health Check موفق بود: {switch.name} | RouterOS={result.routeros_version or '-'} | Uptime={result.uptime or '-'} | CPU={result.cpu_load if result.cpu_load is not None else '-'}% | RAM={result.memory_free_mb if result.memory_free_mb is not None else '-'} MB | Tunnel={result.active_tunnel_count}/{result.tunnel_count}",
        )
    else:
        messages.error(request, f"Health Check ناموفق بود: {switch.name} | {result.message}")
    return redirect("inventory:mikrotik_center")
