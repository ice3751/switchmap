import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ok_items = []
warn_items = []
fail_items = []


def ok(label):
    ok_items.append(label)


def warn(label):
    warn_items.append(label)


def fail(label):
    fail_items.append(label)


def has_file(rel):
    path = ROOT / rel
    if path.exists() and path.is_file():
        ok(f"file:{rel}: OK")
        return True
    fail(f"file:{rel}: missing")
    return False


def file_contains(rel, tokens, fail_missing=True):
    path = ROOT / rel
    if not path.exists():
        if fail_missing:
            fail(f"marker:{rel}: file missing")
        else:
            warn(f"marker:{rel}: file missing")
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        fail(f"marker:{rel}: read error: {exc}")
        return
    missing = [token for token in tokens if token not in text]
    if missing:
        if fail_missing:
            fail(f"marker:{rel}: missing {', '.join(missing)}")
        else:
            warn(f"marker:{rel}: missing {', '.join(missing)}")
    else:
        ok(f"marker:{rel}: OK")


try:
    import django
    django.setup()
except Exception as exc:
    print("PHASE79_0_PREFLIGHT_REPORT")
    print("OK_COUNT=0")
    print("WARNING_COUNT=0")
    print("FAIL_COUNT=1")
    print("\n[FAIL]")
    print(f"FAIL django_setup: {exc}")
    print("PHASE79_0_PREFLIGHT_FAIL")
    sys.exit(1)

from django.core.checks import run_checks
from django.db import connection
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from inventory import models
from inventory.models import AlarmNotification, Port, PortActionLog, SfpMonitorSnapshot, Switch

# 1. Django/system checks
try:
    check_errors = run_checks()
    if check_errors:
        for item in check_errors:
            fail(f"django_check:{item.id}: {item.msg}")
    else:
        ok("django_check: OK")
except Exception as exc:
    fail(f"django_check: error: {exc}")

# 2. Required URL names from stable baseline and Phase 77/78
required_urls = [
    "switch_list",
    "switchmap_dashboard_data",
    "alarm_center",
    "sfp_monitor",
    "topology",
    "backup_center",
    "action_logs",
    "asset_documentation",
    "switchmap_ajax_ssh_port_action",
    "ssh_action_preview",
    "port_payload_json",
    "phase77_noc_dashboard",
    "phase77_status_json",
    "automation_templates",
    "config_backups",
    "asset_completion",
    "phase78_alarm_cleanup",
    "phase78_alarm_recheck",
    "phase78_alarm_resolve_stale",
    "phase78_alarm_cleanup_status_json",
]
for name in required_urls:
    try:
        if name == "port_payload_json":
            reverse(f"inventory:{name}", kwargs={"port_id": 1})
        else:
            reverse(f"inventory:{name}")
        ok(f"url:{name}: OK")
    except NoReverseMatch:
        fail(f"url:{name}: missing")
    except Exception as exc:
        fail(f"url:{name}: error: {exc}")

# 3. Model/class checks
required_models = [
    "Switch",
    "Port",
    "PortActionLog",
    "PortDocumentationHistory",
    "CiscoSyslogEntry",
    "SfpMonitorSnapshot",
    "AlarmNotification",
    "SystemAuditLog",
    "SSHJobTemplate",
    "ConfigBackupSnapshot",
]
for name in required_models:
    if hasattr(models, name):
        ok(f"model:{name}: OK")
    else:
        fail(f"model:{name}: missing")

# 4. Fields needed for Phase79 design
port_fields = {field.name for field in Port._meta.get_fields()}
required_port_fields = [
    "switch",
    "interface_name",
    "display_order",
    "status",
    "connected_device",
    "description",
    "vlan",
    "port_mode",
    "access_vlan",
    "native_vlan",
    "voice_vlan",
    "trunk_vlans",
    "poe_enabled",
    "poe_admin_status",
    "poe_detection_status",
    "owner",
    "device_type",
    "ip_address",
    "mac_address",
    "mac_addresses",
    "mac_count",
    "neighbor_source",
    "neighbor_device",
    "neighbor_port",
    "neighbor_ip",
    "snmp_last_poll",
    "discovery_last_poll",
    "updated_at",
]
for field in required_port_fields:
    if field in port_fields:
        ok(f"field:Port.{field}: OK")
    else:
        fail(f"field:Port.{field}: missing")

alarm_fields = {field.name for field in AlarmNotification._meta.get_fields()}
for field in ["switch", "port", "fingerprint", "category", "severity", "status", "title", "message", "first_seen", "last_seen", "resolved_at"]:
    if field in alarm_fields:
        ok(f"field:AlarmNotification.{field}: OK")
    else:
        fail(f"field:AlarmNotification.{field}: missing")

# 5. Database table visibility and counts
try:
    table_names = set(connection.introspection.table_names())
    for model in [Switch, Port, PortActionLog, SfpMonitorSnapshot, AlarmNotification]:
        table = model._meta.db_table
        if table in table_names:
            ok(f"table:{table}: OK")
        else:
            fail(f"table:{table}: missing")
except Exception as exc:
    fail(f"db:introspection: {exc}")

try:
    switch_count = Switch.objects.count()
    port_count = Port.objects.count()
    active_alarm_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    critical_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count()
    warning_count = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count()
    sfp_count = SfpMonitorSnapshot.objects.count()
    action_count = PortActionLog.objects.count()
    down_ports = Port.objects.filter(status=Port.Status.DOWN).count()
    down_with_last_data = Port.objects.filter(status=Port.Status.DOWN).exclude(connected_device="").count()
    down_with_neighbor = Port.objects.filter(status=Port.Status.DOWN).exclude(neighbor_device="").count()
    down_with_mac = Port.objects.filter(status=Port.Status.DOWN).exclude(mac_addresses="").count() + Port.objects.filter(status=Port.Status.DOWN).exclude(mac_address="").count()
    snmp_timeout_switches = Switch.objects.filter(snmp_enabled=True).exclude(snmp_last_error="").count()

    ok(f"data:switches:{switch_count}")
    ok(f"data:ports:{port_count}")
    ok(f"data:sfp_snapshots:{sfp_count}")
    ok(f"data:port_action_logs:{action_count}")
    ok(f"data:down_ports:{down_ports}")
    ok(f"data:down_ports_connected_device:{down_with_last_data}")
    ok(f"data:down_ports_neighbor:{down_with_neighbor}")
    ok(f"data:down_ports_mac_data:{down_with_mac}")
    ok(f"data:active_alarms:{active_alarm_count}")
    ok(f"data:critical_alarms:{critical_count}")
    ok(f"data:warning_alarms:{warning_count}")
    ok(f"data:snmp_timeout_switches:{snmp_timeout_switches}")

    if active_alarm_count:
        warn(f"monitoring:active_alarms:{active_alarm_count} operational alarms present")
    if snmp_timeout_switches:
        warn(f"monitoring:snmp_timeout_switches:{snmp_timeout_switches} devices have SNMP errors")
    if down_ports and not (down_with_last_data or down_with_neighbor or down_with_mac):
        warn("phase79:last_connected_source:no existing down-port last-device data found")
except Exception as exc:
    fail(f"db:counts: {exc}")

# 6. File/marker checks: do not modify; only verify baseline surfaces exist
files = [
    "inventory/templates/inventory/base.html",
    "inventory/templates/inventory/switch_list.html",
    "inventory/templates/inventory/switch_detail.html",
    "inventory/templates/inventory/alarm_center.html",
    "inventory/templates/inventory/phase77/noc_dashboard.html",
    "inventory/templates/inventory/phase77/automation_templates.html",
    "inventory/templates/inventory/phase77/config_backups.html",
    "inventory/templates/inventory/phase77/asset_completion.html",
    "inventory/templates/inventory/phase78/alarm_cleanup.html",
    "inventory/static/inventory/switchmap.js",
    "inventory/static/inventory/css/switchmap-dashboard-stable-main.css",
    "inventory/static/inventory/css/switchmap-phase77.css",
    "inventory/static/inventory/css/switchmap-phase78.css",
]
for rel in files:
    has_file(rel)

file_contains("inventory/templates/inventory/phase78/alarm_cleanup.html", ["Operational Alarm Cleanup", "Recheck", "Active Alarms"], fail_missing=True)
file_contains("inventory/static/inventory/switchmap.js", ["switchmap", "port"], fail_missing=True)
file_contains("inventory/templates/inventory/switch_list.html", ["quick", "port"], fail_missing=False)

# 7. Existing single SSH action surface. Multi action must be additive in next phase.
try:
    from inventory.forms import SSHPortActionForm
    choices = list(getattr(SSHPortActionForm, "ACTION_CHOICES", []))
    if choices:
        ok(f"ssh:single_action_choices:{len(choices)}")
    else:
        warn("ssh:single_action_choices:empty_or_missing")
except Exception as exc:
    warn(f"ssh:action_choices:inspect_failed:{exc}")

try:
    from inventory.ssh_tools import build_port_commands, run_port_action
    ok("ssh:build_port_commands: OK")
    ok("ssh:run_port_action: OK")
except Exception as exc:
    fail(f"ssh:tools_import: {exc}")

try:
    from inventory.access_control import can_run_ssh_action, operator_or_admin_required, view_required
    ok("access:can_run_ssh_action: OK")
    ok("access:operator_or_admin_required: OK")
    ok("access:view_required: OK")
except Exception as exc:
    fail(f"access:import: {exc}")

# 8. Phase79 next-step readiness summary
if hasattr(models, "PortLinkHistory") or hasattr(models, "PortConnectionHistory"):
    ok("phase79:port_connection_history_model: already_exists")
else:
    warn("phase79:port_connection_history_model:missing_expected_next_migration")

print("PHASE79_0_PREFLIGHT_REPORT")
print(f"OK_COUNT={len(ok_items)}")
print(f"WARNING_COUNT={len(warn_items)}")
print(f"FAIL_COUNT={len(fail_items)}")
print("\n[OK]")
for item in ok_items:
    print("OK " + item)
print("\n[WARNING]")
if warn_items:
    for item in warn_items:
        print("WARNING " + item)
else:
    print("- none")
print("\n[FAIL]")
if fail_items:
    for item in fail_items:
        print("FAIL " + item)
else:
    print("- none")

if fail_items:
    print("PHASE79_0_PREFLIGHT_FAIL")
    sys.exit(1)
print("PHASE79_0_PREFLIGHT_OK")
