# Phase112R8.5.3 Endpoint Search UI + API - exact IP/search fix
from __future__ import annotations

import csv
import re

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import NetworkEndpoint


def _normalize_mac_query(value: str) -> str:
    raw = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    if len(raw) != 12:
        return ""
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2)).lower()


def _base_endpoint_queryset(request):
    qs = NetworkEndpoint.objects.select_related(
        "last_seen_switch",
        "last_seen_port",
        "via_device",
    ).order_by("-last_seen", "mac_address", "ip_address")

    q = (request.GET.get("q") or "").strip()
    vlan = (request.GET.get("vlan") or "").strip()
    connection_type = (request.GET.get("connection_type") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if q:
        mac_norm = _normalize_mac_query(q)
        search_q = (
            Q(identity_key__icontains=q)
            | Q(mac_address__icontains=q)
            | Q(ip_address__icontains=q)
            | Q(hostname__icontains=q)
            | Q(vendor__icontains=q)
            | Q(via_device_name__icontains=q)
            | Q(ssid__icontains=q)
            | Q(sources__icontains=q)
            | Q(evidence_summary__icontains=q)
            | Q(last_seen_switch__name__icontains=q)
            | Q(last_seen_switch__management_ip__icontains=q)
            | Q(last_seen_port__interface_name__icontains=q)
            | Q(last_seen_port__description__icontains=q)
            | Q(last_seen_port__connected_device__icontains=q)
            | Q(last_seen_port__ip_address__icontains=q)
            | Q(last_seen_port__mac_address__icontains=q)
            | Q(last_seen_port__mac_addresses__icontains=q)
            | Q(last_seen_port__neighbor_device__icontains=q)
            | Q(last_seen_port__neighbor_port__icontains=q)
        )
        if mac_norm:
            search_q |= Q(mac_address__icontains=mac_norm)
        qs = qs.filter(search_q).distinct()

    if vlan:
        if vlan.lower() in {"none", "unknown", "null", "-"}:
            qs = qs.filter(vlan__isnull=True)
        elif vlan.isdigit():
            qs = qs.filter(vlan=int(vlan))

    if connection_type:
        qs = qs.filter(connection_type=connection_type)

    if status:
        qs = qs.filter(status=status)

    return qs


def _safe_limit(request, default=250, maximum=1000):
    try:
        value = int(request.GET.get("limit") or default)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _local_dt(value):
    if not value:
        return ""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def _endpoint_to_dict(endpoint: NetworkEndpoint) -> dict:
    switch = endpoint.last_seen_switch
    port = endpoint.last_seen_port
    switch_name = switch.name if switch else ""
    switch_ip = switch.management_ip if switch else ""
    port_name = port.interface_name if port else ""
    port_description = port.description if port else ""
    via_device = endpoint.via_device.name if endpoint.via_device else ""
    return {
        "id": endpoint.id,
        "identity_key": endpoint.identity_key,
        "mac_address": endpoint.mac_address or "",
        "mac": endpoint.mac_address or "",
        "ip_address": endpoint.ip_address or "",
        "ip": endpoint.ip_address or "",
        "vlan": endpoint.vlan,
        "hostname": endpoint.hostname or "",
        "vendor": endpoint.vendor or "",
        "connection_type": endpoint.connection_type or "",
        "status": endpoint.status or "",
        "confidence": endpoint.confidence,
        "switch": switch_name,
        "switch_name": switch_name,
        "switch_ip": switch_ip,
        "device": switch_name,
        "device_name": switch_name,
        "port": port_name,
        "port_name": port_name,
        "interface": port_name,
        "interface_name": port_name,
        "port_description": port_description,
        "via_device": via_device,
        "via_device_name": endpoint.via_device_name or "",
        "ssid": endpoint.ssid or "",
        "sources": endpoint.sources or "",
        "last_seen": _local_dt(endpoint.last_seen),
        "first_seen": _local_dt(endpoint.first_seen),
        "updated_at": _local_dt(endpoint.updated_at),
        "evidence_summary": endpoint.evidence_summary or "",
    }


@login_required
def endpoint_search_view(request):
    qs = _base_endpoint_queryset(request)
    limit = _safe_limit(request)
    endpoints = list(qs[:limit])

    total_count = NetworkEndpoint.objects.count()
    active_count = NetworkEndpoint.objects.filter(status="active", is_active=True).count()
    vlan_counts = dict(
        NetworkEndpoint.objects.values("vlan").annotate(c=Count("id")).order_by("vlan").values_list("vlan", "c")
    )
    connection_counts = dict(
        NetworkEndpoint.objects.values("connection_type").annotate(c=Count("id")).order_by("connection_type").values_list("connection_type", "c")
    )

    context = {
        "query": (request.GET.get("q") or "").strip(),
        "selected_vlan": (request.GET.get("vlan") or "").strip(),
        "selected_connection_type": (request.GET.get("connection_type") or "").strip(),
        "selected_status": (request.GET.get("status") or "").strip(),
        "limit": limit,
        "endpoints": endpoints,
        "result_count": qs.count(),
        "total_count": total_count,
        "active_count": active_count,
        "vlan_counts": vlan_counts,
        "connection_counts": connection_counts,
        "connection_type_choices": NetworkEndpoint.ConnectionType.choices,
        "status_choices": NetworkEndpoint.Status.choices,
        "now": timezone.localtime(timezone.now()),
    }
    return render(request, "inventory/endpoint_search.html", context)


@login_required
def endpoint_export_csv_view(request):
    qs = _base_endpoint_queryset(request)
    limit = _safe_limit(request, default=1000, maximum=5000)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="switchmap_endpoints.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "mac_address",
        "ip_address",
        "vlan",
        "hostname",
        "vendor",
        "connection_type",
        "status",
        "confidence",
        "last_seen_switch",
        "last_seen_switch_ip",
        "last_seen_port",
        "port_description",
        "via_device",
        "via_device_name",
        "ssid",
        "sources",
        "last_seen",
        "evidence_summary",
    ])
    for endpoint in qs[:limit]:
        data = _endpoint_to_dict(endpoint)
        writer.writerow([
            data["mac_address"],
            data["ip_address"],
            data["vlan"] if data["vlan"] is not None else "",
            data["hostname"],
            data["vendor"],
            data["connection_type"],
            data["status"],
            data["confidence"],
            data["switch_name"],
            data["switch_ip"],
            data["port_name"],
            data["port_description"],
            data["via_device"],
            data["via_device_name"],
            data["ssid"],
            data["sources"],
            data["last_seen"],
            data["evidence_summary"],
        ])
    return response


@login_required
def endpoint_search_api_view(request):
    qs = _base_endpoint_queryset(request)
    limit = _safe_limit(request, default=20, maximum=100)
    endpoints = list(qs[:limit])
    return JsonResponse({
        "ok": True,
        "query": (request.GET.get("q") or "").strip(),
        "count": qs.count(),
        "limit": limit,
        "results": [_endpoint_to_dict(endpoint) for endpoint in endpoints],
        "phase": "PHASE112R8_5_3_EXACT_IP_SEARCH_FIX",
    })
