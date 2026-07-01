import re
import csv
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

IRAN_TZ = ZoneInfo("Asia/Tehran")

from .forms import PortForm, SSHPortActionForm, SwitchBulkImportForm, SwitchForm, UserCreateForm, UserPasswordForm, UserUpdateForm
from .access_control import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEW_ONLY, can_admin_panel, can_edit_port, can_refresh, can_run_ssh, can_run_ssh_action, user_role
from .models import AlarmNotification, CiscoSyslogEntry, Port, PortActionLog, PortDocumentationHistory, SfpMonitorSnapshot, Switch, SystemAuditLog
from .phase79_history import latest_port_connection, history_has_identity_data
from .endpoint_display_policy import classify_port_connection_display, port_visual_display_fields
from .alarm_rules import AlarmCandidate, evaluate_alarm_candidates, sfp_alarm_details, sfp_rule_key_for_tag, sfp_severity_for_tag
from .alarm_policy import alarm_is_false_positive, is_actionable_interface_down, sfp_issue_labels_from_values as policy_sfp_issue_labels_from_values
from .topology_engine import classify_edge, edge_warning_allowed, topology_alarm_should_exist
from .ssh_tools import (
    SshActionError,
    action_label,
    action_requires_confirmation,
    action_requires_force,
    action_risk_text,
    build_port_commands,
    run_port_action,
    run_port_multi_actions,
    run_bulk_port_actions,
    run_switch_show_commands,
)
from .snmp_tools import (
    SnmpError,
    is_access_panel_interface,
    is_legacy_gi_sfp_interface,
    is_uplink_interface,
    is_visible_switchmap_interface,
    poll_switch_discovery,
    poll_switch_ports,
    sync_missing_snmp_ports,
    test_snmp_connection,
)


User = get_user_model()


VISIBLE_PORT_PREFETCH = Prefetch(
    "ports",
    # select_related("switch") back-fills the FK cache so the per-port visual
    # display policy (which reads switch role/family for AP context) does not
    # trigger an N+1 query per rendered port button.
    queryset=Port.objects.select_related("switch").order_by("display_order", "interface_name"),
)


def _visible_ports_for_switch(switch):
    return [
        port
        for port in list(switch.ports.all())
        if is_visible_switchmap_interface(port.interface_name)
    ]


def _apply_dashboard_port_groups(switch):
    ordered_ports = list(switch.ports.all())
    visible_ports = [
        port for port in ordered_ports
        if is_visible_switchmap_interface(port.interface_name)
    ]
    access_ports = [
        port for port in visible_ports
        if is_access_panel_interface(port.interface_name)
    ]
    uplink_ports = [
        port for port in visible_ports
        if is_uplink_interface(port.interface_name)
    ]

    switch.dashboard_top_ports = access_ports[0::2]
    switch.dashboard_bottom_ports = access_ports[1::2]
    switch.dashboard_uplink_ports = uplink_ports[:4]
    switch.dashboard_visible_ports = len(visible_ports)
    switch.dashboard_uplink_count = len(uplink_ports)
    switch.dashboard_trunk_count = sum(
        1 for port in visible_ports
        if port.port_mode == Port.PortMode.TRUNK
    )
    switch.dashboard_neighbor_count = sum(
        1 for port in visible_ports if port.neighbor_device
    )
    switch.dashboard_poe_count = sum(
        1 for port in visible_ports if port.poe_enabled
    )



def _phase79_empty_last_connection_payload():
    return {
        "available": False,
        "identity": "سابقه‌ای ثبت نشده",
        "event_type": "-",
        "observed_at_text": "-",
        "last_verified_at_text": "-",
        "neighbor": "-",
        "neighbor_source": "-",
        "mac": "-",
        "ip": "-",
        "vlan": "-",
        "status_after": "-",
        "source": "-",
        "classification": "no_current_evidence",
        "display_label": "",
        "display_source": "",
        "direct": False,
        "confidence": 0,
        "reason": "No current connected-device evidence is available.",
        "raw_evidence": {},
    }


def _phase79_clean_identity(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value in ("", "-", "None", "none", "null", "Null", "NULL"):
        return ""
    if value.lower() in ("unknown", "نامشخص"):
        return ""
    return value


def _phase79_first_mac(value):
    value = _phase79_clean_identity(value)
    if not value:
        return ""
    for part in re.split(r"[\s,;]+", value):
        part = _phase79_clean_identity(part)
        if part:
            return part
    return ""


def _phase79_neighbor_label(device, port):
    return " / ".join(filter(None, [
        _phase79_clean_identity(device),
        _phase79_clean_identity(port),
    ]))


def _phase79_current_connection_payload(port):
    if not port:
        return _phase79_empty_last_connection_payload()
    display = classify_port_connection_display(port)
    if not display.get("available"):
        return _phase79_empty_last_connection_payload()
    observed_at = getattr(port, "discovery_last_poll", None) or getattr(port, "snmp_last_poll", None) or getattr(port, "updated_at", None)
    status_after = getattr(port, "status", "") or ""
    event_type = "Current" if str(status_after).lower() == "up" else "Last known"
    return {
        "available": True,
        "identity": display["display_label"],
        "event_type": event_type,
        "observed_at_text": _dt_text(observed_at),
        "last_verified_at_text": _dt_text(observed_at),
        "neighbor": display["raw_evidence"].get("neighbor") or "-",
        "neighbor_source": _phase79_clean_identity(getattr(port, "neighbor_source", "")) or "-",
        "mac": display["display_mac"] or "-",
        "ip": display["display_ip"] or "-",
        "vlan": display["display_vlan"] or "-",
        "status_after": status_after or "-",
        "source": display["display_source"] or "-",
        "classification": display["classification"],
        "display_label": display["display_label"],
        "display_source": display["display_source"],
        "direct": display["direct"],
        "confidence": display["confidence"],
        "reason": display["reason"],
        "raw_evidence": display["raw_evidence"],
    }


def _phase79_history_payload(history):
    if not history:
        return _phase79_empty_last_connection_payload()
    display = classify_port_connection_display(history)
    if not display.get("available"):
        return _phase79_empty_last_connection_payload()
    return {
        "available": True,
        "identity": display["display_label"],
        "event_type": history.get_event_type_display() if hasattr(history, "get_event_type_display") else _phase79_clean_identity(getattr(history, "event_type", "")) or "-",
        "observed_at_text": _dt_text(getattr(history, "observed_at", None)),
        "last_verified_at_text": _dt_text(getattr(history, "last_verified_at", None)),
        "neighbor": display["raw_evidence"].get("neighbor") or "-",
        "neighbor_source": _phase79_clean_identity(getattr(history, "neighbor_source", "")) or "-",
        "mac": display["display_mac"] or "-",
        "ip": display["display_ip"] or "-",
        "vlan": display["display_vlan"] or "-",
        "status_after": _phase79_clean_identity(getattr(history, "status_after", "")) or "-",
        "source": display["display_source"] or _phase79_clean_identity(getattr(history, "source", "")) or "-",
        "classification": display["classification"],
        "display_label": display["display_label"],
        "display_source": display["display_source"],
        "direct": display["direct"],
        "confidence": display["confidence"],
        "reason": display["reason"],
        "raw_evidence": display["raw_evidence"],
    }


def _phase79_effective_last_connection_payload(port):
    current = _phase79_current_connection_payload(port)
    if current.get("available"):
        return current
    return _phase79_history_payload(latest_port_connection(port))


def _port_payload(port):
    if not port:
        return {}

    # PHASE114 FINAL: the top-level visual fields (device/ip/mac/neighbor/
    # neighbor_source) are produced by the single deterministic display policy
    # so the upper Modal/Detail fields can no longer disagree with the lower
    # "Current Connected Device" card.  Raw legacy values remain available only
    # inside last_connection.raw_evidence for debug/reports.
    visual = port_visual_display_fields(port)
    return {
        "id": port.id,
        "interface": port.interface_name,
        "status": port.get_status_display(),
        "state": port.status,
        "mode": port.get_port_mode_display(),
        "port_mode": port.port_mode,
        "vlan": port.access_vlan or port.vlan or "",
        "access_vlan": port.access_vlan or "",
        "native_vlan": port.native_vlan or "",
        "voice_vlan": port.voice_vlan or "",
        "trunk_vlans": port.trunk_vlans or "",
        "poe_summary": port.poe_summary(),
        "poe_enabled": port.poe_enabled,
        "mac_count": port.mac_count,
        "mac_addresses": port.mac_addresses or "",
        "neighbor_device": port.neighbor_device or "",
        "neighbor_port": port.neighbor_port or "",
        "neighbor_source": visual["neighbor_source"],
        "neighbor": visual["neighbor"],
        "ip_address": visual["ip_address"],
        "mac_address": visual["mac_address"],
        "device": visual["device"],
        "classification": visual["classification"],
        "direct": visual["direct"],
        "current_identity": visual["current_identity"],
        "display_label": visual["display_label"],
        "display_source": visual["display_source"],
        "search_terms": visual["search_terms"],
        "description": port.description or port.snmp_alias or "",
        "updated_at": port.updated_at.isoformat() if port.updated_at else "",
        "updated_at_text": _dt_text(port.updated_at),
        "snmp_last_poll_text": _dt_text(port.snmp_last_poll),
        "discovery_last_poll_text": _dt_text(port.discovery_last_poll),
        "last_connection": _phase79_effective_last_connection_payload(port),
        "edit_url": reverse("inventory:port_edit", args=[port.id]),
        "table_url": reverse("inventory:switch_ports_table", args=[port.switch.id]),
        "map_url": f"{reverse('inventory:switch_detail', args=[port.switch.id])}?port={port.id}",
    }


def _refresh_switch_after_action(switch):
    summary = {"ok": True, "steps": []}
    try:
        if switch.snmp_enabled:
            port_result = poll_switch_ports(switch=switch, dry_run=False, show_ignored=False)
            summary["steps"].append("snmp")
            summary["ports_updated"] = port_result.get("updated", 0)
            discovery_result = poll_switch_discovery(switch=switch, dry_run=False)
            summary["steps"].append("discovery")
            summary["discovery_updated"] = discovery_result.get("updated", 0)
            summary["neighbors"] = discovery_result.get("neighbors", 0)
            summary["mac_ports"] = discovery_result.get("mac_ports", 0)
    except Exception as exc:
        summary["ok"] = False
        summary["error"] = str(exc)
    return summary


def _dt_text(value):
    if not value:
        return "-"
    return timezone.localtime(value, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _attach_refresh_time_texts(switch):
    switch.dashboard_snmp_last_poll_text = _dt_text(getattr(switch, "snmp_last_poll", None))
    switch.dashboard_discovery_last_poll_text = _dt_text(getattr(switch, "discovery_last_poll", None))
    switch.dashboard_last_poll_text = (
        switch.dashboard_snmp_last_poll_text
        if switch.dashboard_snmp_last_poll_text != "-"
        else switch.dashboard_discovery_last_poll_text
    )
    return switch


def _switch_refresh_payload(switch):
    return {
        "switch_id": switch.id,
        "switch": switch.name,
        "ip": str(switch.management_ip),
        "snmp_last_poll": _dt_text(switch.snmp_last_poll),
        "discovery_last_poll": _dt_text(switch.discovery_last_poll),
        "snmp_error": switch.snmp_last_error or "",
        "discovery_error": switch.discovery_last_error or "",
    }


def _refresh_step_payload(stage, result):
    if stage == "sync":
        return {
            "stage": stage,
            "label": "Sync Ports",
            "created": result.get("created", 0),
            "matched": result.get("matched", 0),
            "ignored": result.get("ignored", 0),
            "summary": f"created={result.get('created', 0)} | matched={result.get('matched', 0)} | ignored={result.get('ignored', 0)}",
        }
    if stage == "ports":
        return {
            "stage": stage,
            "label": "SNMP Ports",
            "matched": result.get("matched", 0),
            "updated": result.get("updated", 0),
            "ignored": result.get("ignored", 0),
            "summary": f"matched={result.get('matched', 0)} | updated={result.get('updated', 0)} | ignored={result.get('ignored', 0)}",
        }
    if stage == "discovery":
        return {
            "stage": stage,
            "label": "CDP / LLDP / MAC",
            "matched": result.get("matched", 0),
            "updated": result.get("updated", 0),
            "neighbors": result.get("neighbors", 0),
            "mac_ports": result.get("mac_ports", 0),
            "summary": f"updated={result.get('updated', 0)} | neighbors={result.get('neighbors', 0)} | mac_ports={result.get('mac_ports', 0)}",
        }
    return {"stage": stage, "label": stage, "summary": "-"}



def _alarm_dashboard_payload(limit=8):
    try:
        active_qs = AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE)
        alarms = list(active_qs.order_by("severity", "-last_seen", "-id")[:limit])
        alarms.sort(key=lambda item: (_alarm_severity_rank(item.severity), item.switch.name if item.switch else "", item.title))
        category_counts = {
            AlarmNotification.Category.SNMP: active_qs.filter(category=AlarmNotification.Category.SNMP).count(),
            AlarmNotification.Category.SFP: active_qs.filter(category=AlarmNotification.Category.SFP).count(),
            AlarmNotification.Category.INTERFACE: active_qs.filter(category=AlarmNotification.Category.INTERFACE).count(),
            AlarmNotification.Category.TOPOLOGY: active_qs.filter(category=AlarmNotification.Category.TOPOLOGY).count(),
            AlarmNotification.Category.SYSTEM: active_qs.filter(category=AlarmNotification.Category.SYSTEM).count(),
        }
        return {
            "active": active_qs.count(),
            "critical": active_qs.filter(severity=AlarmNotification.Severity.CRITICAL).count(),
            "warning": active_qs.filter(severity=AlarmNotification.Severity.WARNING).count(),
            "items": alarms,
            "categories": category_counts,
        }
    except Exception:
        return {"active": 0, "critical": 0, "warning": 0, "items": [], "categories": {}}


def _attach_switch_alarm_summaries(switches):
    switch_ids = [switch.id for switch in switches]
    empty_titles = []
    for switch in switches:
        switch.dashboard_alarm_count = 0
        switch.dashboard_alarm_critical_count = 0
        switch.dashboard_alarm_warning_count = 0
        switch.dashboard_alarm_titles = empty_titles

    if not switch_ids:
        return

    alarms = list(
        AlarmNotification.objects.select_related("switch", "port")
        .filter(status=AlarmNotification.Status.ACTIVE, switch_id__in=switch_ids)
        .order_by("severity", "-last_seen", "-id")
    )
    by_switch = {}
    for alarm in alarms:
        by_switch.setdefault(alarm.switch_id, []).append(alarm)

    for switch in switches:
        items = by_switch.get(switch.id, [])
        items.sort(key=lambda item: (_alarm_severity_rank(item.severity), item.title))
        switch.dashboard_alarm_count = len(items)
        switch.dashboard_alarm_critical_count = sum(1 for item in items if item.severity == AlarmNotification.Severity.CRITICAL)
        switch.dashboard_alarm_warning_count = sum(1 for item in items if item.severity == AlarmNotification.Severity.WARNING)
        switch.dashboard_alarm_titles = items[:3]


def _backup_dashboard_payload(force=False):
    if not force and BACKUP_DASHBOARD_CACHE_SECONDS > 0:
        cached = cache.get(BACKUP_DASHBOARD_CACHE_KEY)
        if cached is not None:
            return cached
    try:
        backup_files = _list_backup_files()
        latest_backup = backup_files[0] if backup_files else None
        total_size = sum(item.get("size", 0) for item in backup_files)
        payload = {
            "status": "ok" if backup_files else "unknown",
            "count": len(backup_files),
            "latest": latest_backup,
            "latest_text": latest_backup.get("created_at_text", "") if latest_backup else "",
            "latest_name": latest_backup.get("name", "") if latest_backup else "",
            "total_size_text": _file_size_text(total_size),
        }
    except Exception as exc:
        payload = {
            "status": "unknown",
            "count": 0,
            "latest": None,
            "latest_text": "",
            "latest_name": "",
            "total_size_text": "-",
            "error": str(exc),
        }
    if not force and BACKUP_DASHBOARD_CACHE_SECONDS > 0:
        cache.set(BACKUP_DASHBOARD_CACHE_KEY, payload, BACKUP_DASHBOARD_CACHE_SECONDS)
    return payload

# Phase 63: analytical live dashboard payload and background status
DASHBOARD_INSIGHT_MARKER = "Phase 63 Live Insight Dashboard"
DASHBOARD_FRESH_MINUTES = 20
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


# Phase104R1: dashboard performance stabilization.
# Short TTL keeps the dashboard operational view fresh while avoiding repeated
# topology/SFP/alarm/backup aggregation work on every browser refresh.
def _phase104_int_env(name, default):
    raw = os.environ.get(name, "")
    try:
        value = int(raw or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(0, value)


DASHBOARD_INSIGHT_CACHE_KEY = "switchmap:phase104R1:dashboard_insight:v1"
DASHBOARD_INSIGHT_CACHE_SECONDS = _phase104_int_env("SWITCHMAP_DASHBOARD_INSIGHT_CACHE_SECONDS", 20)
BACKUP_DASHBOARD_CACHE_KEY = "switchmap:phase104R1:backup_dashboard:v1"
BACKUP_DASHBOARD_CACHE_SECONDS = _phase104_int_env("SWITCHMAP_BACKUP_DASHBOARD_CACHE_SECONDS", 60)

# Phase106: dashboard deep performance stabilization.
# Cache the expensive rendered device-browser fragment separately from the live
# four-card summary. This avoids rebuilding all switch-card SVG/port markup on
# every dashboard refresh while keeping cards/data refreshable.
DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS = _phase104_int_env("SWITCHMAP_DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS", 20)
DASHBOARD_DEVICE_BROWSER_CACHE_VERSION = "phase106R1-v1"
DASHBOARD_FAST_TOPOLOGY_CACHE_KEY = "switchmap-phase106R1-dashboard-fast-topology-v1"
DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS = _phase104_int_env("SWITCHMAP_DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS", 20)


def _dashboard_text_blob(switch):
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


def _is_dashboard_test_device(switch):
    blob = _dashboard_text_blob(switch)
    return any(token in blob for token in SWITCHMAP_TEST_DEVICE_TOKENS)


def _dashboard_age_text(value, now=None):
    if not value:
        return "ثبت نشده"
    now = now or timezone.now()
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 90:
        return "کمتر از یک دقیقه قبل"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقیقه قبل"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت قبل"
    days = hours // 24
    return f"{days} روز قبل"



def _dashboard_detail_url(route_name, *args, query=None, fragment=""):
    url = reverse(route_name, args=args)
    if query:
        url += "?" + urlencode({key: value for key, value in query.items() if value not in (None, "")})
    if fragment:
        url += "#" + str(fragment)
    return url


def _alarm_detail_url(alarm):
    return reverse("inventory:alarm_detail", args=[alarm.id])


def _switch_issue_url(switch_id, issue_id=""):
    return _dashboard_detail_url("inventory:switch_detail", switch_id, query={"issue": issue_id} if issue_id else None)


def _port_issue_url(switch_id, port_id, issue_id=""):
    return _dashboard_detail_url("inventory:switch_detail", switch_id, query={"port": port_id, "issue": issue_id})

def _dashboard_status_file():
    return Path(settings.BASE_DIR) / "logs" / "dashboard-background-refresh-status.json"


def _dashboard_background_status(now=None):
    now = now or timezone.now()
    path = _dashboard_status_file()
    default = {
        "configured": False,
        "state": "unknown",
        "label": "وضعیت سرویس مشخص نیست",
        "last_run_text": "ثبت نشده",
        "last_result": "unknown",
        "summary": "فایل وضعیت Auto Refresh هنوز ساخته نشده است.",
    }
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        default.update({"configured": True, "state": "error", "label": "خطا در خواندن وضعیت", "summary": str(exc)})
        return default

    completed = data.get("completed_at") or data.get("started_at") or ""
    completed_dt = None
    if completed:
        try:
            completed_dt = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
            if timezone.is_naive(completed_dt):
                completed_dt = timezone.make_aware(completed_dt, timezone.get_current_timezone())
        except Exception:
            completed_dt = None

    is_fresh = bool(completed_dt and completed_dt >= now - timedelta(minutes=DASHBOARD_FRESH_MINUTES))
    has_error = bool(data.get("errors")) or str(data.get("status") or "").lower() not in {"ok", "success", "done", ""}
    state = "ok" if is_fresh and not has_error else ("warning" if completed_dt else "unknown")
    if has_error:
        state = "warning"
    return {
        "configured": True,
        "state": state,
        "label": "Auto Refresh فعال" if state == "ok" else "Auto Refresh نیاز به بررسی دارد",
        "last_run_text": _dashboard_age_text(completed_dt, now) if completed_dt else "ثبت نشده",
        "last_run": completed_dt.isoformat() if completed_dt else "",
        "last_result": data.get("status") or "ok",
        "summary": data.get("summary") or "SNMP و Discovery در پس‌زمینه اجرا شده‌اند.",
        "devices": data.get("devices", 0),
        "ok": data.get("ok", 0),
        "failed": data.get("failed", 0),
    }


def _device_insight_item(switch, now, fresh_cutoff):
    last_poll = switch.snmp_last_poll
    last_discovery = switch.discovery_last_poll
    best_poll = max([item for item in [last_poll, last_discovery] if item], default=None)
    snmp_error = (switch.snmp_last_error or "").strip()
    discovery_error = (switch.discovery_last_error or "").strip()

    if not switch.snmp_enabled:
        status = "not_monitored"
        severity = "info"
        title = "خارج از پوشش"
        compact_reason = "Not Monitored"
        conclusion = "برای این دستگاه SNMP Read Only تعریف نشده است."
        action = "اگر باید مانیتور شود، SNMP Read Only و Community را ثبت کن."
    elif snmp_error:
        status = "poll_failed"
        severity = "critical"
        title = "خطای مانیتورینگ"
        compact_reason = "SNMP Failed"
        conclusion = "SNMP پاسخ نمی‌دهد یا مسیر UDP 161 بسته است."
        action = f"دسترسی SNMP از VM به {switch.management_ip}:161 و Community را بررسی کن."
    elif discovery_error:
        status = "discovery_warning"
        severity = "warning"
        title = "داده توپولوژی ناقص"
        compact_reason = "Discovery Stale"
        conclusion = "SNMP پایه سالم است، ولی CDP/LLDP/MAC کامل به‌روزرسانی نشده است."
        action = "دسترسی Discovery و SNMP Table ها را بررسی کن."
    elif not best_poll or best_poll < fresh_cutoff:
        status = "stale"
        severity = "warning"
        title = "داده قدیمی"
        compact_reason = "Poll Stale"
        conclusion = "آخرین داده برای تصمیم‌گیری تازه نیست."
        action = "وضعیت Scheduled Task و لاگ Auto Refresh را بررسی کن."
    else:
        status = "healthy"
        severity = "ok"
        title = "قابل اتکا"
        compact_reason = "Healthy"
        conclusion = "داده تازه و بدون خطا است."
        action = "اقدام لازم ندارد."

    issue_id = f"device-{switch.id}-{status}"
    return {
        "id": switch.id,
        "issue_id": issue_id,
        "object_type": "Device",
        "object_name": switch.name,
        "name": switch.name,
        "ip": str(switch.management_ip or ""),
        "status": status,
        "severity": severity,
        "title": title,
        "conclusion": conclusion,
        "short_reason": conclusion,
        "compact_reason": compact_reason,
        "recommended_action": action,
        "last_check_time": timezone.localtime(best_poll, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S") if best_poll else "ثبت نشده",
        "last_poll": timezone.localtime(best_poll, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S") if best_poll else "",
        "last_poll_text": _dashboard_age_text(best_poll, now) if best_poll else "ثبت نشده",
        "snmp_error": snmp_error[:180],
        "discovery_error": discovery_error[:180],
        "detail_url": _switch_issue_url(switch.id, issue_id),
    }



def _dashboard_topology_issues(sfp_dashboard, discovery_warning, limit=5):
    """Build only the compact topology issues needed by the dashboard.

    Phase106R1 intentionally avoids the full topology page builder here because
    that function can trigger many per-edge history lookups. The dashboard only
    needs a short actionable list/count.
    """
    cache_key = DASHBOARD_FAST_TOPOLOGY_CACHE_KEY
    cached = cache.get(cache_key) if DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS > 0 else None
    if cached is not None:
        return cached

    issues = []

    for item in sfp_dashboard.get("items", [])[:8]:
        if any(token in str(item.get("switch", "")).lower() for token in SWITCHMAP_TEST_DEVICE_TOKENS):
            continue
        switch_id = item.get("switch_id")
        port_id = item.get("port_id")
        issue_id = f"sfp-{switch_id}-{item.get('interface', '')}".replace(" ", "-").replace("/", "-")
        detail_url = _port_issue_url(switch_id, port_id, issue_id) if switch_id and port_id else _dashboard_detail_url("inventory:sfp_monitor", query={"switch": switch_id}, fragment=issue_id)
        issues.append({
            "issue_id": issue_id,
            "severity": "critical" if item.get("is_error") else "warning",
            "title": f"SFP / Link: {item.get('switch', '-')} {item.get('interface', '-')}",
            "summary": item.get("note") or item.get("health_text") or "SFP issue",
            "compact_reason": "SFP Warning" if not item.get("is_error") else "SFP Critical",
            "object_type": "SFP",
            "object_name": f"{item.get('switch', '-')} {item.get('interface', '-')}",
            "last_check_time": item.get("poll_time") or "ثبت نشده",
            "short_reason": item.get("note") or "SFP abnormal",
            "recommended_action": "پورت، ماژول SFP، Patch Cord و سمت مقابل لینک را بررسی کن.",
            "detail_url": detail_url,
        })

    for item in discovery_warning[:5]:
        issue_id = item.get("issue_id") or f"discovery-{item.get('id')}"
        issues.append({
            "issue_id": issue_id,
            "severity": "warning",
            "title": f"Discovery stale: {item.get('name', '-')}",
            "summary": item.get("conclusion") or "Topology discovery issue",
            "compact_reason": "Discovery Stale",
            "object_type": "Discovery",
            "object_name": item.get("name") or "Device",
            "last_check_time": item.get("last_check_time") or item.get("last_poll_text") or "ثبت نشده",
            "short_reason": item.get("discovery_error") or item.get("conclusion") or "Discovery ناقص است.",
            "recommended_action": item.get("recommended_action") or "CDP / LLDP / SNMP Table را بررسی کن.",
            "detail_url": item.get("detail_url") or _switch_issue_url(item.get("id"), issue_id),
        })

    try:
        ports = (
            Port.objects.select_related("switch")
            .filter(switch__is_active=True)
            .order_by("switch__name", "display_order", "interface_name")
        )
        for port in ports:
            if len(issues) >= 20:
                break
            switch = getattr(port, "switch", None)
            if not switch or _is_dashboard_test_device(switch):
                continue
            if not is_visible_switchmap_interface(port.interface_name):
                continue
            if _topology_role_for_port(port) == "uplink" and not port.neighbor_device and topology_alarm_should_exist(port):
                issue_id = f"topology-uplink-{port.id}"
                issues.append({
                    "issue_id": issue_id,
                    "severity": "warning",
                    "title": f"Uplink بدون Neighbor: {switch.name} {port.interface_name}",
                    "summary": "Uplink شناسایی شده ولی Neighbor ندارد.",
                    "compact_reason": "Neighbor Missing",
                    "object_type": "Topology Port",
                    "object_name": f"{switch.name} {port.interface_name}",
                    "last_check_time": _dashboard_age_text(getattr(port, "discovery_last_poll", None)),
                    "short_reason": "CDP/LLDP برای این Uplink داده معتبر نداده است.",
                    "recommended_action": "CDP/LLDP و پورت سمت مقابل را بررسی کن.",
                    "detail_url": reverse("inventory:topology_edge_detail", args=[port.id]),
                })
    except Exception:
        pass

    ranked = sorted(
        issues,
        key=lambda item: (0 if item.get("severity") == "critical" else 1, item.get("title") or ""),
    )
    result = (ranked[:limit], len(ranked))
    if DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS > 0:
        cache.set(cache_key, result, DASHBOARD_FAST_TOPOLOGY_CACHE_SECONDS)
    return result


def _dashboard_insight_payload_uncached(force=False):
    now = timezone.now()
    fresh_cutoff = now - timedelta(minutes=DASHBOARD_FRESH_MINUTES)
    queryset = (
        Switch.objects.filter(is_active=True)
        .prefetch_related("ports")
        .order_by("topology_position", "name")
    )
    switches = [switch for switch in queryset if not _is_dashboard_test_device(switch)]
    device_items = [_device_insight_item(switch, now, fresh_cutoff) for switch in switches]

    healthy = [item for item in device_items if item["status"] == "healthy"]
    failed = [item for item in device_items if item["status"] == "poll_failed"]
    stale = [item for item in device_items if item["status"] == "stale"]
    discovery_warning = [item for item in device_items if item["status"] == "discovery_warning"]
    not_monitored = [item for item in device_items if item["status"] == "not_monitored"]
    attention = failed + stale + discovery_warning
    total = len(device_items)
    reliable_percent = round((len(healthy) / total) * 100) if total else 0
    coverage_percent = round(((total - len(not_monitored)) / total) * 100) if total else 0

    alarm_dashboard = _alarm_dashboard_payload(limit=6)
    sfp_dashboard = _sfp_dashboard_payload()
    backup_dashboard = _backup_dashboard_payload(force=force)
    background_status = _dashboard_background_status(now)
    topology_issues, topology_issue_count = _dashboard_topology_issues(sfp_dashboard, discovery_warning, limit=5)

    if alarm_dashboard.get("critical"):
        state = "critical"
        title = "آلارم Critical فعال است"
        subtitle = "اول آلارم‌های Critical را بررسی کن؛ این موارد روی عملیات اثر مستقیم دارند."
    elif failed:
        state = "critical"
        title = f"{len(failed)} دستگاه مانیتورینگ ناموفق دارد"
        subtitle = "SNMP پاسخ نمی‌دهد؛ مسیر شبکه، Firewall یا Community را بررسی کن."
    elif stale:
        state = "warning"
        title = f"{len(stale)} دستگاه داده تازه ندارد"
        subtitle = "داده قدیمی برای تصمیم‌گیری قابل اتکا نیست؛ سرویس Auto Refresh یا لاگ آن را بررسی کن."
    elif topology_issue_count:
        state = "warning"
        title = "چند هشدار قابل بررسی وجود دارد"
        subtitle = "داده اصلی تازه است، ولی بعضی منابع تکمیلی نیاز به بررسی دارند."
    else:
        state = "ok"
        title = "وضعیت شبکه قابل اتکا است"
        subtitle = "داده‌های مانیتورینگ تازه‌اند و خطای مهمی دیده نمی‌شود."

    actions = []
    for item in failed[:4]:
        actions.append({
            "issue_id": item["issue_id"],
            "object_type": item["object_type"],
            "object_name": item["object_name"],
            "severity": "critical",
            "title": item["name"],
            "summary": item["conclusion"],
            "short_reason": item["short_reason"],
            "compact_reason": item.get("compact_reason", item["short_reason"]),
            "action": item["recommended_action"],
            "recommended_action": item["recommended_action"],
            "last_check_time": item["last_check_time"],
            "last_poll_text": item["last_poll_text"],
            "detail_url": item["detail_url"],
        })
    for item in stale[:3]:
        actions.append({
            "issue_id": item["issue_id"],
            "object_type": item["object_type"],
            "object_name": item["object_name"],
            "severity": "warning",
            "title": item["name"],
            "summary": item["conclusion"],
            "short_reason": item["short_reason"],
            "compact_reason": item.get("compact_reason", item["short_reason"]),
            "action": item["recommended_action"],
            "recommended_action": item["recommended_action"],
            "last_check_time": item["last_check_time"],
            "last_poll_text": item["last_poll_text"],
            "detail_url": item["detail_url"],
        })
    for alarm in alarm_dashboard.get("items", [])[:4]:
        target_name = alarm.switch.name if alarm.switch else "SwitchMap"
        if alarm.port:
            target_name = f"{target_name} / {alarm.port.interface_name}"
        actions.append({
            "issue_id": f"alarm-{alarm.id}",
            "object_type": "Alarm",
            "object_name": target_name,
            "severity": "critical" if alarm.severity == AlarmNotification.Severity.CRITICAL else "warning",
            "title": alarm.title,
            "summary": alarm.message or alarm.details or "آلارم فعال",
            "short_reason": alarm.message or alarm.details or "آلارم فعال",
            "compact_reason": "Alarm Active",
            "action": "جزئیات را در Alarm Center بررسی و Ack/Resolve کن.",
            "recommended_action": "جزئیات را در Alarm Center بررسی و Ack/Resolve کن.",
            "last_check_time": timezone.localtime(alarm.last_seen, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S") if alarm.last_seen else "ثبت نشده",
            "last_poll_text": _dashboard_age_text(alarm.last_seen, now),
            "detail_url": _alarm_detail_url(alarm),
        })
    if not actions:
        actions.append({
            "issue_id": "dashboard-ok",
            "object_type": "Dashboard",
            "object_name": "SwitchMap",
            "severity": "ok",
            "title": "اقدام فوری لازم نیست",
            "summary": "وضعیت فعلی قابل اتکا است.",
            "short_reason": "Issue فعالی دیده نشد.",
            "compact_reason": "OK",
            "action": "داشبورد به‌صورت خودکار به‌روزرسانی می‌شود.",
            "recommended_action": "اقدام لازم ندارد.",
            "last_check_time": timezone.localtime(now, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "last_poll_text": _dashboard_age_text(now, now),
            "detail_url": reverse("inventory:switch_list"),
        })

    alarm_items = []
    for alarm in alarm_dashboard.get("items", [])[:6]:
        target_name = alarm.switch.name if alarm.switch else "SwitchMap"
        alarm_items.append({
            "id": alarm.id,
            "issue_id": f"alarm-{alarm.id}",
            "object_type": "Alarm",
            "object_name": target_name,
            "title": alarm.title,
            "severity": alarm.severity,
            "target": target_name,
            "port": alarm.port.interface_name if alarm.port else "",
            "message": alarm.message or alarm.details or "",
            "short_reason": alarm.message or alarm.details or "آلارم فعال",
            "compact_reason": "Alarm Active",
            "recommended_action": "Ack یا Resolve را از Alarm Center انجام بده.",
            "last_check_time": timezone.localtime(alarm.last_seen, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S") if alarm.last_seen else "ثبت نشده",
            "last_seen_text": _dashboard_age_text(alarm.last_seen, now),
            "detail_url": _alarm_detail_url(alarm),
        })

    return {
        "phase_marker": DASHBOARD_INSIGHT_MARKER,
        "generated_at": timezone.localtime(now, IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "overall": {"state": state, "title": title, "subtitle": subtitle},
        "counters": {
            "total_devices": total,
            "healthy": len(healthy),
            "attention": len(attention),
            "snmp_failed": len(failed),
            "stale": len(stale),
            "not_monitored": len(not_monitored),
            "coverage_percent": coverage_percent,
            "reliable_percent": reliable_percent,
            "active_alarms": alarm_dashboard.get("active", 0),
            "critical_alarms": alarm_dashboard.get("critical", 0),
            "warning_alarms": alarm_dashboard.get("warning", 0),
            "sfp_issues": sfp_dashboard.get("summary", {}).get("active", 0),
            "sfp_critical": sfp_dashboard.get("summary", {}).get("error", 0),
            "topology_issues": topology_issue_count,
            "topology_critical": sum(1 for item in topology_issues if item.get("severity") == "critical"),
        },
        "background": background_status,
        "actions": actions[:8],
        "alarms": alarm_items,
        "topology_issues": topology_issues,
        "device_items": device_items,
        "sfp_dashboard": sfp_dashboard,
        "backup_dashboard": backup_dashboard,
        "alarm_categories": alarm_dashboard.get("categories", {}),
    }


def _dashboard_insight_payload(force=False):
    if force or DASHBOARD_INSIGHT_CACHE_SECONDS <= 0:
        return _dashboard_insight_payload_uncached(force=True)
    cached = cache.get(DASHBOARD_INSIGHT_CACHE_KEY)
    if cached is not None:
        return cached
    payload = _dashboard_insight_payload_uncached(force=False)
    cache.set(DASHBOARD_INSIGHT_CACHE_KEY, payload, DASHBOARD_INSIGHT_CACHE_SECONDS)
    return payload


def switchmap_dashboard_data_view(request):
    force = str(request.GET.get("force", "")).strip().lower() in {"1", "true", "yes", "refresh"}
    return JsonResponse({"ok": True, "dashboard": _dashboard_insight_payload(force=force)})


def _dashboard_device_browser_cache_key(request, search_query=""):
    user = getattr(request, "user", None)
    role = user_role(user)
    flags = "".join([
        "r1" if can_refresh(user) else "r0",
        "a1" if can_admin_panel(user) else "a0",
        "e1" if can_edit_port(user) else "e0",
        "s1" if can_run_ssh(user) else "s0",
    ])
    query = (search_query or "").strip().lower()
    safe_role = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(role or "anon")).strip("-") or "anon"
    safe_query = re.sub(r"[^a-zA-Z0-9_.-]+", "-", query).strip("-")[:80]
    return f"switchmap-{DASHBOARD_DEVICE_BROWSER_CACHE_VERSION}-device-browser-{safe_role}-{flags}-{safe_query}"


def _dashboard_device_switches(search_query=""):
    switches = (
        Switch.objects.filter(is_active=True)
        .annotate(
            total_ports=Count("ports", distinct=True),
            up_ports=Count("ports", filter=Q(ports__status=Port.Status.UP), distinct=True),
            down_ports=Count("ports", filter=Q(ports__status=Port.Status.DOWN), distinct=True),
            disabled_ports=Count("ports", filter=Q(ports__status=Port.Status.DISABLED), distinct=True),
            error_ports=Count("ports", filter=Q(ports__status=Port.Status.ERROR), distinct=True),
        )
        .prefetch_related(VISIBLE_PORT_PREFETCH)
    )

    if search_query:
        switches = switches.filter(
            Q(name__icontains=search_query)
            | Q(management_ip__icontains=search_query)
            | Q(model__icontains=search_query)
            | Q(location__icontains=search_query)
            | Q(ports__interface_name__icontains=search_query)
            | Q(ports__connected_device__icontains=search_query)
            | Q(ports__description__icontains=search_query)
            | Q(ports__owner__icontains=search_query)
            | Q(ports__ip_address__icontains=search_query)
            | Q(ports__mac_address__icontains=search_query)
            | Q(ports__port_mode__icontains=search_query)
            | Q(ports__trunk_vlans__icontains=search_query)
            | Q(ports__snmp_raw_name__icontains=search_query)
            | Q(ports__snmp_alias__icontains=search_query)
            | Q(ports__snmp_oper_status__icontains=search_query)
            | Q(ports__neighbor_device__icontains=search_query)
            | Q(ports__neighbor_ip__icontains=search_query)
            | Q(ports__neighbor_port__icontains=search_query)
            | Q(ports__mac_addresses__icontains=search_query)
            | Q(ports__room__icontains=search_query)
            | Q(ports__rack__icontains=search_query)
            | Q(ports__rack_unit__icontains=search_query)
            | Q(ports__patch_panel__icontains=search_query)
            | Q(ports__patch_panel_port__icontains=search_query)
            | Q(ports__outlet__icontains=search_query)
            | Q(ports__cable_label__icontains=search_query)
            | Q(ports__cable_type__icontains=search_query)
            | Q(ports__cable_length__icontains=search_query)
            | Q(ports__asset_tag__icontains=search_query)
        ).distinct()

    switches = list(switches)
    _attach_switch_alarm_summaries(switches)
    for switch in switches:
        _apply_dashboard_port_groups(switch)
        _attach_refresh_time_texts(switch)
    return switches


def _dashboard_device_browser_html(request, search_query=""):
    use_cache = not bool((search_query or "").strip()) and DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS > 0
    cache_key = _dashboard_device_browser_cache_key(request, search_query) if use_cache else ""
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    switches = _dashboard_device_switches(search_query)
    html = render_to_string(
        "inventory/includes/dashboard_device_browser.html",
        {"switches": switches},
        request=request,
    )
    if use_cache:
        cache.set(cache_key, html, DASHBOARD_DEVICE_BROWSER_CACHE_SECONDS)
    return html

def dashboard_device_browser_fragment_view(request):
    """Phase107R2: return the heavy dashboard device/port browser only when requested."""
    search_query = request.GET.get("q", "").strip()
    html = _dashboard_device_browser_html(request, search_query=search_query)
    return HttpResponse(html)



def switch_list(request):
    search_query = request.GET.get("q", "").strip()
    dashboard_insight = _dashboard_insight_payload()
    dashboard_counters = dashboard_insight.get("counters", {})
    alarm_dashboard = {
        "active": dashboard_counters.get("active_alarms", 0),
        "critical": dashboard_counters.get("critical_alarms", 0),
        "warning": dashboard_counters.get("warning_alarms", 0),
        "items": dashboard_insight.get("alarms", []),
        "categories": dashboard_insight.get("alarm_categories", {}),
    }
    dashboard_device_browser_url = reverse("inventory:dashboard_device_browser_fragment")
    if search_query:
        dashboard_device_browser_url += "?" + urlencode({"q": search_query})

    return render(
        request,
        "inventory/switch_list.html",
        {
            "search_query": search_query,
            "dashboard_insight": dashboard_insight,
            "sfp_dashboard": dashboard_insight.get("sfp_dashboard", {}),
            "alarm_dashboard": alarm_dashboard,
            "backup_dashboard": dashboard_insight.get("backup_dashboard", {}),
            "dashboard_device_browser_url": dashboard_device_browser_url,
            "default_ssh_username": "admin",
        },
    )

def switch_detail(request, switch_id):
    switch = get_object_or_404(
        Switch.objects.prefetch_related(VISIBLE_PORT_PREFETCH, "port_action_logs"),
        id=switch_id,
        is_active=True,
    )

    all_ports = list(switch.ports.all())
    if switch.vendor == Switch.Vendor.MIKROTIK:
        ports = sorted(all_ports, key=lambda port: (port.display_order, port.interface_name))
        access_ports = ports
        uplink_ports = sorted(
            [port for port in ports if str(port.interface_name).lower().startswith(("sfp", "qsfp"))],
            key=lambda port: port.display_order,
        )
    else:
        ports = [
            port for port in all_ports
            if is_visible_switchmap_interface(port.interface_name)
        ]
        access_ports = [
            port for port in ports
            if is_access_panel_interface(port.interface_name)
        ]
        uplink_ports = sorted(
            [port for port in ports if is_uplink_interface(port.interface_name)],
            key=lambda port: port.display_order,
        )
    ignored_ports = [
        port for port in all_ports
        if is_legacy_gi_sfp_interface(port.interface_name)
    ]

    port_summary = {
        "total": len(ports),
        "access": len(access_ports),
        "uplinks": len(uplink_ports),
        "ignored": len(ignored_ports),
        "up": sum(1 for port in ports if port.status == Port.Status.UP),
        "down": sum(1 for port in ports if port.status == Port.Status.DOWN),
        "disabled": sum(1 for port in ports if port.status == Port.Status.DISABLED),
        "error": sum(1 for port in ports if port.status == Port.Status.ERROR),
        "trunk": sum(1 for port in ports if port.port_mode == Port.PortMode.TRUNK),
        "neighbors": sum(1 for port in ports if port.neighbor_device),
        "mac_ports": sum(1 for port in ports if port.mac_count > 0),
    }

    return render(
        request,
        "inventory/switch_detail.html",
        {
            "switch": switch,
            "top_ports": access_ports[0::2],
            "bottom_ports": access_ports[1::2],
            "uplink_top_ports": uplink_ports[0:2],
            "uplink_bottom_ports": uplink_ports[2:4],
            "uplink_ports": uplink_ports,
            "ignored_ports": ignored_ports,
            "port_summary": port_summary,
        },
    )


def switch_edit(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id)
    if request.method == "POST":
        form = SwitchForm(request.POST, instance=switch)
        if form.is_valid():
            updated_switch = form.save()
            try:
                _log_system_action(
                    request,
                    "switch_edit",
                    f"{updated_switch.name} | {updated_switch.management_ip} | {updated_switch.vendor} | {updated_switch.device_family} | {updated_switch.device_role}",
                )
            except Exception:
                pass
            messages.success(request, "تغییرات سوییچ ذخیره شد.")
            return redirect("inventory:switch_detail", switch_id=updated_switch.id)
        messages.error(request, "ذخیره انجام نشد؛ فیلدهای مشخص‌شده را اصلاح کن.")
    else:
        form = SwitchForm(instance=switch)

    return render(
        request,
        "inventory/switch_form.html",
        {
            "form": form,
            "switch": switch,
        },
    )


def switch_snmp_test(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    if request.method != "POST":
        return redirect("inventory:switch_detail", switch_id=switch.id)

    result = test_snmp_connection(switch)
    if result["ok"]:
        messages.success(
            request,
            f"SNMP TEST OK | target={result.get('target', '-')} | local={result.get('local', '-')} | value={result.get('value', '-')}",
        )
    else:
        messages.error(
            request,
            f"SNMP TEST FAILED | target={result.get('target', '-')} | local={result.get('local', '-')} | error={result.get('error', '-')}",
        )
    return redirect("inventory:switch_detail", switch_id=switch.id)


def switch_poll_now(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    if request.method != "POST":
        return redirect("inventory:switch_detail", switch_id=switch.id)

    dry_run = request.POST.get("dry_run") == "1"
    try:
        result = poll_switch_ports(switch=switch, dry_run=dry_run, show_ignored=False)
    except SnmpError as exc:
        messages.error(request, f"SNMP POLL FAILED | {exc}")
        return redirect("inventory:switch_detail", switch_id=switch.id)

    result_label = "SNMP DRY RUN OK" if dry_run else "SNMP POLL OK"
    messages.success(
        request,
        f"{result_label} | matched={result['matched']} | updated={result['updated']} | ignored={result['ignored']} | target={result.get('target', '-')} | local={result.get('local', '-')}",
    )
    return redirect("inventory:switch_detail", switch_id=switch.id)


def switch_discovery_now(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    if request.method != "POST":
        return redirect("inventory:switch_detail", switch_id=switch.id)

    dry_run = request.POST.get("dry_run") == "1"
    try:
        result = poll_switch_discovery(switch=switch, dry_run=dry_run)
    except SnmpError as exc:
        messages.error(request, f"DISCOVERY FAILED | {exc}")
        return redirect("inventory:switch_detail", switch_id=switch.id)

    result_label = "DISCOVERY DRY RUN OK" if dry_run else "DISCOVERY POLL OK"
    messages.success(
        request,
        f"{result_label} | matched={result['matched']} | updated={result['updated']} | neighbors={result['neighbors']} | mac_ports={result['mac_ports']} | target={result.get('target', '-')} | local={result.get('local', '-')}",
    )
    return redirect("inventory:switch_detail", switch_id=switch.id)


def switch_sync_snmp_ports(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    if request.method != "POST":
        return redirect("inventory:switch_detail", switch_id=switch.id)

    dry_run = request.POST.get("dry_run") == "1"
    try:
        result = sync_missing_snmp_ports(switch=switch, dry_run=dry_run)
        if not dry_run:
            poll_switch_ports(switch=switch, dry_run=False, show_ignored=False)
    except SnmpError as exc:
        messages.error(request, f"SNMP PORT SYNC FAILED | {exc}")
        return redirect("inventory:switch_detail", switch_id=switch.id)

    label = "SNMP PORT SYNC DRY RUN" if dry_run else "SNMP PORT SYNC"
    messages.success(
        request,
        f"{label} OK | created={result.get('created', 0)} | matched={result.get('matched', 0)} | ignored={result.get('ignored', 0)}",
    )
    return redirect("inventory:switch_detail", switch_id=switch.id)


def switch_ports_table(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    ports = Port.objects.filter(switch=switch).order_by("display_order", "interface_name")

    query = request.GET.get("q", "").strip()
    filter_query = request.GET.get("filter", "").strip()
    mode = request.GET.get("mode", "").strip()
    status = request.GET.get("status", "").strip()
    if filter_query == "trunk":
        mode = Port.PortMode.TRUNK
    elif filter_query in {Port.Status.UP, Port.Status.DOWN, Port.Status.DISABLED, Port.Status.ERROR}:
        status = filter_query

    if query:
        ports = ports.filter(
            Q(interface_name__icontains=query)
            | Q(description__icontains=query)
            | Q(connected_device__icontains=query)
            | Q(owner__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(neighbor_device__icontains=query)
            | Q(neighbor_port__icontains=query)
            | Q(mac_addresses__icontains=query)
            | Q(room__icontains=query)
            | Q(rack__icontains=query)
            | Q(rack_unit__icontains=query)
            | Q(patch_panel__icontains=query)
            | Q(patch_panel_port__icontains=query)
            | Q(outlet__icontains=query)
            | Q(cable_label__icontains=query)
            | Q(cable_type__icontains=query)
            | Q(cable_length__icontains=query)
            | Q(asset_tag__icontains=query)
        )
    if mode:
        ports = ports.filter(port_mode=mode)
    if status:
        ports = ports.filter(status=status)

    visible_ports = [
        port for port in list(ports)
        if is_visible_switchmap_interface(port.interface_name)
    ]

    return render(
        request,
        "inventory/switch_ports_table.html",
        {
            "switch": switch,
            "ports": visible_ports,
            "query": query,
            "mode": mode,
            "status": status,
            "mode_choices": Port.PortMode.choices,
            "status_choices": Port.Status.choices,
            "search_query": query,
            "filter_query": filter_query or mode or status,
            "filter_options": [("", "همه"), ("trunk", "Trunk"), ("up", "Up"), ("down", "Down"), ("disabled", "Disabled"), ("error", "Error")],
            "default_ssh_username": (switch.ssh_username or "admin"),
        },
    )


def port_ssh_helper(request, port_id):
    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    switch = port.switch
    ssh_username = (switch.ssh_username or "admin").strip()
    ssh_port = int(switch.ssh_port or 22)
    ssh_target = f"{ssh_username}@{switch.management_ip}"

    interface_commands = [
        "terminal length 0",
        f"show interfaces {port.interface_name} status",
        f"show interfaces {port.interface_name} description",
        f"show running-config interface {port.interface_name}",
        f"show interfaces {port.interface_name} switchport",
        f"show interfaces {port.interface_name}",
        f"show power inline {port.interface_name} detail",
        f"show mac address-table interface {port.interface_name}",
        f"show cdp neighbors {port.interface_name} detail",
        f"show lldp neighbors {port.interface_name} detail",
    ]

    return render(
        request,
        "inventory/port_ssh_helper.html",
        {
            "port": port,
            "switch": switch,
            "ssh_enabled": switch.ssh_enabled,
            "ssh_command": f"ssh -p {ssh_port} {ssh_target}",
            "ssh_url": f"ssh://{ssh_target}:{ssh_port}",
            "putty_command": f"putty.exe -ssh {ssh_target} -P {ssh_port}",
            "interface_commands": interface_commands,
        },
    )


def port_edit(request, port_id):
    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    if request.method == "POST":
        before_snapshot = _port_documentation_snapshot(port)
        form = PortForm(request.POST, instance=port)
        if form.is_valid():
            changed_field_names = list(form.changed_data)
            saved_port = form.save()
            after_snapshot = _port_documentation_snapshot(saved_port)
            changed_labels = _port_changed_labels(changed_field_names)
            PortActionLog.objects.create(
                port=saved_port,
                switch=saved_port.switch,
                action="manual_port_edit",
                action_label="Manual Port Edit",
                value=saved_port.interface_name,
                ssh_username="",
                success=True,
                message=("Changed fields: " + ", ".join(changed_labels)) if changed_labels else "Manual port documentation saved. No visible change.",
                **_audit_log_context(request),
            )
            if changed_field_names:
                _create_port_documentation_history(
                    request=request,
                    port=saved_port,
                    changed_field_names=changed_field_names,
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                )
            next_url = request.POST.get("next") or "detail"
            if next_url == "table":
                return redirect("inventory:switch_ports_table", switch_id=port.switch.id)
            if next_url == "assets":
                return redirect("inventory:asset_documentation")
            return redirect("inventory:switch_detail", switch_id=port.switch.id)
    else:
        form = PortForm(instance=port)

    recent_history = port.documentation_history.select_related("switch").order_by("-created_at")[:10]
    for item in recent_history:
        item.created_at_text = _dt_text(item.created_at)

    return render(
        request,
        "inventory/port_form.html",
        {
            "form": form,
            "port": port,
            "switch": port.switch,
            "next": request.GET.get("next", "detail"),
            "recent_history": recent_history,
        },
    )


def _json_error(message, status=400, **extra):
    payload = {"ok": False, "message": message, "error": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def _actor_username(request, fallback=""):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user.get_username()
    return fallback or ""


def _audit_log_context(request, ssh_username=""):
    return {
        "actor_username": _actor_username(request, ssh_username),
        "actor_role": user_role(getattr(request, "user", None)),
        "client_ip": _client_ip(request),
        "request_path": request.path[:255],
    }


PORT_DOCUMENTATION_FIELDS = [
    "description",
    "connected_device",
    "device_type",
    "owner",
    "ip_address",
    "mac_address",
    "port_mode",
    "access_vlan",
    "native_vlan",
    "voice_vlan",
    "trunk_vlans",
    "vlan",
    "status",
    "poe_enabled",
    "documentation_status",
    "asset_tag",
    "room",
    "rack",
    "rack_unit",
    "patch_panel",
    "patch_panel_port",
    "outlet",
    "cable_label",
    "cable_type",
    "cable_length",
    "prtg_url",
    "notes",
]

PORT_DOCUMENTATION_LABELS = {
    "description": "Description",
    "connected_device": "Device",
    "device_type": "Device Type",
    "owner": "Owner",
    "ip_address": "IP",
    "mac_address": "MAC",
    "port_mode": "Mode",
    "access_vlan": "Access VLAN",
    "native_vlan": "Native VLAN",
    "voice_vlan": "Voice VLAN",
    "trunk_vlans": "Trunk VLANs",
    "vlan": "VLAN",
    "status": "Status",
    "poe_enabled": "PoE",
    "documentation_status": "Documentation Status",
    "asset_tag": "Asset Tag",
    "room": "Room",
    "rack": "Rack",
    "rack_unit": "Rack Unit",
    "patch_panel": "Patch Panel",
    "patch_panel_port": "Patch Port",
    "outlet": "Outlet",
    "cable_label": "Cable Label",
    "cable_type": "Cable Type",
    "cable_length": "Cable Length",
    "prtg_url": "PRTG URL",
    "notes": "Notes",
}


def _stringify_port_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _port_documentation_snapshot(port):
    return {
        field_name: _stringify_port_value(getattr(port, field_name, ""))
        for field_name in PORT_DOCUMENTATION_FIELDS
    }


def _port_changed_labels(field_names):
    return [PORT_DOCUMENTATION_LABELS.get(field_name, field_name) for field_name in field_names]


def _create_port_documentation_history(request, port, changed_field_names, before_snapshot, after_snapshot):
    tracked_changed_fields = [field_name for field_name in changed_field_names if field_name in PORT_DOCUMENTATION_FIELDS]
    if not tracked_changed_fields:
        return None

    changed_before = {field_name: before_snapshot.get(field_name, "") for field_name in tracked_changed_fields}
    changed_after = {field_name: after_snapshot.get(field_name, "") for field_name in tracked_changed_fields}
    labels = _port_changed_labels(tracked_changed_fields)

    return PortDocumentationHistory.objects.create(
        port=port,
        switch=port.switch,
        interface_name=port.interface_name,
        changed_fields=", ".join(labels),
        before_data=json.dumps(changed_before, ensure_ascii=False, sort_keys=True),
        after_data=json.dumps(changed_after, ensure_ascii=False, sort_keys=True),
        actor_username=_actor_username(request),
        actor_role=user_role(getattr(request, "user", None)),
        client_ip=_client_ip(request),
        request_path=request.path[:255],
        note="Manual port documentation update.",
    )


def _visible_port_list(queryset):
    return [port for port in list(queryset) if is_visible_switchmap_interface(port.interface_name)]


def _asset_filter_querystring(request):
    querydict = request.GET.copy()
    querydict.pop("page", None)
    querydict.pop("export", None)
    return querydict.urlencode()


def _asset_port_queryset(request):
    ports = Port.objects.select_related("switch").filter(switch__is_active=True).order_by("switch__name", "display_order", "interface_name")
    query = request.GET.get("q", "").strip()
    switch_id = request.GET.get("switch", "").strip()
    status = request.GET.get("status", "").strip()
    mode = request.GET.get("mode", "").strip()
    device_type = request.GET.get("device_type", "").strip()
    documentation_status = request.GET.get("documentation_status", "").strip()
    has_neighbor = request.GET.get("has_neighbor", "").strip()
    has_mac = request.GET.get("has_mac", "").strip()

    if query:
        ports = ports.filter(
            Q(switch__name__icontains=query)
            | Q(switch__management_ip__icontains=query)
            | Q(interface_name__icontains=query)
            | Q(description__icontains=query)
            | Q(connected_device__icontains=query)
            | Q(owner__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(neighbor_device__icontains=query)
            | Q(neighbor_port__icontains=query)
            | Q(mac_addresses__icontains=query)
            | Q(room__icontains=query)
            | Q(rack__icontains=query)
            | Q(rack_unit__icontains=query)
            | Q(patch_panel__icontains=query)
            | Q(patch_panel_port__icontains=query)
            | Q(outlet__icontains=query)
            | Q(cable_label__icontains=query)
            | Q(cable_type__icontains=query)
            | Q(cable_length__icontains=query)
            | Q(asset_tag__icontains=query)
            | Q(snmp_alias__icontains=query)
            | Q(notes__icontains=query)
        )
    if switch_id:
        ports = ports.filter(switch_id=switch_id)
    if status:
        ports = ports.filter(status=status)
    if mode:
        ports = ports.filter(port_mode=mode)
    if device_type:
        ports = ports.filter(device_type=device_type)
    if documentation_status:
        ports = ports.filter(documentation_status=documentation_status)
    if has_neighbor == "yes":
        ports = ports.exclude(neighbor_device="")
    elif has_neighbor == "no":
        ports = ports.filter(neighbor_device="")
    if has_mac == "yes":
        ports = ports.filter(mac_count__gt=0)
    elif has_mac == "no":
        ports = ports.filter(mac_count=0)

    return ports, {
        "query": query,
        "switch_id": switch_id,
        "status": status,
        "mode": mode,
        "device_type": device_type,
        "documentation_status": documentation_status,
        "has_neighbor": has_neighbor,
        "has_mac": has_mac,
    }


def _asset_export_headers():
    return [
        "switch",
        "management_ip",
        "interface",
        "status",
        "mode",
        "documentation_status",
        "asset_tag",
        "device_type",
        "connected_device",
        "owner",
        "ip_address",
        "mac_address",
        "access_vlan",
        "native_vlan",
        "voice_vlan",
        "trunk_vlans",
        "poe",
        "neighbor_device",
        "neighbor_port",
        "mac_count",
        "mac_addresses",
        "description",
        "room",
        "rack",
        "rack_unit",
        "patch_panel",
        "patch_panel_port",
        "outlet",
        "cable_label",
        "cable_type",
        "cable_length",
        "prtg_url",
        "notes",
        "snmp_alias",
        "updated_at",
    ]


def _asset_export_rows(ports):
    rows = []
    for port in ports:
        rows.append([
            port.switch.name,
            port.switch.management_ip,
            port.interface_name,
            port.get_status_display(),
            port.get_port_mode_display(),
            port.get_documentation_status_display(),
            port.asset_tag,
            port.get_device_type_display(),
            port.connected_device,
            port.owner,
            port.ip_address or "",
            port.mac_address,
            port.access_vlan or "",
            port.native_vlan or "",
            port.voice_vlan or "",
            port.trunk_vlans,
            port.poe_summary(),
            port.neighbor_device,
            port.neighbor_port,
            port.mac_count,
            port.mac_addresses,
            port.description,
            port.room,
            port.rack,
            port.rack_unit,
            port.patch_panel,
            port.patch_panel_port,
            port.outlet,
            port.cable_label,
            port.cable_type,
            port.cable_length,
            port.prtg_url,
            port.notes,
            port.snmp_alias,
            _dt_text(port.updated_at),
        ])
    return rows


def _xlsx_column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _minimal_xlsx_bytes(headers, rows, sheet_name="SwitchMap Assets"):
    from xml.sax.saxutils import escape

    all_rows = [headers] + rows
    sheet_rows = []
    for row_number, row in enumerate(all_rows, start=1):
        cells = []
        for col_number, value in enumerate(row, start=1):
            ref = f"{_xlsx_column_name(col_number)}{row_number}"
            text = escape(str(value if value is not None else ""))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetData>{"".join(sheet_rows)}</sheetData>
</worksheet>'''
    safe_sheet_name = escape(sheet_name[:31] or "Sheet1")
    workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="{safe_sheet_name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
        archive.writestr("xl/styles.xml", styles)
    return output.getvalue()


def asset_documentation_view(request):
    ports_queryset, filters = _asset_port_queryset(request)
    visible_ports = _visible_port_list(ports_queryset)

    for port in visible_ports:
        port.updated_at_text = _dt_text(port.updated_at)

    stats = {
        "total": len(visible_ports),
        "documented": sum(1 for port in visible_ports if port.documentation_status == Port.DocumentationStatus.DOCUMENTED),
        "partial": sum(1 for port in visible_ports if port.documentation_status == Port.DocumentationStatus.PARTIAL),
        "needs_review": sum(1 for port in visible_ports if port.documentation_status == Port.DocumentationStatus.NEEDS_REVIEW),
        "undocumented": sum(1 for port in visible_ports if port.documentation_status == Port.DocumentationStatus.UNDOCUMENTED),
        "active_undocumented": sum(
            1 for port in visible_ports
            if port.status == Port.Status.UP and port.documentation_status != Port.DocumentationStatus.DOCUMENTED
        ),
    }

    paginator = Paginator(visible_ports, 100)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = _asset_filter_querystring(request)

    return render(
        request,
        "inventory/asset_documentation.html",
        {
            "page_obj": page_obj,
            "stats": stats,
            "switches": Switch.objects.filter(is_active=True).order_by("name"),
            "status_choices": Port.Status.choices,
            "mode_choices": Port.PortMode.choices,
            "device_type_choices": Port.DeviceType.choices,
            "documentation_status_choices": Port.DocumentationStatus.choices,
            "filters": filters,
            "filter_querystring": filter_querystring,
        },
    )


def asset_documentation_export_csv_view(request):
    ports_queryset, _filters = _asset_port_queryset(request)
    visible_ports = _visible_port_list(ports_queryset)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="switchmap_asset_documentation.csv"'
    response.write("﻿")

    writer = csv.writer(response)
    writer.writerow(_asset_export_headers())
    for row in _asset_export_rows(visible_ports):
        writer.writerow(row)
    return response


def asset_documentation_export_xlsx_view(request):
    ports_queryset, _filters = _asset_port_queryset(request)
    visible_ports = _visible_port_list(ports_queryset)
    payload = _minimal_xlsx_bytes(_asset_export_headers(), _asset_export_rows(visible_ports))
    response = HttpResponse(payload, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="switchmap_asset_documentation.xlsx"'
    return response


def port_documentation_history_view(request, port_id):
    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    history_items = list(port.documentation_history.select_related("switch").order_by("-created_at")[:100])

    for item in history_items:
        item.created_at_text = _dt_text(item.created_at)
        try:
            before_data = json.loads(item.before_data or "{}")
        except json.JSONDecodeError:
            before_data = {}
        try:
            after_data = json.loads(item.after_data or "{}")
        except json.JSONDecodeError:
            after_data = {}
        keys = sorted(set(before_data) | set(after_data))
        item.change_rows = [
            {
                "field": PORT_DOCUMENTATION_LABELS.get(key, key),
                "before": before_data.get(key, ""),
                "after": after_data.get(key, ""),
            }
            for key in keys
        ]

    return render(
        request,
        "inventory/port_history.html",
        {
            "port": port,
            "switch": port.switch,
            "history_items": history_items,
        },
    )


ROLE_GROUP_NAMES = {ROLE_VIEW_ONLY, ROLE_OPERATOR, ROLE_ADMIN}


def _ensure_role_groups():
    for role_name in ROLE_GROUP_NAMES:
        Group.objects.get_or_create(name=role_name)


def _effective_user_role(target_user):
    return user_role(target_user)


def _apply_user_role(target_user, role_name):
    _ensure_role_groups()
    target_user.groups.remove(*Group.objects.filter(name__in=ROLE_GROUP_NAMES))
    if role_name in {ROLE_OPERATOR, ROLE_ADMIN}:
        target_user.groups.add(Group.objects.get(name=role_name))


def _user_form_initial(target_user):
    return {
        "username": target_user.username,
        "first_name": target_user.first_name,
        "last_name": target_user.last_name,
        "email": target_user.email,
        "role": _effective_user_role(target_user),
        "is_active": target_user.is_active,
        "is_staff": target_user.is_staff,
    }


def _log_user_management_action(request, action, target_user, message=""):
    SystemAuditLog.objects.create(
        category=SystemAuditLog.Category.USER,
        action=action,
        actor_username=_actor_username(request),
        actor_role=user_role(getattr(request, "user", None)),
        target_username=getattr(target_user, "username", "") or "",
        target_id=getattr(target_user, "id", None),
        client_ip=_client_ip(request),
        request_path=request.path[:255],
        message=message,
    )


def _user_management_queryset(request):
    query = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "").strip()
    status_filter = request.GET.get("status", "").strip()

    users = User.objects.all().order_by("username")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "disabled":
        users = users.filter(is_active=False)

    user_list = list(users.prefetch_related("groups"))
    for item in user_list:
        item.switchmap_role = _effective_user_role(item)
        item.display_name = item.get_full_name() or item.username

    if role_filter:
        user_list = [item for item in user_list if item.switchmap_role == role_filter]

    return user_list, {
        "query": query,
        "role": role_filter,
        "status": status_filter,
    }


def user_management_view(request):
    users, filters = _user_management_queryset(request)
    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    audit_logs = SystemAuditLog.objects.filter(category=SystemAuditLog.Category.USER).order_by("-created_at")[:30]
    for item in audit_logs:
        item.created_at_text = _dt_text(item.created_at)

    return render(
        request,
        "inventory/user_management.html",
        {
            "page_obj": page_obj,
            "query": filters["query"],
            "selected_role": filters["role"],
            "selected_status": filters["status"],
            "role_choices": [ROLE_VIEW_ONLY, ROLE_OPERATOR, ROLE_ADMIN],
            "audit_logs": audit_logs,
        },
    )


def user_create_view(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            target_user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email") or "",
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data.get("first_name") or "",
                last_name=form.cleaned_data.get("last_name") or "",
                is_active=bool(form.cleaned_data.get("is_active")),
            )
            _apply_user_role(target_user, form.cleaned_data.get("role") or ROLE_VIEW_ONLY)
            _log_user_management_action(
                request,
                "user_create",
                target_user,
                f"Created user with role={_effective_user_role(target_user)} active={target_user.is_active}",
            )
            messages.success(request, "User created.")
            return redirect("inventory:user_management")
    else:
        form = UserCreateForm(initial={"role": ROLE_VIEW_ONLY, "is_active": True})

    return render(
        request,
        "inventory/user_form.html",
        {
            "form": form,
            "mode": "create",
            "target_user": None,
        },
    )


def user_edit_view(request, user_id):
    target_user = get_object_or_404(User.objects.prefetch_related("groups"), id=user_id)
    before = {
        "username": target_user.username,
        "first_name": target_user.first_name,
        "last_name": target_user.last_name,
        "email": target_user.email,
        "role": _effective_user_role(target_user),
        "is_active": target_user.is_active,
        "is_staff": target_user.is_staff,
    }

    if request.method == "POST":
        form = UserUpdateForm(request.POST, user_instance=target_user)
        if form.is_valid():
            cleaned = form.cleaned_data
            target_user.username = cleaned["username"]
            target_user.first_name = cleaned.get("first_name") or ""
            target_user.last_name = cleaned.get("last_name") or ""
            target_user.email = cleaned.get("email") or ""
            target_user.is_active = bool(cleaned.get("is_active"))
            target_user.is_staff = bool(cleaned.get("is_staff"))

            if target_user.id == request.user.id:
                target_user.is_active = True
                target_user.is_staff = True

            target_user.save(update_fields=["username", "first_name", "last_name", "email", "is_active", "is_staff"])
            _apply_user_role(target_user, cleaned.get("role") or ROLE_VIEW_ONLY)

            after = {
                "username": target_user.username,
                "first_name": target_user.first_name,
                "last_name": target_user.last_name,
                "email": target_user.email,
                "role": _effective_user_role(target_user),
                "is_active": target_user.is_active,
                "is_staff": target_user.is_staff,
            }
            changed = [f"{key}: {before[key]} -> {after[key]}" for key in before if before[key] != after[key]]
            _log_user_management_action(
                request,
                "user_update",
                target_user,
                "; ".join(changed) or "No visible change.",
            )
            messages.success(request, "User updated.")
            return redirect("inventory:user_management")
    else:
        form = UserUpdateForm(initial=_user_form_initial(target_user), user_instance=target_user)

    return render(
        request,
        "inventory/user_form.html",
        {
            "form": form,
            "mode": "edit",
            "target_user": target_user,
            "effective_role": _effective_user_role(target_user),
        },
    )


def user_password_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = UserPasswordForm(request.POST)
        if form.is_valid():
            target_user.set_password(form.cleaned_data["password1"])
            target_user.save(update_fields=["password"])
            _log_user_management_action(request, "user_password_change", target_user, "Password changed from User Management.")
            messages.success(request, "Password changed.")
            return redirect("inventory:user_management")
    else:
        form = UserPasswordForm()

    return render(
        request,
        "inventory/user_password_form.html",
        {
            "form": form,
            "target_user": target_user,
        },
    )


def _log_system_action(request, action, message=""):
    SystemAuditLog.objects.create(
        category=SystemAuditLog.Category.SYSTEM,
        action=action,
        actor_username=_actor_username(request),
        actor_role=user_role(getattr(request, "user", None)),
        client_ip=_client_ip(request),
        request_path=request.path[:255],
        message=message,
    )


def _switchmap_backup_dir():
    backup_dir = Path(settings.SWITCHMAP_SQLITE_BACKUP_DIR)
    if not backup_dir.is_absolute():
        backup_dir = Path(settings.BASE_DIR) / backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _restore_candidate_dir():
    candidate_dir = _switchmap_backup_dir() / "restore_candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    return candidate_dir


# PHASE99_RESTORE_VALIDATE_SAFETY_GUARD
RESTORE_CANDIDATE_MAX_UPLOAD_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
RESTORE_CANDIDATE_MAX_SQLITE_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_SQLITE_BYTES", 250 * 1024 * 1024))
RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES", 250 * 1024 * 1024))
RESTORE_CANDIDATE_CHUNK_BYTES = 1024 * 1024


def _path_is_under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def _delete_file_quietly(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _safe_backup_filename(filename):
    name = Path(str(filename or "")).name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""):
        raise Http404("Invalid backup filename.")
    if not (name.startswith("switchmap_sqlite_") or name.startswith("restore_candidate_")):
        raise Http404("Invalid backup filename.")
    if not (name.endswith(".zip") or name.endswith(".sqlite3")):
        raise Http404("Invalid backup file type.")
    return name


def _backup_file_path(filename):
    name = _safe_backup_filename(filename)
    backup_dir = _switchmap_backup_dir().resolve()
    candidate_dir = _restore_candidate_dir().resolve()
    candidates = [backup_dir / name, candidate_dir / name]
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        if _path_is_under(path, backup_dir) or _path_is_under(path, candidate_dir):
            return path
    raise Http404("Backup file not found.")


def _file_size_text(size):
    size = int(size or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value = value / 1024
    return f"{size} B"


def _backup_file_info(path, kind="backup"):
    stat = path.stat()
    created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone())
    return {
        "name": path.name,
        "kind": kind,
        "size": stat.st_size,
        "size_text": _file_size_text(stat.st_size),
        "created_at": created,
        "created_at_text": _dt_text(created),
        "is_zip": path.suffix.lower() == ".zip",
        "download_url": reverse("inventory:backup_download", args=[path.name]),
    }


def _list_backup_files():
    backup_dir = _switchmap_backup_dir()
    backup_files = []
    for pattern in ("switchmap_sqlite_*.zip", "switchmap_sqlite_*.sqlite3"):
        for path in backup_dir.glob(pattern):
            if path.is_file():
                backup_files.append(_backup_file_info(path, "backup"))
    backup_files.sort(key=lambda item: item["created_at"], reverse=True)
    return backup_files


def _list_restore_candidates():
    candidate_dir = _restore_candidate_dir()
    candidate_files = []
    for pattern in ("restore_candidate_*.zip", "restore_candidate_*.sqlite3"):
        for path in candidate_dir.glob(pattern):
            if path.is_file():
                candidate_files.append(_backup_file_info(path, "restore_candidate"))
    candidate_files.sort(key=lambda item: item["created_at"], reverse=True)
    return candidate_files[:20]


def _validate_sqlite_file(sqlite_path):
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check;").fetchone()[0]
        if str(integrity).lower() != "ok":
            return False, f"Integrity check failed: {integrity}"
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        table_names = {row[0] for row in rows}
        required = {"auth_user", "inventory_switch", "inventory_port"}
        missing = sorted(required - table_names)
        if missing:
            return False, "Missing required tables: " + ", ".join(missing)
        return True, f"SQLite OK | tables={len(table_names)}"
    finally:
        connection.close()


def _validate_backup_file(path):
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError as exc:
        return False, f"Cannot read candidate file: {exc}"

    if suffix == ".sqlite3":
        if size > RESTORE_CANDIDATE_MAX_SQLITE_BYTES:
            return False, "SQLite candidate is larger than the allowed validation limit."
        return _validate_sqlite_file(path)
    if suffix != ".zip":
        return False, "Only .zip or .sqlite3 is allowed."
    if size > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
        return False, "ZIP candidate is larger than the allowed upload limit."

    temp_name = None
    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            sqlite_infos = [info for info in infos if info.filename.lower().endswith(".sqlite3")]
            if len(sqlite_infos) != 1 or len(infos) != 1:
                return False, f"ZIP must contain only one .sqlite3 file. Found sqlite={len(sqlite_infos)} files={len(infos)}"
            info = sqlite_infos[0]
            member_name = info.filename.replace("\\", "/")
            if member_name.startswith("/") or "../" in member_name or member_name.startswith("../"):
                return False, "ZIP member path is not safe."
            if info.file_size > RESTORE_CANDIDATE_MAX_SQLITE_BYTES or info.file_size > RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES:
                return False, "ZIP SQLite member is larger than the allowed validation limit."
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as temp_file:
                temp_name = temp_file.name
                written = 0
                with archive.open(info) as source:
                    for chunk in iter(lambda: source.read(RESTORE_CANDIDATE_CHUNK_BYTES), b""):
                        written += len(chunk)
                        if written > RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES:
                            return False, "ZIP uncompressed data exceeds the allowed validation limit."
                        temp_file.write(chunk)
        return _validate_sqlite_file(Path(temp_name))
    except zipfile.BadZipFile:
        return False, "Invalid ZIP file."
    finally:
        if temp_name:
            _delete_file_quietly(temp_name)


def backup_center_view(request):
    backup_files = _list_backup_files()
    restore_candidates = _list_restore_candidates()
    db_path = Path(settings.DATABASES["default"]["NAME"])
    db_size = db_path.stat().st_size if db_path.exists() else 0
    backup_total_size = sum(item["size"] for item in backup_files)
    latest_backup = backup_files[0] if backup_files else None
    audit_logs = SystemAuditLog.objects.filter(
        category=SystemAuditLog.Category.SYSTEM
    ).filter(
        Q(action__startswith="backup_") | Q(action__startswith="restore_")
    ).order_by("-created_at")[:30]
    for item in audit_logs:
        item.created_at_text = _dt_text(item.created_at)

    return render(
        request,
        "inventory/backup_center.html",
        {
            "backup_files": backup_files,
            "restore_candidates": restore_candidates,
            "backup_dir": str(_switchmap_backup_dir()),
            "db_path": str(db_path),
            "db_size_text": _file_size_text(db_size),
            "backup_total_size_text": _file_size_text(backup_total_size),
            "latest_backup": latest_backup,
            "retention": getattr(settings, "SWITCHMAP_SQLITE_BACKUP_RETENTION", "-"),
            "audit_logs": audit_logs,
        },
    )


@require_POST
def backup_create_view(request):
    output = StringIO()
    try:
        call_command("backup_sqlite", stdout=output)
    except Exception as exc:
        _log_system_action(request, "backup_create_failed", str(exc))
        messages.error(request, f"Backup failed: {exc}")
        return redirect("inventory:backup_center")

    message = output.getvalue().strip()
    _log_system_action(request, "backup_create", message)
    messages.success(request, message or "Backup created.")
    return redirect("inventory:backup_center")


def backup_download_view(request, filename):
    path = _backup_file_path(filename)
    _log_system_action(request, "backup_download", path.name)
    content_type = "application/zip" if path.suffix.lower() == ".zip" else "application/x-sqlite3"
    response = FileResponse(open(path, "rb"), content_type=content_type, as_attachment=True, filename=path.name)
    response["Content-Length"] = str(path.stat().st_size)
    return response


@require_POST
def backup_validate_restore_view(request):
    upload = request.FILES.get("restore_file")
    if not upload:
        messages.error(request, "Restore candidate file is required.")
        return redirect("inventory:backup_center")

    original_name = Path(upload.name).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".zip", ".sqlite3"}:
        messages.error(request, "Only .zip or .sqlite3 files are allowed.")
        return redirect("inventory:backup_center")

    upload_size = int(getattr(upload, "size", 0) or 0)
    if upload_size > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
        messages.error(request, "Restore candidate rejected: file is larger than the allowed validation limit.")
        _log_system_action(request, "restore_candidate_rejected_size", f"{original_name} | size={upload_size}")
        return redirect("inventory:backup_center")

    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    safe_original = re.sub(r"[^A-Za-z0-9_.-]+", "_", original_name).strip("._") or f"upload{suffix}"
    candidate_name = f"restore_candidate_{timestamp}_{safe_original}"
    candidate_path = _restore_candidate_dir() / candidate_name

    written = 0
    with open(candidate_path, "wb") as destination:
        for chunk in upload.chunks():
            written += len(chunk)
            if written > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
                destination.close()
                _delete_file_quietly(candidate_path)
                messages.error(request, "Restore candidate rejected: file is larger than the allowed validation limit.")
                _log_system_action(request, "restore_candidate_rejected_size", f"{candidate_name} | size>{RESTORE_CANDIDATE_MAX_UPLOAD_BYTES}")
                return redirect("inventory:backup_center")
            destination.write(chunk)

    ok, validation_message = _validate_backup_file(candidate_path)
    action = "restore_candidate_valid" if ok else "restore_candidate_invalid"
    _log_system_action(request, action, f"{candidate_name} | {validation_message}")

    if ok:
        messages.success(request, f"Restore candidate validated. {validation_message}. Restore is NOT executed automatically.")
    else:
        _delete_file_quietly(candidate_path)
        _log_system_action(request, "restore_candidate_invalid_deleted", candidate_name)
        messages.error(request, f"Restore candidate rejected: {validation_message}")
    return redirect("inventory:backup_center")


def _bulk_sensitive_port(port):
    return (
        is_uplink_interface(port.interface_name)
        or port.port_mode == Port.PortMode.TRUNK
        or port.device_type in (Port.DeviceType.UPLINK, Port.DeviceType.SWITCH)
        or bool(port.neighbor_device)
    )


def _bulk_port_queryset(switch, request):
    if request.POST.get("all_ports") == "1":
        return [
            port for port in Port.objects.filter(switch=switch).order_by("display_order", "interface_name")
            if is_visible_switchmap_interface(port.interface_name)
        ]

    raw_ids = request.POST.getlist("port_ids")
    port_ids = []
    for raw_id in raw_ids:
        try:
            port_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    if not port_ids:
        return []

    ports = list(
        Port.objects.filter(switch=switch, id__in=port_ids).order_by("display_order", "interface_name")
    )
    selected = set(port_ids)
    return [
        port for port in ports
        if port.id in selected and is_visible_switchmap_interface(port.interface_name)
    ]


def _bulk_result_payload(results):
    success_count = sum(1 for item in results if item.get("ok"))
    failed_count = len(results) - success_count
    return {
        "success": success_count,
        "failed": failed_count,
        "total": len(results),
        "results": results,
    }


MAX_BULK_SSH_PORTS = 96


def _execute_bulk_ssh_action(request, switch):
    action = (request.POST.get("action") or "").strip()
    value = (request.POST.get("value") or "").strip()
    ssh_username = (request.POST.get("ssh_username") or request.POST.get("username") or switch.ssh_username or "admin").strip()
    ssh_password = request.POST.get("ssh_password") or request.POST.get("password") or ""
    enable_password = request.POST.get("enable_password") or ""
    force = request.POST.get("force") in {"1", "true", "on", "yes"}
    confirmed = request.POST.get("confirmed") in {"1", "true", "on", "yes"}
    bulk_risk_confirmed = request.POST.get("bulk_risk_confirmed") in {"1", "true", "on", "yes"}

    ports = _bulk_port_queryset(switch, request)
    if not ports:
        return _json_error("هیچ پورتی انتخاب نشده است.", status=400)
    if len(ports) > MAX_BULK_SSH_PORTS:
        return _json_error(f"حداکثر تعداد مجاز برای Bulk SSH برابر {MAX_BULK_SSH_PORTS} پورت است.", status=400)

    if not can_run_ssh_action(getattr(request, "user", None), action):
        for port in ports:
            PortActionLog.objects.create(
                port=port,
                switch=switch,
                action=f"bulk_{action or 'unknown'}",
                action_label=f"Bulk SSH - {action_label(action)}",
                value=value,
                ssh_username=ssh_username,
                success=False,
                message="Bulk SSH access denied by role.",
                **_audit_log_context(request, ssh_username),
            )
        return _json_error("این SSH Action برای نقش فعلی مجاز نیست.", status=403)

    if action_requires_confirmation(action) and not confirmed:
        return _json_error("برای این عملیات تأیید نهایی لازم است.", status=400)

    sensitive_ports = [port for port in ports if _bulk_sensitive_port(port)]
    if sensitive_ports and not bulk_risk_confirmed:
        names = ", ".join(port.interface_name for port in sensitive_ports[:10])
        for port in ports:
            PortActionLog.objects.create(
                port=port,
                switch=switch,
                action=f"bulk_{action}",
                action_label=f"Bulk SSH - {action_label(action)}",
                value=value,
                ssh_username=ssh_username,
                success=False,
                message="Bulk SSH stopped: sensitive port confirmation required.",
                **_audit_log_context(request, ssh_username),
            )
        return _json_error(
            f"در انتخاب فعلی پورت حساس وجود دارد: {names}. برای ادامه باید تأیید Bulk روی Uplink / Trunk فعال شود.",
            status=400,
        )

    try:
        bulk_result = run_bulk_port_actions(
            switch=switch,
            ports=ports,
            username=ssh_username,
            password=ssh_password,
            enable_password=enable_password,
            action=action,
            value=value,
            force=force,
        )
    except SshActionError as exc:
        results = []
        for port in ports:
            PortActionLog.objects.create(
                port=port,
                switch=switch,
                action=f"bulk_{action}",
                action_label=f"Bulk SSH - {action_label(action)}",
                value=value,
                ssh_username=ssh_username,
                success=False,
                message=str(exc),
                **_audit_log_context(request, ssh_username),
            )
            results.append({
                "ok": False,
                "port_id": port.id,
                "interface": port.interface_name,
                "message": str(exc),
                "commands": [],
            })
        payload = _bulk_result_payload(results)
        payload.update({"ok": False, "message": str(exc)})
        return JsonResponse(payload, status=400)

    results = bulk_result.get("results", [])
    port_map = {port.id: port for port in ports}
    for item in results:
        port = port_map.get(item.get("port_id"))
        if not port:
            continue
        PortActionLog.objects.create(
            port=port,
            switch=switch,
            action=f"bulk_{action}",
            action_label=f"Bulk SSH - {action_label(action)}",
            value=value,
            ssh_username=ssh_username,
            success=bool(item.get("ok")),
            message=item.get("message") or "",
            commands="\n".join(item.get("commands") or []),
            **_audit_log_context(request, ssh_username),
        )

    _refresh_switch_after_action(switch)

    payload = _bulk_result_payload(results)
    payload.update({
        "ok": payload["failed"] == 0,
        "message": f"Bulk SSH تمام شد. موفق: {payload['success']} | ناموفق: {payload['failed']}",
        "action": action,
        "action_label": action_label(action),
    })
    return JsonResponse(payload, status=200 if payload["ok"] else 207)


def _execute_ssh_action(request):
    form = SSHPortActionForm(request.POST)
    if not form.is_valid():
        return None, _json_error("Form invalid.", status=400, errors=form.errors)

    port = get_object_or_404(
        Port.objects.select_related("switch"),
        id=form.cleaned_data["port_id"],
    )
    switch = port.switch
    action = form.cleaned_data["action"]
    value = form.cleaned_data.get("value") or ""
    ssh_username = form.cleaned_data["ssh_username"]
    ssh_password = form.cleaned_data["ssh_password"]
    enable_password = form.cleaned_data.get("enable_password") or ""
    force = form.cleaned_data.get("force") or False

    if not can_run_ssh_action(getattr(request, "user", None), action):
        PortActionLog.objects.create(
            port=port,
            switch=switch,
            action=action,
            action_label=action_label(action),
            value=value,
            ssh_username=ssh_username,
            success=False,
            message="Access denied by role.",
            **_audit_log_context(request, ssh_username),
        )
        return port, _json_error("این SSH Action برای نقش فعلی مجاز نیست.", status=403)

    try:
        commands = build_port_commands(port=port, action=action, value=value, force=force)
    except SshActionError as exc:
        PortActionLog.objects.create(
            port=port,
            switch=switch,
            action=action,
            action_label=action_label(action),
            value=value,
            ssh_username=ssh_username,
            success=False,
            message=str(exc),
            **_audit_log_context(request, ssh_username),
        )
        return port, _json_error(str(exc), status=400)

    log = PortActionLog.objects.create(
        port=port,
        switch=switch,
        action=action,
        action_label=action_label(action),
        value=value,
        ssh_username=ssh_username,
        success=False,
        commands="\n".join(commands),
        **_audit_log_context(request, ssh_username),
    )

    try:
        result = run_port_action(
            switch=switch,
            port=port,
            username=ssh_username,
            password=ssh_password,
            enable_password=enable_password,
            action=action,
            value=value,
            force=force,
        )
        log.success = True
        log.message = "OK"
        log.commands = "\n".join(result.get("commands", commands))
        log.save(update_fields=["success", "message", "commands"])

        _refresh_switch_after_action(switch)
        port.refresh_from_db()

        return port, JsonResponse(
            {
                "ok": True,
                "message": "عملیات با موفقیت انجام شد.",
                "action": action,
                "action_label": action_label(action),
                "value": value,
                "commands": result.get("commands", commands),
                "port": _port_payload(port),
            }
        )
    except SshActionError as exc:
        log.success = False
        log.message = str(exc)
        log.save(update_fields=["success", "message"])
        return port, _json_error(
            f"SSH ACTION FAILED | {switch.name} | {port.interface_name} | {exc}",
            status=400,
        )


def port_ssh_action(request):
    if request.method != "POST":
        return _json_error("POST required.", status=405)
    _, response = _execute_ssh_action(request)
    return response


def switch_bulk_ssh_action(request, switch_id):
    if request.method != "POST":
        return _json_error("POST required.", status=405)
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    return _execute_bulk_ssh_action(request, switch)



def _parse_multi_ssh_action_items(request, port):
    raw = request.POST.get("actions_json") or request.POST.get("multi_actions") or ""
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError as exc:
        raise SshActionError("فرمت Multi Action نامعتبر است.") from exc
    if not isinstance(items, list):
        raise SshActionError("فرمت Multi Action نامعتبر است.")

    parsed = []
    seen = set()
    global_force = request.POST.get("force") in {"1", "true", "on", "yes"}
    confirmed = request.POST.get("confirmed") in {"1", "true", "on", "yes"}

    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip()
        value = str(item.get("value") or "").strip()
        key = (action, value)
        if not action or key in seen:
            continue
        seen.add(key)
        if not can_run_ssh_action(getattr(request, "user", None), action):
            raise SshActionError(f"Action مجاز نیست: {action_label(action)}")
        if action_requires_force(action, port) and not global_force:
            raise SshActionError(f"برای {action_label(action)} تیک اجازه تغییر روی Trunk/Uplink لازم است.")
        if action_requires_confirmation(action) and not confirmed:
            raise SshActionError(f"برای {action_label(action)} تأیید نهایی لازم است.")
        parsed.append({"action": action, "value": value, "force": global_force})

    if not parsed:
        raise SshActionError("هیچ Action معتبری انتخاب نشده است.")
    if len(parsed) > 6:
        raise SshActionError("حداکثر 6 Action در یک اجرا مجاز است.")
    return parsed


def switchmap_ajax_multi_ssh_port_action(request):
    if request.method != "POST":
        return _json_error("فقط POST مجاز است.", status=405)

    port_id = request.POST.get("port_id")
    ssh_username = (request.POST.get("ssh_username") or request.POST.get("username") or "").strip()
    ssh_password = request.POST.get("ssh_password") or request.POST.get("password") or ""
    enable_password = request.POST.get("enable_password") or ""

    if not port_id:
        return _json_error("ابتدا پورت را انتخاب کن.", status=400)
    if not ssh_username or not ssh_password:
        return _json_error("Username و Password لازم است.", status=400)

    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    switch = port.switch

    try:
        action_items = _parse_multi_ssh_action_items(request, port)
        result = run_port_multi_actions(
            switch=switch,
            port=port,
            username=ssh_username,
            password=ssh_password,
            enable_password=enable_password,
            action_items=action_items,
            force=request.POST.get("force") in {"1", "true", "on", "yes"},
        )
    except SshActionError as exc:
        PortActionLog.objects.create(
            port=port,
            switch=switch,
            action="multi_ssh_action",
            action_label="Multi SSH Action",
            value="",
            ssh_username=ssh_username,
            success=False,
            message=str(exc),
            **_audit_log_context(request, ssh_username),
        )
        return _json_error(str(exc), status=400)

    labels = [item.get("label") or action_label(item.get("action")) for item in result.get("items", [])]
    commands = result.get("commands", [])

    PortActionLog.objects.create(
        port=port,
        switch=switch,
        action="multi_ssh_action",
        action_label="Multi SSH Action",
        value=" | ".join(labels),
        ssh_username=ssh_username,
        success=True,
        message=f"OK | {len(labels)} action(s)",
        commands="\n".join(commands),
        **_audit_log_context(request, ssh_username),
    )

    _refresh_switch_after_action(switch)
    port.refresh_from_db()

    return JsonResponse({
        "ok": True,
        "message": f"Multi SSH با موفقیت انجام شد. تعداد: {len(labels)}",
        "action": "multi_ssh_action",
        "action_label": "Multi SSH Action",
        "actions": result.get("items", []),
        "commands": commands,
        "port": _port_payload(port),
    })

def switchmap_ajax_ssh_port_action(request):
    if request.method != "POST":
        return _json_error("فقط POST مجاز است.", status=405)
    _, response = _execute_ssh_action(request)
    return response


@require_POST
def ssh_action_preview(request):
    port_id = request.POST.get("port_id")
    action = request.POST.get("action")
    value = request.POST.get("value") or ""
    force = request.POST.get("force") in {"1", "true", "on", "yes"}

    if not port_id:
        return _json_error("ابتدا پورت را انتخاب کن.")

    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    if not can_run_ssh_action(getattr(request, "user", None), action):
        return _json_error("این SSH Action برای نقش فعلی مجاز نیست.", status=403)
    try:
        commands = build_port_commands(port=port, action=action, value=value, force=force)
    except SshActionError as exc:
        return _json_error(str(exc), status=400)

    return JsonResponse(
        {
            "ok": True,
            "commands": commands,
            "requires_force": action_requires_force(action, port),
            "requires_confirmation": action_requires_confirmation(action),
            "risk": action_risk_text(action),
        }
    )


def port_payload_json(request, port_id):
    port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
    return JsonResponse({"ok": True, "port": _port_payload(port)})


def _normalize_name(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = value.split(".")[0] if "." in value and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", value) else value
    value = re.sub(r"[^a-z0-9آ-ی]+", "", value)
    return value


def _topology_switch_aliases(switch):
    aliases = set()
    base_values = [
        switch.name or "",
        str(switch.management_ip or ""),
        switch.model or "",
    ]
    for value in base_values:
        normalized = _normalize_name(value)
        if normalized:
            aliases.add(normalized)

    text = " ".join(base_values).lower()
    if any(token in text for token in ("nexus", "n3k", "n5k", "n7k", "n9k")):
        aliases.update({"nexus", "n3kcore", "n3kcoresw", "coresw"})
    if any(token in text for token in ("rb5009", "routeros", "mikrotik")):
        aliases.update({"rb5009", "mikrotik", "routeros"})
    if any(token in text for token in ("crs354", "crs")):
        aliases.update({"crs354", "crs", "coreswitch"})
    if any(token in text for token in ("rb2011", "iranmall")):
        aliases.update({"rb2011", "iranmall", "rb2011iranmall"})
    if any(token in text for token in ("hex", "hex-s", "hexs")):
        aliases.update({"hexs", "hex", "edge"})
    if any(token in text for token in ("alihome", "ali-home")):
        aliases.update({"alihome", "alihomehap", "alihomerouter"})
    if "ax3" in text or "karaj" in text:
        aliases.update({"ax3", "ax3karaj", "karaj"})
    if "cap" in text or "access point" in text:
        aliases.update({_normalize_name(switch.name), _normalize_name((switch.name or "").replace("-", ""))})
    if "edari" in text:
        aliases.add(_normalize_name((switch.name or "").replace("edari", "edari-")))
    return {alias for alias in aliases if len(alias) >= 3}


def _build_topology_alias_lookup(switches):
    alias_lookup = {}
    ambiguous_aliases = set()
    for switch in switches:
        for alias in _topology_switch_aliases(switch):
            if alias in alias_lookup and alias_lookup[alias].id != switch.id:
                ambiguous_aliases.add(alias)
                continue
            alias_lookup[alias] = switch
    for alias in ambiguous_aliases:
        alias_lookup.pop(alias, None)
    return alias_lookup


def _topology_name_overlaps(left, right, min_length=5):
    left = str(left or "")
    right = str(right or "")
    if not left or not right:
        return False
    if left == right:
        return True
    return len(left) >= min_length and len(right) >= min_length and (left in right or right in left)


def _topology_report_matches_source(source_key, neighbor_key, min_length=5):
    source_key = str(source_key or "")
    neighbor_key = str(neighbor_key or "")
    if not source_key or not neighbor_key:
        return False
    if source_key == neighbor_key:
        return True
    return len(source_key) >= min_length and len(neighbor_key) >= min_length and source_key in neighbor_key


def _switch_has_reciprocal_topology_link(candidate_switch, source_port):
    source_keys = {_normalize_name(source_port.switch.name)}
    source_keys.update(_topology_switch_aliases(source_port.switch))
    source_keys = {key for key in source_keys if key}
    if not source_keys:
        return False

    source_interface = _normalize_interface(source_port.interface_name)
    for candidate_port in candidate_switch.ports.all():
        neighbor_key = _normalize_name(candidate_port.neighbor_device)
        if not neighbor_key:
            continue
        if any(_topology_report_matches_source(source_key, neighbor_key) for source_key in source_keys):
            candidate_neighbor_interface = _normalize_interface(candidate_port.neighbor_port)
            if not source_interface or not candidate_neighbor_interface or candidate_neighbor_interface == source_interface:
                return True
    return False


def _find_reciprocal_alias_switch(port, switches, neighbor_key):
    matches = []
    for candidate_switch in switches:
        if candidate_switch.id == port.switch_id:
            continue
        candidate_aliases = _topology_switch_aliases(candidate_switch)
        if neighbor_key in candidate_aliases or any(_topology_name_overlaps(alias, neighbor_key) for alias in candidate_aliases):
            if _switch_has_reciprocal_topology_link(candidate_switch, port):
                matches.append(candidate_switch)

    if len(matches) == 1:
        return matches[0]
    return None


def _normalize_interface(value):
    value = str(value or "").strip()
    replacements = [
        (r"^GigabitEthernet", "Gi"),
        (r"^TenGigabitEthernet", "Te"),
        (r"^FastEthernet", "Fa"),
        (r"^FortyGigabitEthernet", "Fo"),
        (r"^TwentyFiveGigE", "Twe"),
        (r"^TwoGigabitEthernet", "Tw"),
        (r"^Ethernet", "Eth"),
    ]
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", value)


def _topology_role_for_port(port):
    if is_uplink_interface(port.interface_name):
        return "uplink"
    if port.port_mode == Port.PortMode.TRUNK:
        return "uplink"
    if port.device_type in (Port.DeviceType.SWITCH, Port.DeviceType.UPLINK):
        return "uplink"
    if port.neighbor_source in ("CDP", "LLDP") or port.neighbor_device:
        return "neighbor"
    return "access"


def _topology_port_state(port):
    if not port:
        return "unknown", "Unknown"

    admin_state = str(port.snmp_admin_status or "").strip().lower()
    oper_state = str(port.snmp_oper_status or "").strip().lower()
    text = " ".join([
        str(port.status or ""),
        admin_state,
        oper_state,
        str(port.description or ""),
        str(port.snmp_alias or ""),
    ]).lower()

    if "err" in text or "fault" in text or port.status == Port.Status.ERROR:
        return "down", "Error"
    if port.status in (Port.Status.DOWN, Port.Status.DISABLED):
        return "down", port.get_status_display()
    if oper_state and oper_state not in ("1", "up", "operational", "connected"):
        return "down", port.get_status_display()
    if admin_state in ("2", "down", "disabled"):
        return "down", "Admin Down"
    return "up", port.get_status_display()


def _topology_link_health(source_port, matched_switch=None, matched_port=None):
    source_state, source_label = _topology_port_state(source_port)
    target_state, target_label = _topology_port_state(matched_port)

    if source_state == "down" or target_state == "down":
        return "down", "Down / Error"
    if not matched_switch:
        return "warning", "Unknown"
    if matched_switch and not matched_port:
        return "warning", "One-way"
    if source_state == "up" and target_state == "up":
        return "up", "Up"
    return "warning", source_label or target_label or "Check"


def _topology_role_group_from_switch(switch):
    role = getattr(switch, "device_role", "") or ""
    family = getattr(switch, "device_family", "") or ""
    vendor = getattr(switch, "vendor", "") or ""

    if role in (Switch.DeviceRole.CORE_ROUTER, Switch.DeviceRole.CORE_SWITCH, Switch.DeviceRole.DISTRIBUTION):
        return "core", switch.get_device_role_display()
    if role == Switch.DeviceRole.EDGE_ROUTER:
        return "edge", "Edge Router"
    if role == Switch.DeviceRole.REMOTE_OFFICE:
        return "remote", "Remote Office"
    if role == Switch.DeviceRole.ACCESS_POINT:
        return "wireless", "Access Point"
    if role == Switch.DeviceRole.ACCESS_SWITCH:
        return "access", "Access Switch"
    if family == Switch.DeviceFamily.MIKROTIK_SWITCH:
        return "core", "Core Switch"
    if family == Switch.DeviceFamily.MIKROTIK_AP:
        return "wireless", "Access Point"
    if vendor == Switch.Vendor.MIKROTIK:
        return "edge", "MikroTik Router"
    return "unknown", "Unknown"


def _topology_switch_role(switch, ports, internal_switch_ids):
    explicit_key, explicit_label = _topology_role_group_from_switch(switch)
    if explicit_key != "unknown":
        return explicit_key, explicit_label

    text = " ".join([
        switch.name or "",
        switch.model or "",
        switch.location or "",
    ]).lower()
    uplink_count = sum(1 for port in ports if _topology_role_for_port(port) == "uplink")
    access_count = sum(1 for port in ports if _topology_role_for_port(port) == "access")

    if any(token in text for token in ("core", "nexus", "n3k", "n5k", "n7k", "n9k", "distribution")):
        return "core", "Core / Distribution"
    if any(token in text for token in ("access", "edari", "3850", "2960", "catalyst")):
        return "access", "Access"
    if switch.id in internal_switch_ids and uplink_count >= 2:
        return "core", "Core / Distribution"
    if access_count >= uplink_count:
        return "access", "Access"
    return "unknown", "Unknown"


def _find_matched_switch(port, switches, switch_lookup, ip_lookup, alias_lookup=None):
    if port.neighbor_ip:
        matched = ip_lookup.get(str(port.neighbor_ip))
        if matched:
            return matched, "ip"

    neighbor_key = _normalize_name(port.neighbor_device)
    if not neighbor_key:
        return None, "none"

    alias_lookup = alias_lookup or {}
    matched = alias_lookup.get(neighbor_key)
    if matched:
        return matched, "alias"

    matched = _find_reciprocal_alias_switch(port, switches, neighbor_key)
    if matched:
        return matched, "partial-alias"

    for switch_key, candidate_switch in switch_lookup.items():
        if not switch_key:
            continue
        if switch_key == neighbor_key:
            return candidate_switch, "name"
        if _topology_name_overlaps(switch_key, neighbor_key):
            return candidate_switch, "partial-name"

    for alias, candidate_switch in alias_lookup.items():
        if _topology_name_overlaps(alias, neighbor_key):
            return candidate_switch, "partial-alias"

    return None, "none"


def _find_matched_port(source_port, matched_switch):
    if not matched_switch:
        return None

    wanted_interface = _normalize_interface(source_port.neighbor_port)
    if wanted_interface:
        for candidate in matched_switch.ports.all():
            if _normalize_interface(candidate.interface_name) == wanted_interface:
                return candidate

    source_switch_key = _normalize_name(source_port.switch.name)
    source_interface = _normalize_interface(source_port.interface_name)
    for candidate in matched_switch.ports.all():
        if _normalize_name(candidate.neighbor_device) == source_switch_key:
            if not source_interface or _normalize_interface(candidate.neighbor_port) == source_interface:
                return candidate

    return None


def _topology_link_key(source_port, matched_switch, matched_port):
    if matched_switch and matched_port:
        return tuple(sorted((source_port.id, matched_port.id)))
    if matched_switch:
        return (
            "matched",
            min(source_port.switch_id, matched_switch.id),
            max(source_port.switch_id, matched_switch.id),
            _normalize_interface(source_port.interface_name),
            _normalize_interface(source_port.neighbor_port),
        )
    return ("external", source_port.id)


def _topology_sort_key_for_link(link):
    return (
        link.get("health") != "down",
        link.get("health") != "warning",
        str(link.get("source_switch")),
        str(link.get("source_port")),
    )


def _build_topology_payload():
    switches = list(
        Switch.objects.filter(is_active=True)
        .prefetch_related(VISIBLE_PORT_PREFETCH)
        .order_by("topology_position", "name")
    )
    switch_lookup = {_normalize_name(switch.name): switch for switch in switches}
    alias_lookup = _build_topology_alias_lookup(switches)
    ip_lookup = {str(switch.management_ip): switch for switch in switches}

    neighbor_ports = [
        port for port in Port.objects.select_related("switch")
        .exclude(neighbor_device="")
        .filter(switch__is_active=True)
        .order_by("switch__name", "display_order", "interface_name")
        if is_visible_switchmap_interface(port.interface_name)
    ]

    links = []
    duplicate_links = []
    seen_keys = set()
    internal_switch_ids = set()
    unknown_neighbor_names = set()

    for port in neighbor_ports:
        matched_switch, matched_by = _find_matched_switch(port, switches, switch_lookup, ip_lookup, alias_lookup)
        matched_port = _find_matched_port(port, matched_switch)
        link_key = _topology_link_key(port, matched_switch, matched_port)
        if link_key in seen_keys:
            duplicate_links.append(port)
            continue
        seen_keys.add(link_key)

        is_internal = bool(matched_switch)
        role = _topology_role_for_port(port)
        edge_info = classify_edge(port, matched_switch, matched_port, matched_by)
        health = edge_info.get("health", "unknown")
        health_label = edge_info.get("health_label", "Unknown")

        if is_internal:
            internal_switch_ids.add(port.switch_id)
            internal_switch_ids.add(matched_switch.id)
        else:
            unknown_neighbor_names.add(port.neighbor_device or "Unknown")

        links.append(
            {
                "source_switch": port.switch,
                "source_port": port,
                "source_role": role,
                "neighbor_device": port.neighbor_device,
                "neighbor_port": port.neighbor_port,
                "neighbor_source": port.neighbor_source,
                "neighbor_ip": port.neighbor_ip,
                "matched_switch": matched_switch,
                "matched_port": matched_port,
                "matched_by": matched_by,
                "mac_count": port.mac_count,
                "is_internal": is_internal,
                "state": "internal" if is_internal else "external",
                "is_uplink": role == "uplink",
                "direction": "two-way" if matched_port and matched_port.neighbor_device else "one-way",
                "health": health,
                "health_label": health_label,
                "edge_id": edge_info.get("edge_id"),
                "confidence": edge_info.get("confidence"),
                "severity": edge_info.get("severity"),
                "reason": edge_info.get("reason"),
                "evidence": edge_info.get("evidence", []),
                "evidence_count": edge_info.get("evidence_count", 0),
                "parent_down": edge_info.get("parent_down", False),
                "first_seen": edge_info.get("first_seen"),
                "last_seen": edge_info.get("last_seen"),
                "source_state": edge_info.get("source_state"),
                "target_state": edge_info.get("target_state"),
                "detail_url": edge_info.get("detail_url"),
            }
        )

    uplinks_without_neighbor = []
    for switch in switches:
        for port in switch.ports.all():
            if not is_visible_switchmap_interface(port.interface_name):
                continue
            if _topology_role_for_port(port) == "uplink" and not port.neighbor_device and topology_alarm_should_exist(port):
                uplinks_without_neighbor.append(port)

    nodes = []
    role_groups = {
        "core": {"key": "core", "title": "Core", "nodes": []},
        "edge": {"key": "edge", "title": "Edge Routers", "nodes": []},
        "remote": {"key": "remote", "title": "Remote Office", "nodes": []},
        "wireless": {"key": "wireless", "title": "Wireless / AP", "nodes": []},
        "access": {"key": "access", "title": "Access Switches", "nodes": []},
        "unknown": {"key": "unknown", "title": "Unknown", "nodes": []},
    }

    for index, switch in enumerate(switches):
        ports = list(switch.ports.all())
        visible_ports = [port for port in ports if is_visible_switchmap_interface(port.interface_name)]
        neighbor_count = sum(1 for port in visible_ports if port.neighbor_device)
        uplink_count = sum(1 for port in visible_ports if _topology_role_for_port(port) == "uplink")
        link_count = sum(
            1 for link in links
            if link["source_switch"].id == switch.id or (link["matched_switch"] and link["matched_switch"].id == switch.id)
        )
        role_key, role_label = _topology_switch_role(switch, visible_ports, internal_switch_ids)
        node = {
            "switch": switch,
            "index": index,
            "role_key": role_key,
            "role_label": role_label,
            "neighbor_count": neighbor_count,
            "uplink_count": uplink_count,
            "link_count": link_count,
            "visible_port_count": len(visible_ports),
            "has_internal_link": switch.id in internal_switch_ids,
            "is_isolated": link_count == 0,
        }
        nodes.append(node)
        if role_key not in role_groups:
            role_key = "unknown"
            node["role_key"] = role_key
            node["role_label"] = "Unknown"
        role_groups[role_key]["nodes"].append(node)

    internal_links = sorted([link for link in links if link["is_internal"]], key=_topology_sort_key_for_link)
    external_links = sorted([link for link in links if not link["is_internal"]], key=_topology_sort_key_for_link)

    topology_map = {
        "core_nodes": role_groups["core"]["nodes"],
        "edge_nodes": role_groups["edge"]["nodes"],
        "remote_nodes": role_groups["remote"]["nodes"],
        "wireless_nodes": role_groups["wireless"]["nodes"],
        "access_nodes": role_groups["access"]["nodes"],
        "unknown_nodes": role_groups["unknown"]["nodes"],
        "links": internal_links[:80],
    }

    topology_groups = [
        role_groups["core"],
        role_groups["edge"],
        role_groups["remote"],
        role_groups["wireless"],
        role_groups["access"],
        role_groups["unknown"],
    ]

    return {
        "switches": switches,
        "topology_nodes": nodes,
        "topology_groups": topology_groups,
        "topology_map": topology_map,
        "links": links,
        "internal_links": internal_links,
        "external_links": external_links,
        "uplinks_without_neighbor": uplinks_without_neighbor,
        "duplicate_links": duplicate_links,
        "switch_count": len(switches),
        "link_count": len(links),
        "matched_link_count": len(internal_links),
        "external_link_count": len(external_links),
        "unknown_uplink_count": len(uplinks_without_neighbor),
        "unknown_neighbor_count": len(unknown_neighbor_names),
        "duplicate_link_count": len(duplicate_links),
        "down_link_count": sum(1 for link in links if link["health"] == "down" and edge_warning_allowed(link)),
        "warning_link_count": sum(1 for link in links if edge_warning_allowed(link) and link["health"] != "down"),
        "up_link_count": sum(1 for link in links if link["health"] == "up"),
        "confirmed_link_count": sum(1 for link in links if link.get("confidence") == "confirmed"),
        "partial_link_count": sum(1 for link in links if link.get("confidence") == "partial"),
        "inferred_link_count": sum(1 for link in links if link.get("confidence") == "inferred"),
        "stale_link_count": sum(1 for link in links if link.get("confidence") == "stale"),
        "suppressed_link_count": sum(1 for link in links if link.get("parent_down")),
    }

def topology_view(request):
    payload = _build_topology_payload()
    return render(request, "inventory/topology.html", payload)


def topology_edge_detail_view(request, port_id):
    payload = _build_topology_payload()
    edge = None
    for item in payload.get("links", []):
        source_port = item.get("source_port")
        if source_port and source_port.id == port_id:
            edge = item
            break
    if not edge:
        port = get_object_or_404(Port.objects.select_related("switch"), id=port_id)
        matched_switch = None
        matched_port = None
        edge_info = classify_edge(port, matched_switch, matched_port, "no-neighbor")
        edge = {
            "source_switch": port.switch,
            "source_port": port,
            "matched_switch": None,
            "matched_port": None,
            "matched_by": "no-neighbor",
            "neighbor_device": port.neighbor_device,
            "neighbor_port": port.neighbor_port,
            "neighbor_source": port.neighbor_source,
            "neighbor_ip": port.neighbor_ip,
            **edge_info,
        }
    return render(request, "inventory/topology_edge_detail.html", {"edge": edge, "phase81_83_topology_drilldown": True})

def reports_view(request):
    switches = Switch.objects.filter(is_active=True).order_by("name")
    base_ports = Port.objects.select_related("switch").filter(switch__is_active=True)
    visible_ids = [
        port.id for port in base_ports
        if is_visible_switchmap_interface(port.interface_name)
    ]
    visible_ports = Port.objects.select_related("switch").filter(id__in=visible_ids)

    free_ports = visible_ports.filter(
        status=Port.Status.DOWN,
        connected_device="",
        neighbor_device="",
        mac_count=0,
    ).order_by("switch__name", "display_order")

    active_undocumented_ports = visible_ports.filter(
        status=Port.Status.UP,
        connected_device="",
        owner="",
        description="",
        neighbor_device="",
    ).order_by("switch__name", "display_order")

    neighbor_ports = visible_ports.exclude(neighbor_device="").order_by("switch__name", "display_order")
    mac_ports = visible_ports.filter(mac_count__gt=0).order_by("switch__name", "display_order")
    multi_mac_ports = visible_ports.filter(mac_count__gt=1).order_by("switch__name", "display_order")
    trunk_ports = visible_ports.filter(port_mode=Port.PortMode.TRUNK).order_by("switch__name", "display_order")
    poe_ports = visible_ports.filter(poe_enabled=True).order_by("switch__name", "display_order")
    error_ports = visible_ports.filter(status=Port.Status.ERROR).order_by("switch__name", "display_order")

    return render(
        request,
        "inventory/reports.html",
        {
            "switches": switches,
            "free_ports": free_ports,
            "active_undocumented_ports": active_undocumented_ports,
            "neighbor_ports": neighbor_ports,
            "mac_ports": mac_ports,
            "multi_mac_ports": multi_mac_ports,
            "trunk_ports": trunk_ports,
            "poe_ports": poe_ports,
            "error_ports": error_ports,
        },
    )


CISCO_SEVERITY_CHOICES = [
    (0, "Emergency"),
    (1, "Alert"),
    (2, "Critical"),
    (3, "Error"),
    (4, "Warning"),
    (5, "Notification"),
    (6, "Informational"),
    (7, "Debug"),
]


CISCO_SAMPLE_LOG_TEXT = """*Jun 22 07:11:14.123: %LINK-3-UPDOWN: Interface Gi1/0/1, changed state to up
*Jun 22 07:11:16.456: %LINEPROTO-5-UPDOWN: Line protocol on Interface Gi1/0/1, changed state to up
*Jun 22 07:12:01.000: %SYS-5-CONFIG_I: Configured from console by admin on vty0
*Jun 22 07:13:10.000: %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: admin] [Source: 192.168.0.10] [localport: 22] at 07:13:10 UTC Mon Jun 22 2026
*Jun 22 07:14:20.000: %ILPOWER-7-DETECT: Interface Gi1/0/2: Power Device detected: IEEE PD
*Jun 22 07:15:30.000: %SPANTREE-2-BLOCK_BPDUGUARD: Received BPDU on port Gi1/0/3 with BPDU Guard enabled. Disabling port."""

CISCO_SYSLOG_RE = re.compile(
    r"^(?P<prefix>.*?)(?:%)(?P<facility>[A-Z0-9_./-]+)-(?P<severity>[0-7])-(?P<mnemonic>[A-Z0-9_./-]+):\s*(?P<message>.*)$",
    re.IGNORECASE,
)

CISCO_INTERFACE_RE = re.compile(
    r"(?:Interface|interface|on Interface|on interface)\s+([A-Za-z]+[A-Za-z0-9/.:_-]+)",
    re.IGNORECASE,
)


def _category_label_map():
    return dict(CiscoSyslogEntry.CATEGORY_CHOICES)


def _severity_name(value):
    try:
        return dict(CISCO_SEVERITY_CHOICES).get(int(value), "")
    except (TypeError, ValueError):
        return ""


def _guess_cisco_log_category(facility, mnemonic, message):
    text = " ".join([facility or "", mnemonic or "", message or ""]).upper()

    if any(key in text for key in ("SEC", "LOGIN", "AAA", "AUTH", "RADIUS", "TACACS", "PORT_SECURITY", "PSECURE")):
        return "security"
    if any(key in text for key in ("CONFIG", "CONFIG_I", "PARSER", "SYS-5-CONFIG")):
        return "config"
    if any(key in text for key in ("SPANTREE", "STP", "LOOP", "ROOT", "BPDU", "UDLD")):
        return "stp"
    if any(key in text for key in ("VLAN", "TRUNK", "VTP", "DTP")):
        return "vlan"
    if any(key in text for key in ("ILPOWER", "POE", "POWER", "PWR")):
        return "poe"
    if any(key in text for key in ("ENV", "FAN", "TEMP", "TEMPERATURE", "SUPPLY", "PSU")):
        return "environment"
    if any(key in text for key in ("STACK", "SWITCH_NUMBER", "MODULE", "PLATFORM", "HARDWARE")):
        return "stack"
    if any(key in text for key in ("OSPF", "EIGRP", "BGP", "ROUTE", "HSRP", "VRRP", "GLBP")):
        return "routing"
    if any(key in text for key in ("CDP", "LLDP", "SNMP")):
        return "protocol"
    if any(key in text for key in ("DHCP", "IP-", "ARP", "DUPADDR")):
        return "dhcp"
    if any(key in text for key in ("LINK", "LINEPROTO", "IF", "PORT", "ETHER", "GBIC", "SFP")):
        return "interface"
    if any(key in text for key in ("SYS", "CLOCK", "NTP", "RELOAD", "BOOT")):
        return "system"
    return "other"


def _extract_cisco_interface(message):
    match = CISCO_INTERFACE_RE.search(message or "")
    if not match:
        return ""
    return match.group(1).strip().rstrip(",")


def _parse_cisco_syslog_line(raw_line):
    clean = (raw_line or "").strip()
    if not clean:
        return None

    clean_without_priority = re.sub(r"^<\d+>", "", clean).strip()
    match = CISCO_SYSLOG_RE.match(clean_without_priority)
    if not match:
        return {
            "event_time_text": "",
            "facility": "",
            "severity": None,
            "severity_name": "",
            "mnemonic": "",
            "category": "other",
            "interface_name": "",
            "message": clean_without_priority,
            "raw_line": clean,
            "is_parsed": False,
        }

    facility = match.group("facility").upper()
    severity = int(match.group("severity"))
    mnemonic = match.group("mnemonic").upper()
    message = match.group("message").strip()
    prefix = match.group("prefix").strip(" :*")

    return {
        "event_time_text": prefix,
        "facility": facility,
        "severity": severity,
        "severity_name": _severity_name(severity),
        "mnemonic": mnemonic,
        "category": _guess_cisco_log_category(facility, mnemonic, message),
        "interface_name": _extract_cisco_interface(message),
        "message": message,
        "raw_line": clean,
        "is_parsed": True,
    }



def _store_cisco_syslog_lines(switch, source_ip, raw_text, skip_non_syslog=False, dedupe=False):
    counters = {
        "imported": 0,
        "parsed": 0,
        "unparsed": 0,
        "skipped": 0,
        "duplicates": 0,
        "candidates": 0,
        "lines": 0,
    }

    for raw_line in str(raw_text or "").splitlines():
        counters["lines"] += 1
        if not raw_line.strip():
            counters["skipped"] += 1
            continue
        if skip_non_syslog and "%" not in raw_line:
            counters["skipped"] += 1
            continue

        parsed = _parse_cisco_syslog_line(raw_line)
        if not parsed:
            counters["skipped"] += 1
            continue

        counters["candidates"] += 1
        raw_value = parsed.get("raw_line") or raw_line.strip()
        duplicate_filter = CiscoSyslogEntry.objects.filter(raw_line=raw_value)
        if switch is not None:
            duplicate_filter = duplicate_filter.filter(switch=switch)
        elif source_ip:
            duplicate_filter = duplicate_filter.filter(source_ip=source_ip)

        if dedupe and duplicate_filter.exists():
            counters["duplicates"] += 1
            continue

        CiscoSyslogEntry.objects.create(
            switch=switch,
            source_ip=source_ip,
            **parsed,
        )
        counters["imported"] += 1
        if parsed.get("is_parsed"):
            counters["parsed"] += 1
        else:
            counters["unparsed"] += 1

    return counters

def _cisco_syslog_queryset(request):
    logs = CiscoSyslogEntry.objects.select_related("switch").order_by("-received_at")
    query = request.GET.get("cq", "").strip()
    switch_id = request.GET.get("c_switch", "").strip()
    severity = request.GET.get("severity", "").strip()
    category = request.GET.get("category", "").strip()
    facility = request.GET.get("facility", "").strip()
    date_from = request.GET.get("c_date_from", "").strip()
    date_to = request.GET.get("c_date_to", "").strip()

    if query:
        logs = logs.filter(
            Q(switch__name__icontains=query)
            | Q(source_ip__icontains=query)
            | Q(facility__icontains=query)
            | Q(mnemonic__icontains=query)
            | Q(category__icontains=query)
            | Q(interface_name__icontains=query)
            | Q(message__icontains=query)
            | Q(raw_line__icontains=query)
        )
    if switch_id:
        logs = logs.filter(switch_id=switch_id)
    if severity != "":
        try:
            logs = logs.filter(severity=int(severity))
        except ValueError:
            pass
    if category:
        logs = logs.filter(category=category)
    if facility:
        logs = logs.filter(facility=facility)

    date_from_obj = parse_date(date_from) if date_from else None
    if date_from_obj:
        start_dt = timezone.make_aware(datetime.combine(date_from_obj, time.min), IRAN_TZ)
        logs = logs.filter(received_at__gte=start_dt)

    date_to_obj = parse_date(date_to) if date_to else None
    if date_to_obj:
        end_dt = timezone.make_aware(datetime.combine(date_to_obj, time.max), IRAN_TZ)
        logs = logs.filter(received_at__lte=end_dt)

    filters = {
        "query": query,
        "switch_id": switch_id,
        "severity": severity,
        "category": category,
        "facility": facility,
        "date_from": date_from,
        "date_to": date_to,
    }
    return logs, filters


def _cisco_logs_filter_querystring(request):
    querydict = request.GET.copy()
    querydict.pop("c_page", None)
    return querydict.urlencode()



SFP_STATUS_RE = re.compile(
    r"^\s*(?P<iface>[A-Za-z]+\d+/\d+/\d+)\s+(?P<name>.*?)\s+(?P<status>connected|notconnect|disabled|err-disabled|inactive|suspended|monitoring|up|down)\s+(?P<vlan>\S+)\s+(?P<duplex>\S+)\s+(?P<speed>\S+)\s*(?P<type>.*)$",
    re.IGNORECASE,
)
SFP_COUNTER_IFACE_RE = re.compile(r"^\s*(?P<iface>[A-Za-z]+\d+/\d+/\d+)\s+(?P<values>[\d\s]+)\s*$")
SFP_TRANSCEIVER_RE = re.compile(
    r"^\s*(?P<iface>[A-Za-z]+\d+/\d+/\d+)\s+"
    r"(?P<temp>-?\d+(?:\.\d+)?)\s+"
    r"(?P<volt>-?\d+(?:\.\d+)?)\s+"
    r"(?P<current>-?\d+(?:\.\d+)?)\s+"
    r"(?P<tx>-?\d+(?:\.\d+)?)\s+"
    r"(?P<rx>-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
SFP_INTERFACE_RE = re.compile(r"^(?:Te\d+/1/[1-4]|Gi\d+/1/[1-4])$", re.IGNORECASE)


SFP_SHOW_COMMANDS = [
    "show interfaces status",
    "show interfaces counters errors",
    "show interfaces transceiver detail",
]

SFP_HISTORY_KEEP = 20
SFP_RX_POWER_MIN_DBM = Decimal("-18.00")
SFP_RX_POWER_MAX_DBM = Decimal("2.00")
SFP_TX_POWER_MIN_DBM = Decimal("-15.00")
SFP_TX_POWER_MAX_DBM = Decimal("3.00")
SFP_TEMP_MIN_C = Decimal("0.00")
SFP_TEMP_MAX_C = Decimal("70.00")


def _is_sfp_monitor_interface(interface_name):
    name = str(interface_name or "").strip()
    return bool(SFP_INTERFACE_RE.match(name)) or is_uplink_interface(name) or is_legacy_gi_sfp_interface(name)


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _to_decimal(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def _delta(current, previous):
    current_value = _to_int(current)
    previous_value = _to_int(previous)
    if current_value < previous_value:
        return 0
    return current_value - previous_value


def _decimal_outside(value, minimum, maximum):
    decimal_value = _to_decimal(value)
    if decimal_value is None:
        return False
    return decimal_value < minimum or decimal_value > maximum


# PHASE80_2_RESEARCHED_SFP_SUPPRESSION
def _sfp_link_status_text(values):
    return str(values.get("link_status") or "").strip().lower()


def _sfp_optical_power_should_be_evaluated(values):
    return _sfp_link_status_text(values) in {"connected", "up"}


def _sfp_issue_labels_from_values(values):
    # PHASE83_1_NO_GENERIC_OPTICAL_THRESHOLDS
    # Do not inject global Rx/Tx thresholds. Optical alarms require real per-module thresholds.
    return policy_sfp_issue_labels_from_values(dict(values or {}))


def _sfp_issue_labels_for_snapshot(item):
    return _sfp_issue_labels_from_values({
        "link_status": getattr(item, "link_status", ""),
        "err_disabled": getattr(item, "err_disabled", False),
        "align_delta": getattr(item, "align_delta", 0),
        "fcs_delta": getattr(item, "fcs_delta", 0),
        "xmit_delta": getattr(item, "xmit_delta", 0),
        "rcv_delta": getattr(item, "rcv_delta", 0),
        "input_error_delta": getattr(item, "input_error_delta", 0),
        "output_error_delta": getattr(item, "output_error_delta", 0),
        "out_discard_delta": getattr(item, "out_discard_delta", 0),
        "rx_power_dbm": getattr(item, "rx_power_dbm", None),
        "tx_power_dbm": getattr(item, "tx_power_dbm", None),
        "temperature_c": getattr(item, "temperature_c", None),
    })

def _sfp_has_issue(item):
    return bool(_sfp_issue_labels_for_snapshot(item))


def _parse_sfp_status(output):
    status_map = {}
    for raw_line in str(output or "").splitlines():
        match = SFP_STATUS_RE.match(raw_line)
        if not match:
            continue
        iface = match.group("iface").strip()
        if not _is_sfp_monitor_interface(iface):
            continue
        status_map[iface] = {
            "interface_name": iface,
            "link_status": match.group("status").strip(),
            "vlan_text": match.group("vlan").strip(),
            "duplex": match.group("duplex").strip(),
            "speed": match.group("speed").strip(),
            "media_type": match.group("type").strip(),
            "raw_status_line": raw_line.strip(),
        }
    return status_map


def _parse_sfp_error_counters(output):
    counters = {}
    headers = []
    aliases = {
        "align-err": "align_errors",
        "fcs-err": "fcs_errors",
        "xmit-err": "xmit_errors",
        "rcv-err": "rcv_errors",
        "in-err": "input_errors",
        "input-err": "input_errors",
        "input-errors": "input_errors",
        "out-err": "output_errors",
        "output-err": "output_errors",
        "output-errors": "output_errors",
        "outdiscards": "out_discards",
        "out-discards": "out_discards",
    }

    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("port"):
            headers = [part.strip().lower() for part in re.split(r"\s+", line)]
            continue

        match = SFP_COUNTER_IFACE_RE.match(line)
        if not match or not headers:
            continue
        iface = match.group("iface").strip()
        if not _is_sfp_monitor_interface(iface):
            continue
        values = [_to_int(value) for value in re.split(r"\s+", match.group("values").strip())]
        entry = counters.setdefault(iface, {})
        for header, value in zip(headers[1:], values):
            field = aliases.get(header)
            if field:
                entry[field] = entry.get(field, 0) + value
    return counters


def _parse_sfp_transceivers(output):
    transceivers = {}
    for raw_line in str(output or "").splitlines():
        match = SFP_TRANSCEIVER_RE.match(raw_line)
        if not match:
            continue
        iface = match.group("iface").strip()
        if not _is_sfp_monitor_interface(iface):
            continue
        transceivers[iface] = {
            "temperature_c": _to_decimal(match.group("temp")),
            "voltage_v": _to_decimal(match.group("volt")),
            "current_ma": _to_decimal(match.group("current")),
            "tx_power_dbm": _to_decimal(match.group("tx")),
            "rx_power_dbm": _to_decimal(match.group("rx")),
        }
    return transceivers


def _health_for_sfp(data):
    # PHASE83_1_SFP_HEALTH_NO_DOWN_WARNING
    status = str(data.get("link_status") or "").strip().lower()
    issue_labels = _sfp_issue_labels_from_values(data)

    if "Err-disabled" in issue_labels:
        return SfpMonitorSnapshot.Health.CRITICAL, "Err-disabled"
    if any(label in issue_labels for label in ("CRC Increased", "Input Error", "Output Error")):
        return SfpMonitorSnapshot.Health.WARNING, " | ".join(issue_labels)
    if issue_labels:
        return SfpMonitorSnapshot.Health.WARNING, " | ".join(issue_labels)
    if status in {"connected", "up"}:
        return SfpMonitorSnapshot.Health.HEALTHY, "OK"
    if status in {"notconnect", "down", "disabled", "inactive", "suspended", "sfpabsent", "xcvrabsent"}:
        return SfpMonitorSnapshot.Health.UNKNOWN, f"{status} / no alarm"
    return SfpMonitorSnapshot.Health.UNKNOWN, "no status"


def _latest_sfp_snapshot_map(switch):
    latest = {}
    for item in SfpMonitorSnapshot.objects.filter(switch=switch).order_by("interface_name", "-poll_time"):
        latest.setdefault(item.interface_name, item)
    return latest


def _sfp_interface_port_map(switch):
    ports = Port.objects.filter(switch=switch).order_by("display_order", "interface_name")
    return {port.interface_name: port for port in ports if _is_sfp_monitor_interface(port.interface_name)}


def _poll_sfp_monitor(switch, username, password, enable_password=""):
    result = run_switch_show_commands(
        switch=switch,
        username=username,
        password=password,
        enable_password=enable_password,
        commands=SFP_SHOW_COMMANDS,
        command_wait=1.6,
    )
    outputs = result.get("outputs", {})
    status_map = _parse_sfp_status(outputs.get("show interfaces status", ""))
    counter_map = _parse_sfp_error_counters(outputs.get("show interfaces counters errors", ""))
    transceiver_map = _parse_sfp_transceivers(outputs.get("show interfaces transceiver detail", ""))

    interface_names = set(status_map) | set(counter_map) | set(transceiver_map)
    port_map = _sfp_interface_port_map(switch)
    interface_names |= set(port_map)
    latest_map = _latest_sfp_snapshot_map(switch)

    created = []
    now = timezone.now()
    for interface_name in sorted(interface_names):
        data = {
            "interface_name": interface_name,
            "link_status": "",
            "vlan_text": "",
            "duplex": "",
            "speed": "",
            "media_type": "",
            "raw_status_line": "",
            "align_errors": 0,
            "fcs_errors": 0,
            "xmit_errors": 0,
            "rcv_errors": 0,
            "input_errors": 0,
            "output_errors": 0,
            "out_discards": 0,
        }
        data.update(status_map.get(interface_name, {}))
        data.update(counter_map.get(interface_name, {}))
        data.update(transceiver_map.get(interface_name, {}))
        if not data.get("input_errors") and data.get("rcv_errors"):
            data["input_errors"] = data["rcv_errors"]
        if not data.get("output_errors") and data.get("xmit_errors"):
            data["output_errors"] = data["xmit_errors"]
        data["err_disabled"] = "err-disabled" in str(data.get("link_status") or "").lower()

        previous = latest_map.get(interface_name)
        if previous is None:
            data["align_delta"] = 0
            data["fcs_delta"] = 0
            data["xmit_delta"] = 0
            data["rcv_delta"] = 0
            data["input_error_delta"] = 0
            data["output_error_delta"] = 0
            data["out_discard_delta"] = 0
        else:
            data["align_delta"] = _delta(data.get("align_errors"), getattr(previous, "align_errors", 0))
            data["fcs_delta"] = _delta(data.get("fcs_errors"), getattr(previous, "fcs_errors", 0))
            data["xmit_delta"] = _delta(data.get("xmit_errors"), getattr(previous, "xmit_errors", 0))
            data["rcv_delta"] = _delta(data.get("rcv_errors"), getattr(previous, "rcv_errors", 0))
            data["input_error_delta"] = _delta(data.get("input_errors"), getattr(previous, "input_errors", 0))
            data["output_error_delta"] = _delta(data.get("output_errors"), getattr(previous, "output_errors", 0))
            data["out_discard_delta"] = _delta(data.get("out_discards"), getattr(previous, "out_discards", 0))
        data["health_state"], data["health_note"] = _health_for_sfp(data)

        created.append(SfpMonitorSnapshot.objects.create(
            switch=switch,
            port=port_map.get(interface_name),
            poll_time=now,
            **data,
        ))

        old_ids = list(
            SfpMonitorSnapshot.objects
            .filter(switch=switch, interface_name=interface_name)
            .order_by("-poll_time", "-id")
            .values_list("id", flat=True)[SFP_HISTORY_KEEP:]
        )
        if old_ids:
            SfpMonitorSnapshot.objects.filter(id__in=old_ids).delete()

    return {
        "ok": True,
        "created": len(created),
        "snapshots": created,
        "commands": SFP_SHOW_COMMANDS,
    }


def _sfp_history_for_item(item, limit=4):
    return list(
        SfpMonitorSnapshot.objects
        .filter(switch_id=item.switch_id, interface_name=item.interface_name)
        .exclude(id=item.id)
        .order_by("-poll_time", "-id")[:limit]
    )


def _decorate_sfp_snapshot(item):
    issue_tags = _sfp_issue_labels_for_snapshot(item)
    item.issue_tags = issue_tags
    item.has_issue = bool(issue_tags)
    item.issue_text = " | ".join(issue_tags) or "OK"
    history_items = _sfp_history_for_item(item)
    item.history_items = history_items
    previous = history_items[0] if history_items else None
    item.previous_poll_text = _dt_text(previous.poll_time) if previous else "-"
    history_parts = []
    for history in history_items:
        history_parts.append(
            f"{_dt_text(history.poll_time)}: CRCΔ={history.fcs_delta}, InΔ={history.input_error_delta}, OutΔ={history.output_error_delta}"
        )
    item.history_text = " | ".join(history_parts) or "-"
    return item


def _latest_sfp_snapshots(switch_id=""):
    qs = SfpMonitorSnapshot.objects.select_related("switch", "port").order_by("interface_name", "-poll_time")
    if switch_id:
        qs = qs.filter(switch_id=switch_id)
    latest = {}
    for item in qs:
        key = (item.switch_id, item.interface_name)
        latest.setdefault(key, item)
    return [_decorate_sfp_snapshot(item) for item in latest.values()]


def _sfp_snapshot_payload(item):
    item = _decorate_sfp_snapshot(item)
    return {
        "switch": item.switch.name,
        "switch_id": item.switch_id,
        "interface": item.interface_name,
        "poll_time": _dt_text(item.poll_time),
        "previous_poll": item.previous_poll_text,
        "status": item.link_status or "-",
        "speed": item.speed or "-",
        "media_type": item.media_type or "-",
        "err_disabled": item.err_disabled,
        "fcs": item.fcs_errors,
        "fcs_delta": item.fcs_delta,
        "input_errors": item.input_errors,
        "input_delta": item.input_error_delta,
        "output_errors": item.output_errors,
        "output_delta": item.output_error_delta,
        "out_discards": item.out_discards,
        "out_discard_delta": item.out_discard_delta,
        "rx_power": "" if item.rx_power_dbm is None else str(item.rx_power_dbm),
        "tx_power": "" if item.tx_power_dbm is None else str(item.tx_power_dbm),
        "temperature": "" if item.temperature_c is None else str(item.temperature_c),
        "health": item.health_state,
        "health_note": item.health_note or "-",
        "has_issue": item.has_issue,
        "issue_tags": item.issue_tags,
        "issue_text": item.issue_text,
        "history": [
            {
                "poll_time": _dt_text(history.poll_time),
                "fcs_delta": history.fcs_delta,
                "input_delta": history.input_error_delta,
                "output_delta": history.output_error_delta,
                "out_discard_delta": history.out_discard_delta,
                "rx_power": "" if history.rx_power_dbm is None else str(history.rx_power_dbm),
                "tx_power": "" if history.tx_power_dbm is None else str(history.tx_power_dbm),
                "temperature": "" if history.temperature_c is None else str(history.temperature_c),
                "health": history.health_state,
            }
            for history in item.history_items
        ],
    }


def _sfp_monitor_summary(items):
    return {
        "total": len(items),
        "problem": sum(1 for item in items if _sfp_has_issue(item)),
        "healthy": sum(1 for item in items if item.health_state == SfpMonitorSnapshot.Health.HEALTHY),
        "warning": sum(1 for item in items if item.health_state == SfpMonitorSnapshot.Health.WARNING),
        "critical": sum(1 for item in items if item.health_state == SfpMonitorSnapshot.Health.CRITICAL),
        "err_disabled": sum(1 for item in items if item.err_disabled),
        "crc_increased": sum(1 for item in items if item.fcs_delta > 0 or item.align_delta > 0),
        "input_error": sum(1 for item in items if item.input_error_delta > 0 or item.rcv_delta > 0),
        "output_error": sum(1 for item in items if item.output_error_delta > 0 or item.xmit_delta > 0),
        "rx_power_abnormal": sum(1 for item in items if "Rx Power abnormal" in _sfp_issue_labels_for_snapshot(item)),
        "tx_power_abnormal": sum(1 for item in items if "Tx Power abnormal" in _sfp_issue_labels_for_snapshot(item)),
    }


def _is_active_sfp_snapshot(item):
    status = str(getattr(item, "link_status", "") or "").strip().lower()
    return status in {"connected", "up"} or _sfp_has_issue(item)


def _sfp_error_summary_text(item):
    issue_tags = _sfp_issue_labels_for_snapshot(item)
    if issue_tags:
        return " | ".join(issue_tags)
    if item.health_state == SfpMonitorSnapshot.Health.CRITICAL:
        return item.health_note or "Critical"
    if item.health_state == SfpMonitorSnapshot.Health.WARNING:
        return item.health_note or "Warning"
    return "OK"


def _active_sfp_dashboard_items(limit=12):
    latest_items = _latest_sfp_snapshots("")
    problem_items = [item for item in latest_items if _sfp_has_issue(item)]
    problem_items.sort(
        key=lambda item: (
            0 if item.health_state == SfpMonitorSnapshot.Health.CRITICAL or item.err_disabled else 1,
            item.switch.name,
            item.interface_name,
        )
    )
    for item in problem_items:
        item.poll_time_text = _dt_text(item.poll_time)
        item.error_summary_text = _sfp_error_summary_text(item)
        item.is_error = item.health_state == SfpMonitorSnapshot.Health.CRITICAL or item.err_disabled
    return problem_items[:limit]


def _sfp_dashboard_summary(items):
    return {
        "active": len(items),
        "ok": sum(1 for item in items if item.health_state == SfpMonitorSnapshot.Health.WARNING and not item.err_disabled),
        "error": sum(1 for item in items if item.health_state == SfpMonitorSnapshot.Health.CRITICAL or item.err_disabled),
    }


def _sfp_dashboard_payload():
    items = _active_sfp_dashboard_items(limit=12)
    return {
        "summary": _sfp_dashboard_summary(items),
        "items": [
            {
                "switch": item.switch.name,
                "switch_id": item.switch_id,
                "interface": item.interface_name,
                "port_id": item.port_id,
                "health": item.health_state,
                "health_text": "Critical" if item.is_error else "Warning",
                "is_error": item.is_error,
                "status": item.link_status or "-",
                "note": item.error_summary_text,
                "poll_time": item.poll_time_text,
                "issue_tags": _sfp_issue_labels_for_snapshot(item),
            }
            for item in items
        ],
    }


def sfp_monitor_view(request):
    switches = Switch.objects.filter(is_active=True).order_by("name")
    selected_switch = request.GET.get("switch", "").strip()
    latest_items = _latest_sfp_snapshots(selected_switch)
    latest_items.sort(key=lambda item: (item.switch.name, item.interface_name))
    for item in latest_items:
        item.poll_time_text = _dt_text(item.poll_time)

    return render(
        request,
        "inventory/sfp_monitor.html",
        {
            "switches": switches,
            "selected_switch": selected_switch,
            "default_ssh_username": (switches.first().ssh_username if switches.exists() else "admin") or "admin",
            "snapshots": latest_items,
            "summary": _sfp_monitor_summary(latest_items),
        },
    )


def _poll_sfp_monitor_switches(switches, ssh_username, ssh_password, enable_password=""):
    results = []
    total_created = 0
    failed = []
    for switch in switches:
        username = ssh_username or switch.ssh_username or "admin"
        try:
            result = _poll_sfp_monitor(
                switch=switch,
                username=username,
                password=ssh_password,
                enable_password=enable_password,
            )
            created = int(result.get("created", 0))
            total_created += created
            results.append({"switch": switch.name, "ok": True, "created": created})
        except SshActionError as exc:
            failed.append({"switch": switch.name, "error": str(exc)})
            results.append({"switch": switch.name, "ok": False, "error": str(exc)})
    return {
        "ok": not failed,
        "total_created": total_created,
        "failed": failed,
        "results": results,
    }


@require_POST
def sfp_monitor_poll_view(request):
    switch_id = request.POST.get("switch", "").strip()
    ssh_username = request.POST.get("ssh_username", "").strip()
    ssh_password = request.POST.get("ssh_password", "")
    enable_password = request.POST.get("enable_password", "")
    dashboard_mode = request.POST.get("dashboard", "") == "1"

    if switch_id:
        switches = [get_object_or_404(Switch, id=switch_id, is_active=True)]
        redirect_url = f"{reverse('inventory:sfp_monitor')}?switch={switch_id}"
    else:
        switches = list(Switch.objects.filter(is_active=True, ssh_enabled=True).order_by("name"))
        redirect_url = reverse("inventory:sfp_monitor")

    if not switches:
        message = "هیچ سوییچ فعالی برای SFP Poll پیدا نشد."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": message}, status=400)
        messages.warning(request, message)
        return redirect(redirect_url)

    result = _poll_sfp_monitor_switches(
        switches=switches,
        ssh_username=ssh_username,
        ssh_password=ssh_password,
        enable_password=enable_password,
    )

    selected_for_payload = switch_id if switch_id else ""
    latest_items = _latest_sfp_snapshots(selected_for_payload)
    latest_items.sort(key=lambda item: (item.switch.name, item.interface_name))
    payload = [_sfp_snapshot_payload(item) for item in latest_items]

    fail_count = len(result["failed"])
    message = f"SFP Poll OK | switches={len(switches)} | ports={result['total_created']}"
    if fail_count:
        message = f"SFP Poll partial | switches={len(switches)} | failed={fail_count} | ports={result['total_created']}"

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        all_failed = fail_count == len(switches)
        response_payload = {
            "ok": not all_failed,
            "message": message,
            "summary": _sfp_monitor_summary(latest_items),
            "snapshots": payload,
            "failed": result["failed"],
            "dashboard": _sfp_dashboard_payload() if dashboard_mode else None,
        }
        return JsonResponse(response_payload, status=400 if all_failed else 200)

    if fail_count:
        failed_names = ", ".join(item["switch"] for item in result["failed"][:5])
        messages.warning(request, f"{message} | failed: {failed_names}")
    else:
        messages.success(request, message)
    return redirect(redirect_url)


def sfp_monitor_data_view(request):
    if request.GET.get("dashboard", "") == "1":
        return JsonResponse({"ok": True, "dashboard": _sfp_dashboard_payload()})
    switch_id = request.GET.get("switch", "").strip()
    items = _latest_sfp_snapshots(switch_id)
    if request.GET.get("active_only", "") == "1":
        items = [item for item in items if _is_active_sfp_snapshot(item)]
    if request.GET.get("issues_only", "") == "1":
        items = [item for item in items if _sfp_has_issue(item)]
    items.sort(key=lambda item: (item.switch.name, item.interface_name))
    return JsonResponse({
        "ok": True,
        "summary": _sfp_monitor_summary(items),
        "snapshots": [_sfp_snapshot_payload(item) for item in items],
    })


def _alarm_severity_rank(value):
    ranks = {
        AlarmNotification.Severity.CRITICAL: 0,
        AlarmNotification.Severity.WARNING: 1,
        AlarmNotification.Severity.INFO: 2,
    }
    return ranks.get(value, 9)


def _alarm_slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "alarm"


def _alarm_upsert(*, fingerprint, source, category, severity, title, message, switch=None, port=None, details="", count_occurrence=True, observed_at=None):
    # PHASE80_ALARM_DEDUP_COOLDOWN
    now = observed_at or timezone.now()
    alarm, created = AlarmNotification.objects.get_or_create(
        fingerprint=fingerprint,
        defaults={
            "source": source,
            "category": category,
            "severity": severity,
            "status": AlarmNotification.Status.ACTIVE,
            "title": title,
            "message": message,
            "details": details,
            "switch": switch,
            "port": port,
            "occurrences": 1,
            "last_seen": now,
        },
    )
    if created:
        return alarm

    update_fields = [
        "source",
        "category",
        "severity",
        "title",
        "message",
        "details",
        "switch",
        "port",
    ]
    alarm.source = source
    alarm.category = category
    alarm.severity = severity
    alarm.title = title
    alarm.message = message
    alarm.details = details
    alarm.switch = switch
    alarm.port = port

    if alarm.status == AlarmNotification.Status.RESOLVED:
        alarm.status = AlarmNotification.Status.ACTIVE
        alarm.resolved_at = None
        update_fields.extend(["status", "resolved_at"])
        count_occurrence = True

    if count_occurrence:
        alarm.last_seen = now
        alarm.occurrences = int(alarm.occurrences or 0) + 1
        update_fields.extend(["last_seen", "occurrences"])

    alarm.save(update_fields=update_fields)
    return alarm


def _latest_sfp_alarm_items():
    latest = {}
    for item in SfpMonitorSnapshot.objects.select_related("switch", "port").order_by("interface_name", "-poll_time", "-id"):
        key = (item.switch_id, item.interface_name)
        latest.setdefault(key, item)
    return list(latest.values())



def _phase80_observed_key(*parts):
    return "|".join(str(part or "") for part in parts)


def _phase80_port_observed_at(port):
    return getattr(port, "snmp_last_poll", None) or getattr(port, "discovery_last_poll", None)


def _phase80_is_important_down_port(port):
    # PHASE80_2_ACTIONABLE_DOWN_ONLY
    return is_actionable_interface_down(port)


def _sync_alarm_notifications():
    # PHASE83R5_SINGLE_ALARM_WRITER
    # UI/Alarm Center/Sync button must not create alarms directly.
    from .alarm_engine import sync_alarm_notifications_v2
    return sync_alarm_notifications_v2()

    # PHASE83R_ALARM_ENGINE_V2_SINGLE_WRITER
    from .alarm_engine import sync_alarm_notifications_v2
    return sync_alarm_notifications_v2()

def alarm_center_view(request):
    alarms, filters = _alarm_queryset(request)
    active_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    critical_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count()
    warning_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count()
    ack_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACKNOWLEDGED).count()
    resolved_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.RESOLVED).count()

    paginator = Paginator(alarms, 100)
    page_obj = paginator.get_page(request.GET.get("page"))
    for alarm in page_obj.object_list:
        alarm.first_seen_text = _dt_text(alarm.first_seen)
        alarm.last_seen_text = _dt_text(alarm.last_seen)
        alarm.resolved_at_text = _dt_text(alarm.resolved_at)
        alarm.acknowledged_at_text = _dt_text(alarm.acknowledged_at)

    return render(
        request,
        "inventory/alarm_center.html",
        {
            "page_obj": page_obj,
            "switches": Switch.objects.filter(is_active=True).order_by("name"),
            "query": filters["query"],
            "selected_status": filters["status"],
            "selected_severity": filters["severity"],
            "selected_category": filters["category"],
            "selected_switch": filters["switch_id"],
            "selected_alarm_id": request.GET.get("alarm", "").strip(),
            "active_count": active_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "ack_count": ack_count,
            "resolved_count": resolved_count,
            "status_choices": AlarmNotification.Status.choices,
            "severity_choices": AlarmNotification.Severity.choices,
            "category_choices": AlarmNotification.Category.choices,
        },
    )


@require_POST
def alarm_sync_view(request):
    summary = _sync_alarm_notifications()
    active_count = summary.get('active', 0)
    ack_count = summary.get('acknowledged', summary.get('ack', summary.get('acknowledged_count', 0)))
    resolved_count = summary.get('resolved', 0)
    sep = chr(124)
    messages.success(request, 'Alarm Sync OK ' + sep + ' Active=' + str(active_count) + ' ' + sep + ' Ack=' + str(ack_count) + ' ' + sep + ' Resolved=' + str(resolved_count))
    return redirect("inventory:alarm_center")


@require_POST
def alarm_acknowledge_view(request, alarm_id):
    alarm = get_object_or_404(AlarmNotification, id=alarm_id)
    if alarm.status != AlarmNotification.Status.RESOLVED:
        alarm.status = AlarmNotification.Status.ACKNOWLEDGED
        alarm.acknowledged_at = timezone.now()
        alarm.acknowledged_by = _actor_username(request)
        alarm.save(update_fields=["status", "acknowledged_at", "acknowledged_by"])
        messages.success(request, "Alarm acknowledged.")
    return redirect(request.POST.get("next") or "inventory:alarm_center")


@require_POST
def alarm_resolve_view(request, alarm_id):
    alarm = get_object_or_404(AlarmNotification, id=alarm_id)
    alarm.status = AlarmNotification.Status.RESOLVED
    alarm.resolved_at = timezone.now()
    alarm.save(update_fields=["status", "resolved_at"])
    messages.success(request, "Alarm resolved.")
    return redirect(request.POST.get("next") or "inventory:alarm_center")


@require_POST
def alarm_bulk_action_view(request):
    action = request.POST.get("bulk_action", "").strip()
    alarm_ids = [item for item in request.POST.getlist("alarm_ids") if str(item).isdigit()]
    next_url = request.POST.get("next") or "inventory:alarm_center"

    if action not in {"acknowledge", "resolve"}:
        messages.error(request, "Bulk action is invalid.")
        return redirect(next_url)

    if not alarm_ids:
        messages.warning(request, "هیچ آلارمی انتخاب نشده است.")
        return redirect(next_url)

    alarms = AlarmNotification.objects.filter(id__in=alarm_ids)
    now = timezone.now()

    if action == "acknowledge":
        updated = alarms.exclude(status=AlarmNotification.Status.RESOLVED).update(
            status=AlarmNotification.Status.ACKNOWLEDGED,
            acknowledged_at=now,
            acknowledged_by=_actor_username(request),
        )
        messages.success(request, f"{updated} alarm acknowledged.")
    else:
        updated = alarms.exclude(status=AlarmNotification.Status.RESOLVED).update(
            status=AlarmNotification.Status.RESOLVED,
            resolved_at=now,
        )
        messages.success(request, f"{updated} alarm resolved.")

    return redirect(next_url)


def _action_log_queryset(request):
    logs = PortActionLog.objects.select_related("switch", "port").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    switch_id = request.GET.get("switch", "").strip()
    action = request.GET.get("action", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if query:
        logs = logs.filter(
            Q(switch__name__icontains=query)
            | Q(switch__management_ip__icontains=query)
            | Q(port__interface_name__icontains=query)
            | Q(action__icontains=query)
            | Q(action_label__icontains=query)
            | Q(value__icontains=query)
            | Q(ssh_username__icontains=query)
            | Q(actor_username__icontains=query)
            | Q(actor_role__icontains=query)
            | Q(client_ip__icontains=query)
            | Q(message__icontains=query)
            | Q(commands__icontains=query)
        )
    if status == "ok":
        logs = logs.filter(success=True)
    elif status == "fail":
        logs = logs.filter(success=False)
    if switch_id:
        logs = logs.filter(switch_id=switch_id)
    if action:
        logs = logs.filter(action=action)

    date_from_obj = parse_date(date_from) if date_from else None
    if date_from_obj:
        start_dt = timezone.make_aware(datetime.combine(date_from_obj, time.min), IRAN_TZ)
        logs = logs.filter(created_at__gte=start_dt)

    date_to_obj = parse_date(date_to) if date_to else None
    if date_to_obj:
        end_dt = timezone.make_aware(datetime.combine(date_to_obj, time.max), IRAN_TZ)
        logs = logs.filter(created_at__lte=end_dt)

    filters = {
        "query": query,
        "status": status,
        "switch_id": switch_id,
        "action": action,
        "date_from": date_from,
        "date_to": date_to,
    }
    return logs, filters


def _action_logs_filter_querystring(request):
    querydict = request.GET.copy()
    querydict.pop("page", None)
    querydict.pop("export", None)
    return querydict.urlencode()


def action_logs_view(request):
    logs, filters = _action_log_queryset(request)
    total_count = logs.count()
    ok_count = logs.filter(success=True).count()
    fail_count = logs.filter(success=False).count()

    paginator = Paginator(logs, 100)
    page_obj = paginator.get_page(request.GET.get("page"))
    for log in page_obj.object_list:
        log.created_at_text = _dt_text(log.created_at)

    cisco_logs, cisco_filters = _cisco_syslog_queryset(request)
    cisco_total_count = cisco_logs.count()
    cisco_parsed_count = cisco_logs.filter(is_parsed=True).count()
    cisco_unparsed_count = cisco_logs.filter(is_parsed=False).count()
    cisco_error_count = cisco_logs.filter(severity__lte=3).count()

    cisco_paginator = Paginator(cisco_logs, 100)
    cisco_page_obj = cisco_paginator.get_page(request.GET.get("c_page"))
    for log in cisco_page_obj.object_list:
        log.received_at_text = _dt_text(log.received_at)
        log.category_label = _category_label_map().get(log.category, log.category or "-")

    actions = (
        PortActionLog.objects.exclude(action="")
        .values_list("action", "action_label")
        .distinct()
        .order_by("action")
    )
    switches = Switch.objects.filter(is_active=True).order_by("name")
    filter_querystring = _action_logs_filter_querystring(request)
    cisco_filter_querystring = _cisco_logs_filter_querystring(request)
    cisco_facilities = (
        CiscoSyslogEntry.objects.exclude(facility="")
        .values_list("facility", flat=True)
        .distinct()
        .order_by("facility")
    )
    cisco_category_count_map = {
        item["category"]: item["total"]
        for item in CiscoSyslogEntry.objects.values("category").annotate(total=Count("id"))
    }
    cisco_category_counts = [
        {"category": value, "label": label, "total": cisco_category_count_map.get(value, 0)}
        for value, label in CiscoSyslogEntry.CATEGORY_CHOICES
    ]

    return render(
        request,
        "inventory/action_logs.html",
        {
            "page_obj": page_obj,
            "query": filters["query"],
            "status": filters["status"],
            "selected_switch": filters["switch_id"],
            "selected_alarm_id": request.GET.get("alarm", "").strip(),
            "selected_action": filters["action"],
            "date_from": filters["date_from"],
            "date_to": filters["date_to"],
            "total_count": total_count,
            "ok_count": ok_count,
            "fail_count": fail_count,
            "switches": switches,
            "default_ssh_username": (switches.first().ssh_username if switches.exists() else "admin") or "admin",
            "actions": actions,
            "filter_querystring": filter_querystring,
            "cisco_page_obj": cisco_page_obj,
            "cisco_query": cisco_filters["query"],
            "selected_cisco_switch": cisco_filters["switch_id"],
            "selected_severity": cisco_filters["severity"],
            "selected_category": cisco_filters["category"],
            "selected_facility": cisco_filters["facility"],
            "cisco_date_from": cisco_filters["date_from"],
            "cisco_date_to": cisco_filters["date_to"],
            "cisco_total_count": cisco_total_count,
            "cisco_parsed_count": cisco_parsed_count,
            "cisco_unparsed_count": cisco_unparsed_count,
            "cisco_error_count": cisco_error_count,
            "cisco_severities": CISCO_SEVERITY_CHOICES,
            "cisco_severity_options": [(str(level), label) for level, label in CISCO_SEVERITY_CHOICES],
            "cisco_categories": CiscoSyslogEntry.CATEGORY_CHOICES,
            "cisco_facilities": cisco_facilities,
            "cisco_category_counts": cisco_category_counts,
            "cisco_sample_log_text": CISCO_SAMPLE_LOG_TEXT,
            "cisco_filter_querystring": cisco_filter_querystring,
        },
    )


def action_logs_export_csv_view(request):
    logs, _filters = _action_log_queryset(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="switchmap_action_logs.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow([
        "created_at",
        "switch",
        "management_ip",
        "port",
        "action",
        "action_label",
        "value",
        "result",
        "ssh_username",
        "actor_username",
        "actor_role",
        "client_ip",
        "message",
        "commands",
    ])

    for log in logs:
        writer.writerow([
            _dt_text(log.created_at),
            log.switch.name,
            log.switch.management_ip,
            log.port.interface_name,
            log.action,
            log.action_label or action_label(log.action),
            log.value,
            "OK" if log.success else "FAILED",
            log.ssh_username,
            log.actor_username,
            log.actor_role,
            log.client_ip or "",
            log.message,
            log.commands,
        ])

    return response


@require_POST
def cisco_syslog_import_view(request):
    switch_id = request.POST.get("switch", "").strip()
    raw_text = request.POST.get("raw_text", "").strip()
    source_ip = request.POST.get("source_ip", "").strip() or None
    switch = None
    if switch_id:
        switch = get_object_or_404(Switch, id=switch_id)
        if not source_ip:
            source_ip = str(switch.management_ip)

    if not raw_text:
        messages.warning(request, "متن Cisco Syslog وارد نشده است.")
        return redirect(f"{reverse('inventory:action_logs')}?tab=cisco")

    result = _store_cisco_syslog_lines(
        switch=switch,
        source_ip=source_ip,
        raw_text=raw_text,
        skip_non_syslog=False,
        dedupe=False,
    )

    if result["imported"]:
        messages.success(
            request,
            f"Cisco logs imported: {result['imported']} | parsed: {result['parsed']} | unparsed: {result['unparsed']} | skipped: {result['skipped']}",
        )
    else:
        messages.warning(request, f"هیچ Cisco Syslog معتبری وارد نشد. skipped={result['skipped']}")
    return redirect(f"{reverse('inventory:action_logs')}?tab=cisco")


@require_POST
def cisco_syslog_pull_view(request):
    switch_id = request.POST.get("pull_switch", "").strip()
    ssh_username = request.POST.get("ssh_username", "").strip()
    ssh_password = request.POST.get("ssh_password", "")
    enable_password = request.POST.get("enable_password", "")

    if not switch_id:
        messages.warning(request, "برای Pull Cisco Logs باید Switch انتخاب شود.")
        return redirect(f"{reverse('inventory:action_logs')}?tab=cisco")

    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    if not ssh_username:
        ssh_username = switch.ssh_username or "admin"

    try:
        result = run_switch_show_commands(
            switch=switch,
            username=ssh_username,
            password=ssh_password,
            enable_password=enable_password,
            commands=["show logging"],
            command_wait=2.0,
        )
        raw_output = result.get("outputs", {}).get("show logging") or result.get("output", "")
        imported = _store_cisco_syslog_lines(
            switch=switch,
            source_ip=str(switch.management_ip),
            raw_text=raw_output,
            skip_non_syslog=True,
            dedupe=True,
        )
    except SshActionError as exc:
        messages.error(request, f"Pull Cisco Logs failed | {switch.name} | {exc}")
        return redirect(f"{reverse('inventory:action_logs')}?tab=cisco")

    if imported["imported"]:
        messages.success(
            request,
            f"Pull Cisco Logs OK | switch={switch.name} | imported={imported['imported']} | parsed={imported['parsed']} | unparsed={imported['unparsed']} | duplicates={imported['duplicates']} | skipped={imported['skipped']}",
        )
    elif imported["duplicates"]:
        messages.info(
            request,
            f"Pull Cisco Logs OK | switch={switch.name} | لاگ جدیدی نبود | duplicates={imported['duplicates']} | skipped={imported['skipped']}",
        )
    else:
        messages.warning(
            request,
            f"Pull Cisco Logs انجام شد ولی Syslog قابل ثبت پیدا نشد | switch={switch.name} | lines={imported['lines']} | skipped={imported['skipped']}",
        )
    return redirect(f"{reverse('inventory:action_logs')}?tab=cisco")

def cisco_syslog_export_csv_view(request):
    logs, _filters = _cisco_syslog_queryset(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="switchmap_cisco_syslog.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow([
        "received_at",
        "switch",
        "source_ip",
        "event_time_text",
        "severity",
        "severity_name",
        "facility",
        "mnemonic",
        "category",
        "interface",
        "message",
        "raw_line",
        "is_parsed",
    ])

    category_labels = _category_label_map()
    for log in logs:
        writer.writerow([
            _dt_text(log.received_at),
            log.switch.name if log.switch else "",
            log.source_ip or "",
            log.event_time_text,
            "" if log.severity is None else log.severity,
            log.severity_label(),
            log.facility,
            log.mnemonic,
            category_labels.get(log.category, log.category),
            log.interface_name,
            log.message,
            log.raw_line,
            "yes" if log.is_parsed else "no",
        ])

    return response


def _ensure_access_ports(switch, port_count):
    created_count = 0
    for number in range(1, int(port_count or 0) + 1):
        _, created = Port.objects.update_or_create(
            switch=switch,
            interface_name=f"Gi1/0/{number}",
            defaults={"display_order": number},
        )
        if created:
            created_count += 1
    return created_count


def switch_bulk_import(request):
    if request.method == "POST":
        form = SwitchBulkImportForm(request.POST)
        if form.is_valid():
            raw_text = form.cleaned_data["csv_text"].strip()
            create_ports = form.cleaned_data["create_ports"]
            default_port_count = form.cleaned_data["default_port_count"]
            reader = csv.reader(StringIO(raw_text))
            rows = [row for row in reader if row and any(cell.strip() for cell in row)]

            imported = 0
            updated = 0
            created_ports = 0
            skipped = 0
            errors = []

            header_names = {"name", "management_ip", "ip", "model", "location", "port_count", "snmp_community"}
            if rows:
                first_row = [cell.strip().lower() for cell in rows[0]]
                if any(cell in header_names for cell in first_row):
                    rows = rows[1:]

            for line_number, row in enumerate(rows, start=1):
                cells = [cell.strip() for cell in row]
                if len(cells) < 2:
                    skipped += 1
                    errors.append(f"line {line_number}: missing name/ip")
                    continue

                name = cells[0]
                management_ip = cells[1]
                model = cells[2] if len(cells) > 2 and cells[2] else "Cisco Catalyst 3850"
                location = cells[3] if len(cells) > 3 else ""
                try:
                    port_count = int(cells[4]) if len(cells) > 4 and cells[4] else default_port_count
                except ValueError:
                    port_count = default_port_count
                snmp_community = cells[5] if len(cells) > 5 else ""

                switch = Switch.objects.filter(Q(name=name) | Q(management_ip=management_ip)).first()
                if switch:
                    switch.name = name
                    switch.management_ip = management_ip
                    switch.model = model
                    switch.location = location
                    switch.port_count = port_count
                    if snmp_community:
                        switch.snmp_enabled = True
                        switch.snmp_community = snmp_community
                    switch.is_active = True
                    switch.save()
                    updated += 1
                else:
                    switch = Switch.objects.create(
                        name=name,
                        management_ip=management_ip,
                        model=model,
                        location=location,
                        port_count=port_count,
                        snmp_enabled=bool(snmp_community),
                        snmp_community=snmp_community,
                        is_active=True,
                    )
                    imported += 1

                if create_ports:
                    created_ports += _ensure_access_ports(switch, port_count)

            if errors:
                messages.warning(
                    request,
                    f"IMPORT DONE WITH WARNINGS | created={imported} | updated={updated} | ports={created_ports} | skipped={skipped} | errors={' ; '.join(errors[:5])}",
                )
            else:
                messages.success(
                    request,
                    f"IMPORT OK | created={imported} | updated={updated} | ports={created_ports}",
                )
            return redirect("inventory:switch_list")
    else:
        form = SwitchBulkImportForm()

    return render(request, "inventory/switch_import.html", {"form": form})


def export_ports_csv_view(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="switchmap_ports.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow([
        "switch",
        "management_ip",
        "interface",
        "status",
        "mode",
        "access_vlan",
        "native_vlan",
        "voice_vlan",
        "trunk_vlans",
        "poe",
        "poe_admin",
        "poe_device",
        "neighbor_device",
        "neighbor_port",
        "mac_count",
        "mac_addresses",
        "connected_device",
        "device_type",
        "owner",
        "ip_address",
        "mac_address",
        "description",
        "documentation_status",
        "asset_tag",
        "room",
        "rack",
        "rack_unit",
        "patch_panel",
        "patch_panel_port",
        "outlet",
        "cable_label",
        "cable_type",
        "cable_length",
        "snmp_alias",
    ])

    ports = (
        Port.objects.select_related("switch")
        .filter(switch__is_active=True)
        .order_by("switch__name", "display_order", "interface_name")
    )

    for port in ports:
        if not is_visible_switchmap_interface(port.interface_name):
            continue

        writer.writerow([
            port.switch.name,
            port.switch.management_ip,
            port.interface_name,
            port.get_status_display(),
            port.get_port_mode_display(),
            port.access_vlan or "",
            port.native_vlan or "",
            port.voice_vlan or "",
            port.trunk_vlans,
            port.poe_summary(),
            port.normalized_poe_admin(),
            port.normalized_poe_detection(),
            port.neighbor_device,
            port.neighbor_port,
            port.mac_count,
            port.mac_addresses,
            port.connected_device,
            port.get_device_type_display(),
            port.owner,
            port.ip_address or "",
            port.mac_address,
            port.description,
            port.get_documentation_status_display(),
            port.asset_tag,
            port.room,
            port.rack,
            port.rack_unit,
            port.patch_panel,
            port.patch_panel_port,
            port.outlet,
            port.cable_label,
            port.cable_type,
            port.cable_length,
            port.snmp_alias,
        ])

    return response


def poll_all_ports_view(request):
    if request.method != "POST":
        return redirect("inventory:switch_list")

    dry_run = request.POST.get("dry_run") == "1"
    switches = Switch.objects.filter(is_active=True, snmp_enabled=True).order_by("name")
    ok_count = 0
    error_count = 0
    details = []

    for switch in switches:
        try:
            sync_missing_snmp_ports(switch=switch, dry_run=dry_run)
            result = poll_switch_ports(switch=switch, dry_run=dry_run, show_ignored=False)
            ok_count += 1
            details.append(f"{switch.name}:updated={result['updated']}")
        except SnmpError as exc:
            error_count += 1
            details.append(f"{switch.name}:ERROR={exc}")

    label = "POLL ALL DRY RUN" if dry_run else "POLL ALL PORTS"
    if error_count:
        messages.warning(request, f"{label} DONE | ok={ok_count} | errors={error_count} | {' ; '.join(details[:6])}")
    else:
        messages.success(request, f"{label} OK | ok={ok_count} | {' ; '.join(details[:6])}")

    return redirect("inventory:switch_list")


def poll_all_discovery_view(request):
    if request.method != "POST":
        return redirect("inventory:switch_list")

    dry_run = request.POST.get("dry_run") == "1"
    switches = Switch.objects.filter(is_active=True, snmp_enabled=True).order_by("name")
    ok_count = 0
    error_count = 0
    details = []

    for switch in switches:
        try:
            result = poll_switch_discovery(switch=switch, dry_run=dry_run)
            ok_count += 1
            details.append(f"{switch.name}:neighbors={result['neighbors']},mac_ports={result['mac_ports']}")
        except SnmpError as exc:
            error_count += 1
            details.append(f"{switch.name}:ERROR={exc}")

    label = "DISCOVERY ALL DRY RUN" if dry_run else "DISCOVERY ALL"
    if error_count:
        messages.warning(request, f"{label} DONE | ok={ok_count} | errors={error_count} | {' ; '.join(details[:6])}")
    else:
        messages.success(request, f"{label} OK | ok={ok_count} | {' ; '.join(details[:6])}")

    return redirect("inventory:switch_list")


@require_POST
def switchmap_refresh_switch_step(request, switch_id):
    switch = get_object_or_404(Switch, id=switch_id, is_active=True)
    stage = (request.POST.get("stage") or "").strip().lower()

    if not switch.snmp_enabled:
        return JsonResponse({
            "ok": False,
            "stage": stage,
            "message": "SNMP برای این سوییچ فعال نیست.",
            "switch_status": _switch_refresh_payload(switch),
        })

    try:
        if stage == "sync":
            result = sync_missing_snmp_ports(switch=switch, dry_run=False)
        elif stage == "ports":
            result = poll_switch_ports(switch=switch, dry_run=False, show_ignored=False)
        elif stage == "discovery":
            result = poll_switch_discovery(switch=switch, dry_run=False)
        else:
            return JsonResponse({
                "ok": False,
                "stage": stage,
                "message": "Refresh stage نامعتبر است.",
                "switch_status": _switch_refresh_payload(switch),
            }, status=400)

        now = timezone.now()
        if stage in {"sync", "ports"}:
            switch.snmp_last_poll = now
            switch.snmp_last_error = ""
            switch.save(update_fields=["snmp_last_poll", "snmp_last_error"])
        elif stage == "discovery":
            switch.discovery_last_poll = now
            switch.discovery_last_error = ""
            switch.save(update_fields=["discovery_last_poll", "discovery_last_error"])
        switch.refresh_from_db()
        return JsonResponse({
            "ok": True,
            "stage": stage,
            "step": _refresh_step_payload(stage, result),
            "switch_status": _switch_refresh_payload(switch),
        })
    except SnmpError as exc:
        switch.refresh_from_db()
        return JsonResponse({
            "ok": False,
            "stage": stage,
            "message": str(exc),
            "switch_status": _switch_refresh_payload(switch),
        })


@require_POST
def switchmap_refresh_all_data(request):
    switches = Switch.objects.filter(is_active=True, snmp_enabled=True).order_by("name")
    ok_count = 0
    error_count = 0
    results = []

    for switch in switches:
        item = {
            "switch": switch.name,
            "ip": str(switch.management_ip),
            "ok": True,
            "steps": [],
        }
        try:
            sync_result = sync_missing_snmp_ports(switch=switch, dry_run=False)
            sync_payload = _refresh_step_payload("sync", sync_result)
            item["steps"].append(sync_payload["summary"])

            port_result = poll_switch_ports(switch=switch, dry_run=False, show_ignored=False)
            port_payload = _refresh_step_payload("ports", port_result)
            item["steps"].append(port_payload["summary"])

            discovery_result = poll_switch_discovery(switch=switch, dry_run=False)
            discovery_payload = _refresh_step_payload("discovery", discovery_result)
            item["steps"].append(discovery_payload["summary"])
            item.update({
                "sync_created": sync_result.get("created", 0),
                "ports_updated": port_result.get("updated", 0),
                "discovery_updated": discovery_result.get("updated", 0),
                "neighbors": discovery_result.get("neighbors", 0),
                "mac_ports": discovery_result.get("mac_ports", 0),
            })
            switch.refresh_from_db()
            item["switch_status"] = _switch_refresh_payload(switch)
            ok_count += 1
        except SnmpError as exc:
            error_count += 1
            item["ok"] = False
            item["error"] = str(exc)
            item["switch_status"] = _switch_refresh_payload(switch)
        results.append(item)

    ok = error_count == 0
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        return JsonResponse(
            {
                "ok": ok,
                "ok_count": ok_count,
                "error_count": error_count,
                "results": results,
                "finished_at": timezone.now().isoformat(),
            }
        )

    if ok:
        messages.success(request, f"Refresh All انجام شد | ok={ok_count}")
    else:
        messages.warning(request, f"Refresh All با خطا تمام شد | ok={ok_count} | errors={error_count}")
    return redirect("inventory:switch_list")

# Phase 66.5 Dashboard Command Center Layout
