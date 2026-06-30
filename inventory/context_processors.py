from django.core.cache import cache
from django.db.models import Count


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


SWITCHMAP_MENU_EXCLUDE_TOKENS = (
    "smoke",
    "test",
    "phase41",
    "phase42",
    "phase43",
    "phase48",
    "phase50",
    "phase55",
    "phase56",
    "switchmap-phase",
    "switchmap_phase",
)


def _is_switchmap_test_device(switch):
    if switch is None:
        return False
    blob = " ".join(
        [
            switch.name or "",
            switch.model or "",
            str(switch.management_ip or ""),
            switch.site or "",
            switch.location or "",
            switch.notes or "",
        ]
    ).lower()
    return any(token in blob for token in SWITCHMAP_MENU_EXCLUDE_TOKENS)


def _alarm_counts():
    # Phase93: performance-safe context cache refine.
    # Keep behavior unchanged, but avoid three repeated COUNT queries on every uncached page render.
    cache_key = "switchmap:phase93:alarm_counts:v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
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
        severity_totals = {
            row["severity"]: row["total"]
            for row in active_qs.values("severity").annotate(total=Count("id"))
        }
        result = {
            "active": sum(severity_totals.values()),
            "critical": severity_totals.get(AlarmNotification.Severity.CRITICAL, 0),
            "warning": severity_totals.get(AlarmNotification.Severity.WARNING, 0),
            "items": items,
        }
        cache.set(cache_key, result, 20)
        return result
    except Exception:
        return {"active": 0, "critical": 0, "warning": 0, "items": []}



def _switch_menu_groups():
    cache_key = "switchmap:phase77:switch_menu_groups:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
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
            "id", "name", "management_ip", "device_family", "device_role", "model", "vendor", "topology_position", "site", "location", "notes"
        ).order_by("topology_position", "name")
        for sw in switches:
            if _is_switchmap_test_device(sw):
                continue
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
        cache.set(cache_key, groups, 60)
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
