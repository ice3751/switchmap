"""Alarm center view exports and Phase79.9 filters."""

# PHASE79_9_ALARM_FILTERS

from datetime import datetime, time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import AlarmNotification, Switch

try:
    from .alarm_rules import alarm_rule_report, phase80_state_summary
except Exception:
    def alarm_rule_report():
        return []
    def phase80_state_summary():
        return {}

try:
    from .topology_engine import build_alarm_evidence
except Exception:
    def build_alarm_evidence(alarm):
        return {"alarm": alarm, "evidence_groups": [], "evidence_items": [], "edge": None}
from .views import (
    _dt_text,
    _sync_alarm_notifications,
    alarm_acknowledge_view,
    alarm_bulk_action_view,
    alarm_resolve_view,
    alarm_sync_view,
)

IRAN_TZ = ZoneInfo("Asia/Tehran")


def _choice_values(choices):
    return {value for value, _label in choices}


def _choice_label(choices, value):
    labels = dict(choices)
    return labels.get(value, value or "-")


def _clean_choice(value, choices, default=""):
    value = (value or "").strip()
    if value in _choice_values(choices):
        return value
    return default


def _alarm_filter_values(request):
    status_raw = request.GET.get("status", "active").strip()
    if status_raw == "all":
        status = ""
    else:
        status = _clean_choice(status_raw, AlarmNotification.Status.choices, "active")

    alarm_type_raw = request.GET.get("type", request.GET.get("category", ""))
    alarm_type = _clean_choice(alarm_type_raw, AlarmNotification.Category.choices, "")

    severity = _clean_choice(request.GET.get("severity", ""), AlarmNotification.Severity.choices, "")
    switch_id = request.GET.get("switch", "").strip()
    if switch_id and not switch_id.isdigit():
        switch_id = ""

    return {
        "query": request.GET.get("q", "").strip(),
        "status": status,
        "status_raw": "all" if status_raw == "all" else status,
        "severity": severity,
        "type": alarm_type,
        "switch_id": switch_id,
        "port": request.GET.get("port", "").strip(),
        "source": request.GET.get("source", "").strip(),
        "date_from": request.GET.get("date_from", "").strip(),
        "date_to": request.GET.get("date_to", "").strip(),
    }


def _alarm_queryset_phase79_9(request):
    # PHASE83R2: Alarm Center is read-only on GET; never create/reactivate alarms from UI refresh.
    filters = _alarm_filter_values(request)
    alarms = AlarmNotification.objects.select_related("switch", "port").order_by("-last_seen", "-id")

    query = filters["query"]
    if query:
        alarms = alarms.filter(
            Q(title__icontains=query)
            | Q(message__icontains=query)
            | Q(details__icontains=query)
            | Q(source__icontains=query)
            | Q(switch__name__icontains=query)
            | Q(switch__management_ip__icontains=query)
            | Q(port__interface_name__icontains=query)
        )

    if filters["status"]:
        alarms = alarms.filter(status=filters["status"])
    if filters["severity"]:
        alarms = alarms.filter(severity=filters["severity"])
    if filters["type"]:
        alarms = alarms.filter(category=filters["type"])
    if filters["switch_id"]:
        alarms = alarms.filter(switch_id=filters["switch_id"])
    if filters["port"]:
        alarms = alarms.filter(port__interface_name__icontains=filters["port"])
    if filters["source"]:
        alarms = alarms.filter(source__icontains=filters["source"])

    date_from_obj = parse_date(filters["date_from"]) if filters["date_from"] else None
    if date_from_obj:
        start_dt = timezone.make_aware(datetime.combine(date_from_obj, time.min), IRAN_TZ)
        alarms = alarms.filter(last_seen__gte=start_dt)

    date_to_obj = parse_date(filters["date_to"]) if filters["date_to"] else None
    if date_to_obj:
        end_dt = timezone.make_aware(datetime.combine(date_to_obj, time.max), IRAN_TZ)
        alarms = alarms.filter(last_seen__lte=end_dt)

    return alarms, filters


def _filter_querystring(request):
    querydict = request.GET.copy()
    querydict.pop("page", None)
    return querydict.urlencode()


def _alarm_filter_badges(filters):
    badges = []
    if filters["query"]:
        badges.append(("Search", filters["query"]))
    if filters["status_raw"]:
        status_text = "All" if filters["status_raw"] == "all" else _choice_label(AlarmNotification.Status.choices, filters["status_raw"])
        badges.append(("Status", status_text))
    if filters["severity"]:
        badges.append(("Severity", _choice_label(AlarmNotification.Severity.choices, filters["severity"])))
    if filters["type"]:
        badges.append(("Type", _choice_label(AlarmNotification.Category.choices, filters["type"])))
    if filters["switch_id"]:
        switch = Switch.objects.filter(id=filters["switch_id"]).only("name").first()
        badges.append(("Switch", switch.name if switch else filters["switch_id"]))
    if filters["port"]:
        badges.append(("Port", filters["port"]))
    if filters["source"]:
        badges.append(("Source", filters["source"]))
    if filters["date_from"]:
        badges.append(("From", filters["date_from"]))
    if filters["date_to"]:
        badges.append(("To", filters["date_to"]))
    return badges


def alarm_center_view(request):
    alarms, filters = _alarm_queryset_phase79_9(request)
    filtered_count = alarms.count()

    active_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    critical_count = AlarmNotification.objects.filter(
        status=AlarmNotification.Status.ACTIVE,
        severity=AlarmNotification.Severity.CRITICAL,
    ).count()
    warning_count = AlarmNotification.objects.filter(
        status=AlarmNotification.Status.ACTIVE,
        severity=AlarmNotification.Severity.WARNING,
    ).count()
    ack_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACKNOWLEDGED).count()
    resolved_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.RESOLVED).count()

    paginator = Paginator(alarms, 100)
    page_obj = paginator.get_page(request.GET.get("page"))
    for alarm in page_obj.object_list:
        alarm.first_seen_text = _dt_text(alarm.first_seen)
        alarm.last_seen_text = _dt_text(alarm.last_seen)
        alarm.resolved_at_text = _dt_text(alarm.resolved_at)
        alarm.acknowledged_at_text = _dt_text(alarm.acknowledged_at)

    sources = (
        AlarmNotification.objects.exclude(source="")
        .order_by("source")
        .values_list("source", flat=True)
        .distinct()
    )

    return render(
        request,
        "inventory/alarm_center.html",
        {
            "page_obj": page_obj,
            "switches": Switch.objects.filter(is_active=True).order_by("name"),
            "sources": sources,
            "query": filters["query"],
            "selected_status": filters["status_raw"],
            "selected_severity": filters["severity"],
            "selected_category": filters["type"],
            "selected_type": filters["type"],
            "selected_switch": filters["switch_id"],
            "selected_port": filters["port"],
            "selected_source": filters["source"],
            "selected_date_from": filters["date_from"],
            "selected_date_to": filters["date_to"],
            "selected_alarm_id": request.GET.get("alarm", "").strip(),
            "filter_querystring": _filter_querystring(request),
            "filter_badges": _alarm_filter_badges(filters),
            "filters_active": bool(_filter_querystring(request)),
            "filtered_count": filtered_count,
            "active_count": active_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "ack_count": ack_count,
            "resolved_count": resolved_count,
            "status_choices": AlarmNotification.Status.choices,
            "severity_choices": AlarmNotification.Severity.choices,
            "type_choices": AlarmNotification.Category.choices,
            "category_choices": AlarmNotification.Category.choices,
            "phase79_9_alarm_filters": True,
        },
    )


# PHASE83R2_HOTFIX_RESTORE_ALARM_RULES_VIEW
def alarm_rules_view(request):
    return render(
        request,
        "inventory/alarm_rules.html",
        {
            "rules": alarm_rule_report(),
            "state_summary": phase80_state_summary(),
            "phase80_alarm_rules": True,
            "phase83r2_hotfix_alarm_rules_view": True,
        },
    )


# PHASE83R2_HOTFIX_RESTORE_ALARM_DETAIL_VIEW
def alarm_detail_view(request, alarm_id):
    alarm = get_object_or_404(AlarmNotification.objects.select_related("switch", "port"), id=alarm_id)
    context = build_alarm_evidence(alarm) or {}
    context.update({
        "alarm": alarm,
        "phase81_83_alarm_drilldown": True,
        "phase83r2_hotfix_alarm_detail_view": True,
        "alarm_first_seen_text": _dt_text(alarm.first_seen),
        "alarm_last_seen_text": _dt_text(alarm.last_seen),
        "alarm_resolved_at_text": _dt_text(alarm.resolved_at),
        "alarm_acknowledged_at_text": _dt_text(alarm.acknowledged_at),
    })
    return render(request, "inventory/alarm_detail.html", context)
