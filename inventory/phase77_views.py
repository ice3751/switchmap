"""Phase 77 isolated operational views.

This module is intentionally additive. It does not replace the stable dashboard,
SSH popup, quick search, alarm center, SFP monitor, topology, backup center, or
role logic. New pages read existing data and use separate templates/CSS.
"""

import difflib
import hashlib
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.db.models import Count, Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access_control import user_role
from .forms import SSHPortActionForm
from .models import (
    AlarmNotification,
    ConfigBackupSnapshot,
    Port,
    PortActionLog,
    RouterHealthSnapshot,
    SfpMonitorSnapshot,
    SSHJobTemplate,
    Switch,
    SystemAuditLog,
)
from .snmp_tools import is_visible_switchmap_interface
from .ssh_tools import action_label, action_risk_text, build_port_commands


class SSHJobTemplateForm(forms.ModelForm):
    class Meta:
        model = SSHJobTemplate
        fields = [
            "name",
            "action",
            "value_template",
            "description",
            "risk_level",
            "requires_approval",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"dir": "ltr"}),
            "action": forms.Select(),
            "value_template": forms.TextInput(attrs={"dir": "ltr", "placeholder": "VLAN / Description / allowed VLANs"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    action = forms.ChoiceField(choices=SSHPortActionForm.ACTION_CHOICES)


class ConfigSnapshotForm(forms.ModelForm):
    class Meta:
        model = ConfigBackupSnapshot
        fields = ["switch", "config_type", "command_source", "command", "content", "note"]
        widgets = {
            "command": forms.TextInput(attrs={"dir": "ltr"}),
            "content": forms.Textarea(attrs={"rows": 18, "dir": "ltr", "spellcheck": "false"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


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


def _visible_ports_queryset():
    return Port.objects.select_related("switch").filter(switch__is_active=True)


def _latest_sfp_per_port():
    latest = (
        SfpMonitorSnapshot.objects.values("switch_id", "interface_name")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    return SfpMonitorSnapshot.objects.select_related("switch", "port").filter(id__in=list(latest))


def _latest_router_health_per_switch():
    latest = (
        RouterHealthSnapshot.objects.values("switch_id")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    return RouterHealthSnapshot.objects.select_related("switch").filter(id__in=list(latest))


def phase77_noc_dashboard_view(request):
    now = timezone.now()
    stale_after = now - timedelta(minutes=30)

    switches = Switch.objects.filter(is_active=True).order_by("topology_position", "name")
    ports = _visible_ports_queryset()
    total_ports = ports.count()
    visible_port_ids = [port.id for port in ports.select_related(None).only("id", "interface_name") if is_visible_switchmap_interface(port.interface_name)]
    visible_ports = ports.filter(id__in=visible_port_ids)

    alarm_active = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
    alarm_items = list(alarm_active.select_related("switch", "port").order_by("severity", "-last_seen", "-id")[:12])
    for item in alarm_items:
        item.last_seen_text = _dt_text(item.last_seen)

    sfp_latest = list(_latest_sfp_per_port())
    sfp_problem = [
        item for item in sfp_latest
        if item.health_state in {SfpMonitorSnapshot.Health.WARNING, SfpMonitorSnapshot.Health.CRITICAL} or item.err_disabled
    ]
    sfp_problem.sort(key=lambda item: (0 if item.health_state == SfpMonitorSnapshot.Health.CRITICAL or item.err_disabled else 1, item.switch.name, item.interface_name))

    router_health = list(_latest_router_health_per_switch().order_by("switch__name"))
    for item in router_health:
        item.collected_at_text = _dt_text(item.collected_at)

    snmp_failed = switches.filter(snmp_enabled=True).exclude(snmp_last_error="").count()
    snmp_stale = switches.filter(snmp_enabled=True, snmp_last_poll__lt=stale_after).count()
    undocumented = visible_ports.filter(documentation_status=Port.DocumentationStatus.UNDOCUMENTED).count()
    partial = visible_ports.filter(documentation_status=Port.DocumentationStatus.PARTIAL).count()
    documented = visible_ports.filter(documentation_status=Port.DocumentationStatus.DOCUMENTED).count()
    documentation_percent = round((documented / max(visible_ports.count(), 1)) * 100)

    recent_actions = list(PortActionLog.objects.select_related("switch", "port").order_by("-created_at")[:10])
    recent_audit = list(SystemAuditLog.objects.order_by("-created_at")[:10])
    for item in recent_actions:
        item.created_at_text = _dt_text(item.created_at)
    for item in recent_audit:
        item.created_at_text = _dt_text(item.created_at)

    return render(
        request,
        "inventory/phase77/noc_dashboard.html",
        {
            "now_text": _dt_text(now),
            "switch_count": switches.count(),
            "port_count": total_ports,
            "visible_port_count": visible_ports.count(),
            "snmp_failed": snmp_failed,
            "snmp_stale": snmp_stale,
            "alarm_active_count": alarm_active.count(),
            "alarm_critical_count": alarm_active.filter(severity=AlarmNotification.Severity.CRITICAL).count(),
            "alarm_warning_count": alarm_active.filter(severity=AlarmNotification.Severity.WARNING).count(),
            "alarm_items": alarm_items,
            "sfp_problem_count": len(sfp_problem),
            "sfp_problem_items": sfp_problem[:12],
            "documentation_percent": documentation_percent,
            "undocumented_count": undocumented,
            "partial_count": partial,
            "documented_count": documented,
            "router_health": router_health,
            "recent_actions": recent_actions,
            "recent_audit": recent_audit,
        },
    )


def automation_templates_view(request):
    templates = SSHJobTemplate.objects.order_by("risk_level", "name")
    action_filter = request.GET.get("action", "").strip()
    risk_filter = request.GET.get("risk", "").strip()
    if action_filter:
        templates = templates.filter(action=action_filter)
    if risk_filter:
        templates = templates.filter(risk_level=risk_filter)
    return render(
        request,
        "inventory/phase77/automation_templates.html",
        {
            "templates": templates,
            "action_filter": action_filter,
            "risk_filter": risk_filter,
            "action_choices": SSHPortActionForm.ACTION_CHOICES,
            "risk_choices": SSHJobTemplate.RiskLevel.choices,
        },
    )


def automation_template_create_view(request):
    if request.method == "POST":
        form = SSHJobTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = _actor(request)
            template.updated_by = _actor(request)
            template.save()
            SystemAuditLog.objects.create(
                category=SystemAuditLog.Category.SYSTEM,
                action="job_template_create",
                target_username=template.name,
                actor_username=_actor(request),
                actor_role=user_role(request.user),
                client_ip=_client_ip(request),
                request_path=request.path,
                message=f"SSH job template created: {template.name}",
            )
            messages.success(request, "Job Template ساخته شد.")
            return redirect("inventory:automation_templates")
    else:
        form = SSHJobTemplateForm()
    return render(request, "inventory/phase77/automation_template_form.html", {"form": form, "mode": "create"})


def automation_template_edit_view(request, template_id):
    template = get_object_or_404(SSHJobTemplate, id=template_id)
    if request.method == "POST":
        form = SSHJobTemplateForm(request.POST, instance=template)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.updated_by = _actor(request)
            saved.save()
            SystemAuditLog.objects.create(
                category=SystemAuditLog.Category.SYSTEM,
                action="job_template_update",
                target_username=saved.name,
                actor_username=_actor(request),
                actor_role=user_role(request.user),
                client_ip=_client_ip(request),
                request_path=request.path,
                message=f"SSH job template updated: {saved.name}",
            )
            messages.success(request, "Job Template ذخیره شد.")
            return redirect("inventory:automation_templates")
    else:
        form = SSHJobTemplateForm(instance=template)
    return render(request, "inventory/phase77/automation_template_form.html", {"form": form, "template_obj": template, "mode": "edit"})


def automation_template_preview_view(request, template_id):
    template = get_object_or_404(SSHJobTemplate, id=template_id, is_active=True)
    port_id = request.GET.get("port", "").strip()
    port = None
    commands = []
    error = ""
    if port_id:
        try:
            port = Port.objects.select_related("switch").get(id=int(port_id), switch__is_active=True)
            value = (template.value_template or "").format(
                switch=port.switch.name,
                interface=port.interface_name,
                description=port.description or "",
                cable_label=port.cable_label or "",
                owner=port.owner or "",
            )
            force = template.action in {"set_trunk_allowed", "add_trunk_vlan", "remove_trunk_vlan", "force_trunk"}
            commands = build_port_commands(port, template.action, value, force=force)
        except Exception as exc:
            error = str(exc)
    ports = Port.objects.select_related("switch").filter(switch__is_active=True).order_by("switch__name", "display_order")[:500]
    return render(
        request,
        "inventory/phase77/automation_template_preview.html",
        {
            "template_obj": template,
            "ports": ports,
            "selected_port": port,
            "commands": commands,
            "error": error,
            "risk_text": action_risk_text(template.action),
            "action_label": action_label(template.action),
        },
    )


def config_backups_view(request):
    snapshots = ConfigBackupSnapshot.objects.select_related("switch").order_by("-created_at")
    switch_filter = request.GET.get("switch", "").strip()
    if switch_filter:
        snapshots = snapshots.filter(switch_id=switch_filter)
    switches = Switch.objects.filter(is_active=True).order_by("name")
    if request.method == "POST":
        form = ConfigSnapshotForm(request.POST)
        if form.is_valid():
            snapshot = form.save(commit=False)
            snapshot.actor_username = _actor(request)
            content = snapshot.content or ""
            snapshot.content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            previous = (
                ConfigBackupSnapshot.objects.filter(switch=snapshot.switch, config_type=snapshot.config_type)
                .order_by("-created_at", "-id")
                .first()
            )
            if previous:
                snapshot.diff_text = "\n".join(
                    difflib.unified_diff(
                        previous.content.splitlines(),
                        content.splitlines(),
                        fromfile=f"previous-{previous.created_at:%Y%m%d-%H%M%S}",
                        tofile="current",
                        lineterm="",
                    )
                )[:200000]
            snapshot.save()
            SystemAuditLog.objects.create(
                category=SystemAuditLog.Category.SYSTEM,
                action="snapshot_create",
                target_username=snapshot.switch.name,
                actor_username=_actor(request),
                actor_role=user_role(request.user),
                client_ip=_client_ip(request),
                request_path=request.path,
                message=f"Config snapshot saved for {snapshot.switch.name}",
            )
            messages.success(request, "Config snapshot ذخیره شد.")
            return redirect("inventory:config_backup_detail", snapshot_id=snapshot.id)
    else:
        form = ConfigSnapshotForm(initial={"command": "show running-config", "config_type": ConfigBackupSnapshot.ConfigType.RUNNING})
    return render(
        request,
        "inventory/phase77/config_backups.html",
        {"snapshots": snapshots[:200], "switches": switches, "switch_filter": switch_filter, "form": form},
    )


def config_backup_detail_view(request, snapshot_id):
    snapshot = get_object_or_404(ConfigBackupSnapshot.objects.select_related("switch"), id=snapshot_id)
    previous = (
        ConfigBackupSnapshot.objects.filter(switch=snapshot.switch, config_type=snapshot.config_type, created_at__lt=snapshot.created_at)
        .order_by("-created_at", "-id")
        .first()
    )
    return render(
        request,
        "inventory/phase77/config_backup_detail.html",
        {"snapshot": snapshot, "previous": previous},
    )


def config_backup_download_view(request, snapshot_id):
    snapshot = get_object_or_404(ConfigBackupSnapshot.objects.select_related("switch"), id=snapshot_id)
    filename = f"{snapshot.switch.name}_{snapshot.config_type}_{snapshot.created_at:%Y%m%d_%H%M%S}.txt"
    response = HttpResponse(snapshot.content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def asset_completion_view(request):
    ports = _visible_ports_queryset().order_by("switch__name", "display_order")
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        ports = ports.filter(documentation_status=status_filter)
    grouped = (
        ports.values("switch__name", "switch_id")
        .annotate(
            total=Count("id"),
            undocumented=Count("id", filter=Q(documentation_status=Port.DocumentationStatus.UNDOCUMENTED)),
            partial=Count("id", filter=Q(documentation_status=Port.DocumentationStatus.PARTIAL)),
            documented=Count("id", filter=Q(documentation_status=Port.DocumentationStatus.DOCUMENTED)),
            needs_review=Count("id", filter=Q(documentation_status=Port.DocumentationStatus.NEEDS_REVIEW)),
        )
        .order_by("switch__name")
    )
    rows = []
    for item in grouped:
        total = item["total"] or 1
        item["percent"] = round((item["documented"] / total) * 100)
        rows.append(item)
    return render(
        request,
        "inventory/phase77/asset_completion.html",
        {
            "rows": rows,
            "status_filter": status_filter,
            "status_choices": Port.DocumentationStatus.choices,
            "ports": ports[:300],
        },
    )


@require_POST
def seed_default_job_templates_view(request):
    defaults = [
        {
            "name": "Access VLAN Change",
            "action": SSHPortActionForm.ACTION_SET_ACCESS_VLAN,
            "value_template": "100",
            "risk_level": SSHJobTemplate.RiskLevel.MEDIUM,
            "requires_approval": True,
            "description": "تغییر VLAN دسترسی با Preview قبل از اجرا.",
        },
        {
            "name": "Set Port Description",
            "action": SSHPortActionForm.ACTION_SET_DESCRIPTION,
            "value_template": "SWITCHMAP-{interface}",
            "risk_level": SSHJobTemplate.RiskLevel.LOW,
            "requires_approval": False,
            "description": "ثبت Description استاندارد برای پورت.",
        },
        {
            "name": "Safe No Shutdown",
            "action": SSHPortActionForm.ACTION_NO_SHUTDOWN,
            "value_template": "",
            "risk_level": SSHJobTemplate.RiskLevel.MEDIUM,
            "requires_approval": True,
            "description": "فعال‌سازی پورت بعد از بررسی.",
        },
        {
            "name": "PoE Off",
            "action": SSHPortActionForm.ACTION_POE_NEVER,
            "value_template": "",
            "risk_level": SSHJobTemplate.RiskLevel.HIGH,
            "requires_approval": True,
            "description": "قطع PoE؛ فقط برای Operator/Admin و بعد از تأیید.",
        },
    ]
    created = 0
    for item in defaults:
        _, was_created = SSHJobTemplate.objects.get_or_create(
            name=item["name"],
            defaults={**item, "created_by": _actor(request), "updated_by": _actor(request)},
        )
        if was_created:
            created += 1
    messages.success(request, f"{created} Job Template پیش‌فرض ساخته شد.")
    return redirect("inventory:automation_templates")


def phase77_status_json_view(request):
    return JsonResponse(
        {
            "ok": True,
            "phase": "77",
            "modules": {
                "stabilization_lock": True,
                "performance": True,
                "asset_documentation": True,
                "controlled_refactor": True,
                "automation_templates": True,
                "config_backup_diff": True,
                "noc_dashboard": True,
            },
            "urls": {
                "noc": reverse("inventory:phase77_noc_dashboard"),
                "automation": reverse("inventory:automation_templates"),
                "config_backups": reverse("inventory:config_backups"),
                "asset_completion": reverse("inventory:asset_completion"),
            },
        }
    )
