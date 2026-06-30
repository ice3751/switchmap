"""Phase 78 operational alarm cleanup views.

Additive only. This module does not replace the stable Alarm Center, Dashboard,
SSH popup, Quick Search, Topology, SFP monitor, or Backup Center.
"""

from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Max
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access_control import user_role
from .models import AlarmNotification, Port, SfpMonitorSnapshot, Switch, SystemAuditLog
from .views import _sync_alarm_notifications

MANAGED_PREFIXES = (
    "snmp-down:",
    "discovery-error:",
    "port-error:",
    "uplink-down:",
    "sfp:",
)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def _actor(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user.get_username()
    return ""


def _dt_text(value):
    if not value:
        return "-"
    try:
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def _is_managed_fingerprint(fingerprint):
    return str(fingerprint or "").startswith(MANAGED_PREFIXES)


def _token(value, index, default=""):
    parts = str(value or "").split(":")
    try:
        return parts[index]
    except IndexError:
        return default


def _int_token(value, index):
    item = _token(value, index)
    try:
        return int(item)
    except (TypeError, ValueError):
        return None


def _is_uplink_like(port):
    if not port:
        return False
    interface = (port.interface_name or "").lower()
    return bool(
        interface.startswith(("te", "tengig", "ten-gig", "fo", "forty", "hu", "hundred"))
        or port.port_mode == Port.PortMode.TRUNK
        or port.neighbor_device
    )


def _latest_sfp_map():
    latest_ids = list(
        SfpMonitorSnapshot.objects.values("switch_id", "interface_name")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    items = SfpMonitorSnapshot.objects.select_related("switch", "port").filter(id__in=latest_ids)
    result = {}
    for item in items:
        result[(item.switch_id, (item.interface_name or "").strip().lower())] = item
        if item.port_id:
            result[(item.switch_id, f"port:{item.port_id}")] = item
    return result


def _sfp_snapshot_has_issue(item):
    if not item:
        return False
    delta_values = [
        item.fcs_delta,
        item.align_delta,
        item.xmit_delta,
        item.rcv_delta,
        item.input_error_delta,
        item.output_error_delta,
        item.out_discard_delta,
    ]
    return bool(
        item.err_disabled
        or item.health_state in {SfpMonitorSnapshot.Health.WARNING, SfpMonitorSnapshot.Health.CRITICAL}
        or any((value or 0) > 0 for value in delta_values)
    )


def _classify_alarm(alarm, sfp_map, now=None):
    now = now or timezone.now()
    fingerprint = alarm.fingerprint or ""
    managed = _is_managed_fingerprint(fingerprint)
    age_minutes = None
    if alarm.last_seen:
        age_minutes = int((now - alarm.last_seen).total_seconds() // 60)

    result = {
        "state": "manual",
        "state_label": "Manual / Unknown",
        "stale_candidate": False,
        "current_condition": None,
        "reason": "این آلارم با Fingerprint مدیریتی Phase 78 شناسایی نشد.",
        "age_minutes": age_minutes,
        "managed": managed,
    }

    if not managed:
        return result

    stale_reason = "شرط فعلی دیگر در DB دیده نمی‌شود."
    current_reason = "شرط فعلی هنوز در DB وجود دارد."

    if fingerprint.startswith("snmp-down:"):
        switch_id = _int_token(fingerprint, 1)
        switch = alarm.switch or (Switch.objects.filter(id=switch_id).first() if switch_id else None)
        current = bool(switch and switch.snmp_enabled and switch.snmp_last_error)
        result.update(
            state="current" if current else "stale",
            state_label="Current" if current else "Stale Candidate",
            stale_candidate=not current,
            current_condition=current,
            reason=(switch.snmp_last_error if current and switch else stale_reason),
        )
        return result

    if fingerprint.startswith("discovery-error:"):
        switch_id = _int_token(fingerprint, 1)
        switch = alarm.switch or (Switch.objects.filter(id=switch_id).first() if switch_id else None)
        current = bool(switch and switch.discovery_last_error)
        result.update(
            state="current" if current else "stale",
            state_label="Current" if current else "Stale Candidate",
            stale_candidate=not current,
            current_condition=current,
            reason=(switch.discovery_last_error if current and switch else stale_reason),
        )
        return result

    if fingerprint.startswith("port-error:"):
        port = alarm.port
        port_id = _int_token(fingerprint, 2)
        if not port and port_id:
            port = Port.objects.select_related("switch").filter(id=port_id).first()
        current = bool(port and port.status == Port.Status.ERROR)
        result.update(
            state="current" if current else "stale",
            state_label="Current" if current else "Stale Candidate",
            stale_candidate=not current,
            current_condition=current,
            reason=(current_reason if current else stale_reason),
        )
        return result

    if fingerprint.startswith("uplink-down:"):
        port = alarm.port
        port_id = _int_token(fingerprint, 2)
        if not port and port_id:
            port = Port.objects.select_related("switch").filter(id=port_id).first()
        current = bool(port and port.status == Port.Status.DOWN and _is_uplink_like(port))
        result.update(
            state="current" if current else "stale",
            state_label="Current" if current else "Stale Candidate",
            stale_candidate=not current,
            current_condition=current,
            reason=(current_reason if current else stale_reason),
        )
        return result

    if fingerprint.startswith("sfp:"):
        item = None
        if alarm.port_id and alarm.switch_id:
            item = sfp_map.get((alarm.switch_id, f"port:{alarm.port_id}"))
        if not item and alarm.switch_id and alarm.port:
            item = sfp_map.get((alarm.switch_id, (alarm.port.interface_name or "").strip().lower()))
        if not item and alarm.switch_id:
            interface_name = _token(fingerprint, 2)
            if interface_name:
                for (switch_id, key), candidate in sfp_map.items():
                    if switch_id == alarm.switch_id and not str(key).startswith("port:") and interface_name in str(key).replace("/", "-").replace(" ", "-"):
                        item = candidate
                        break
        current = _sfp_snapshot_has_issue(item)
        result.update(
            state="current" if current else "stale",
            state_label="Current" if current else "Stale Candidate",
            stale_candidate=not current,
            current_condition=current,
            reason=(current_reason if current else "آخرین Snapshot مربوطه دیگر Issue فعال نشان نمی‌دهد."),
        )
        return result

    return result


def _decorated_active_alarms():
    now = timezone.now()
    stale_after = now - timedelta(minutes=60)
    sfp_map = _latest_sfp_map()
    alarms = list(
        AlarmNotification.objects.select_related("switch", "port")
        .filter(status=AlarmNotification.Status.ACTIVE)
        .order_by("severity", "category", "switch__name", "port__display_order", "-last_seen", "-id")
    )
    for alarm in alarms:
        meta = _classify_alarm(alarm, sfp_map, now=now)
        alarm.phase78_state = meta["state"]
        alarm.phase78_state_label = meta["state_label"]
        alarm.phase78_stale_candidate = meta["stale_candidate"]
        alarm.phase78_current_condition = meta["current_condition"]
        alarm.phase78_reason = meta["reason"]
        alarm.phase78_age_minutes = meta["age_minutes"]
        alarm.phase78_needs_recheck = bool(alarm.last_seen and alarm.last_seen < stale_after)
        alarm.first_seen_text = _dt_text(alarm.first_seen)
        alarm.last_seen_text = _dt_text(alarm.last_seen)
    return alarms


def _cleanup_summary(alarms):
    by_category = list(
        AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
        .values("category")
        .annotate(total=Count("id"))
        .order_by("category")
    )
    by_switch = list(
        AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, switch__isnull=False)
        .values("switch_id", "switch__name", "switch__management_ip")
        .annotate(total=Count("id"))
        .order_by("-total", "switch__name")[:12]
    )
    snmp_timeout_devices = list(
        Switch.objects.filter(is_active=True, snmp_enabled=True)
        .exclude(snmp_last_error="")
        .order_by("name")
    )
    for item in snmp_timeout_devices:
        item.snmp_last_poll_text = _dt_text(item.snmp_last_poll)
    return {
        "active_count": len(alarms),
        "critical_count": sum(1 for alarm in alarms if alarm.severity == AlarmNotification.Severity.CRITICAL),
        "warning_count": sum(1 for alarm in alarms if alarm.severity == AlarmNotification.Severity.WARNING),
        "stale_candidate_count": sum(1 for alarm in alarms if alarm.phase78_stale_candidate),
        "needs_recheck_count": sum(1 for alarm in alarms if alarm.phase78_needs_recheck),
        "current_count": sum(1 for alarm in alarms if alarm.phase78_state == "current"),
        "manual_count": sum(1 for alarm in alarms if alarm.phase78_state == "manual"),
        "by_category": by_category,
        "by_switch": by_switch,
        "snmp_timeout_devices": snmp_timeout_devices,
    }


def phase78_alarm_cleanup_view(request):
    alarms = _decorated_active_alarms()
    summary = _cleanup_summary(alarms)
    stale_candidates = [alarm for alarm in alarms if alarm.phase78_stale_candidate]
    operational_alarms = [alarm for alarm in alarms if not alarm.phase78_stale_candidate]

    return render(
        request,
        "inventory/phase78/alarm_cleanup.html",
        {
            "now_text": _dt_text(timezone.now()),
            "alarms": alarms,
            "stale_candidates": stale_candidates,
            "operational_alarms": operational_alarms,
            "summary": summary,
        },
    )


def phase78_alarm_cleanup_status_json(request):
    alarms = _decorated_active_alarms()
    summary = _cleanup_summary(alarms)
    return JsonResponse(
        {
            "ok": True,
            "phase": "78",
            "active_alarms": summary["active_count"],
            "critical": summary["critical_count"],
            "warning": summary["warning_count"],
            "current": summary["current_count"],
            "stale_candidates": summary["stale_candidate_count"],
            "needs_recheck": summary["needs_recheck_count"],
            "snmp_timeout_devices": len(summary["snmp_timeout_devices"]),
        }
    )


@require_POST
def phase78_alarm_recheck_view(request):
    summary = _sync_alarm_notifications()
    SystemAuditLog.objects.create(
        category=SystemAuditLog.Category.SYSTEM,
        action="phase78_alarm_recheck",
        actor_username=_actor(request),
        actor_role=user_role(request.user),
        client_ip=_client_ip(request),
        request_path=request.path,
        message=f"Phase78 alarm recheck: active={summary.get('active')} ack={summary.get('acknowledged')} resolved={summary.get('resolved')}",
    )
    messages.success(
        request,
        f"Recheck OK | Active={summary.get('active')} | Ack={summary.get('acknowledged')} | Resolved={summary.get('resolved')}",
    )
    return redirect("inventory:phase78_alarm_cleanup")


@require_POST
def phase78_alarm_resolve_stale_view(request):
    alarms = _decorated_active_alarms()
    stale_ids = [alarm.id for alarm in alarms if alarm.phase78_stale_candidate]
    updated = 0
    if stale_ids:
        updated = AlarmNotification.objects.filter(
            id__in=stale_ids,
            status=AlarmNotification.Status.ACTIVE,
        ).update(status=AlarmNotification.Status.RESOLVED, resolved_at=timezone.now())
    SystemAuditLog.objects.create(
        category=SystemAuditLog.Category.SYSTEM,
        action="phase78_resolve_stale_alarms",
        actor_username=_actor(request),
        actor_role=user_role(request.user),
        client_ip=_client_ip(request),
        request_path=request.path,
        message=f"Phase78 resolved stale alarm candidates: {updated}",
    )
    messages.success(request, f"{updated} stale alarm candidate resolved.")
    return redirect("inventory:phase78_alarm_cleanup")


def phase78_links():
    return {
        "alarm_cleanup": reverse("inventory:phase78_alarm_cleanup"),
        "status_json": reverse("inventory:phase78_alarm_cleanup_status_json"),
    }
