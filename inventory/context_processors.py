from .forms import SSHPortActionForm
from .access_control import (
    allowed_ssh_actions,
    can_admin_panel,
    can_edit_port,
    can_import_cisco_logs,
    can_import_switches,
    can_manage_users,
    can_manage_backups,
    can_pull_cisco_logs,
    can_refresh,
    can_run_ssh,
    can_sfp_poll,
    user_role,
)


def _alarm_counts():
    try:
        from .models import AlarmNotification

        active_qs = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
        items = list(
            active_qs.select_related("switch", "port")
            .order_by("severity", "-last_seen", "-id")[:6]
        )
        severity_order = {
            AlarmNotification.Severity.CRITICAL: 0,
            AlarmNotification.Severity.WARNING: 1,
            AlarmNotification.Severity.INFO: 2,
        }
        items.sort(key=lambda item: (severity_order.get(item.severity, 9), item.switch.name if item.switch else "", item.title))
        return {
            "active": active_qs.count(),
            "critical": active_qs.filter(severity=AlarmNotification.Severity.CRITICAL).count(),
            "warning": active_qs.filter(severity=AlarmNotification.Severity.WARNING).count(),
            "items": items,
        }
    except Exception:
        return {"active": 0, "critical": 0, "warning": 0, "items": []}




def _switch_menu_groups():
    try:
        from django.urls import reverse
        from .models import Switch

        group_order = [
            ("cisco_3850", "Cisco 3850"),
            ("cisco_nexus", "Cisco Nexus"),
            ("mikrotik_switch", "MikroTik Switches"),
            ("mikrotik_router", "MikroTik Routers"),
            ("mikrotik_ap", "MikroTik AP / CAP"),
            ("other", "Other / Unknown"),
        ]
        buckets = {key: {"key": key, "title": title, "items": []} for key, title in group_order}
        switches = Switch.objects.filter(is_active=True).only(
            "id", "name", "management_ip", "device_family", "device_role", "model", "vendor", "topology_position"
        ).order_by("topology_position", "name")
        for sw in switches:
            key = sw.device_family or "other"
            if key not in buckets:
                key = "other"
            try:
                role = sw.get_device_role_display()
            except Exception:
                role = sw.device_role or ""
            buckets[key]["items"].append({
                "id": sw.id,
                "name": sw.name,
                "ip": str(sw.management_ip),
                "model": sw.model or "",
                "role": role,
                "url": reverse("inventory:switch_detail", args=[sw.id]),
            })
        groups = []
        for key, title in group_order:
            group = buckets[key]
            group["count"] = len(group["items"])
            groups.append(group)
        return groups
    except Exception:
        return []


def switchmap_access(request):
    user = getattr(request, "user", None)
    alarm_counts = _alarm_counts()
    return {
        "swmap_role": user_role(user),
        "swmap_alarm_active_count": alarm_counts["active"],
        "swmap_alarm_critical_count": alarm_counts["critical"],
        "swmap_alarm_warning_count": alarm_counts["warning"],
        "swmap_alarm_sidebar_items": alarm_counts.get("items", []),
        "swmap_can_admin": can_admin_panel(user),
        "swmap_can_manage_users": can_manage_users(user),
        "swmap_can_manage_backups": can_manage_backups(user),
        "swmap_can_edit_port": can_edit_port(user),
        "swmap_can_refresh": can_refresh(user),
        "swmap_can_ssh": can_run_ssh(user),
        "swmap_can_sfp_poll": can_sfp_poll(user),
        "swmap_can_import_switches": can_import_switches(user),
        "swmap_can_pull_cisco_logs": can_pull_cisco_logs(user),
        "swmap_can_import_cisco_logs": can_import_cisco_logs(user),
        "swmap_ssh_actions": allowed_ssh_actions(user, SSHPortActionForm.ACTION_CHOICES),
        "swmap_switch_menu_groups": _switch_menu_groups(),
    }
