from pathlib import Path
import json
import os
import py_compile
import sys
import traceback

# PHASE79_10_1_VERIFY_SCRIPT_FIX
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

OK = 0
WARN = 0
FAIL = 0


def _print(level, name, detail=""):
    if detail:
        print(f"{level} {name}: {detail}")
    else:
        print(f"{level} {name}")


def ok(name, detail=""):
    global OK
    OK += 1
    _print("OK", name, detail)


def warn(name, detail=""):
    global WARN
    WARN += 1
    _print("WARNING", name, detail)


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    _print("FAIL", name, detail)


def check(name, cond, detail_ok="", detail_fail=""):
    if cond:
        ok(name, detail_ok)
    else:
        fail(name, detail_fail)


def read_text(rel):
    path = ROOT / rel
    if not path.exists():
        fail(f"missing_file:{rel}")
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        fail(f"read_file:{rel}", str(exc))
        return ""


print("PHASE79_10_FINAL_VERIFY_START")
print(f"ROOT={ROOT}")

# 1) Source markers for Phase 79 features.
marker_checks = [
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_6_5_LAST_CONNECTED_OVERRIDE"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_7_POST_SSH_PORT_REFRESH"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_MULTI_SSH_ACTION"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_1_MULTI_SSH_UI_RESULT_ORDER"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
    ("inventory/static/inventory/switchmap.css", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
    ("inventory/templates/inventory/base.html", "phase79-8-2-platform-action-guard"),
    ("inventory/templates/inventory/alarm_center.html", "PHASE79_9_2_COMPACT_ALARM_FILTER"),
    ("inventory/templates/inventory/alarm_center.html", "alarm-filter-icon"),
    ("inventory/templates/inventory/alarm_center.html", "alarm-inline-filter-form"),
    ("inventory/ssh_tools.py", "PLATFORM_UNSUPPORTED_ACTIONS"),
    ("inventory/ssh_tools.py", "unsupported_action_reason"),
    ("inventory/urls.py", "ssh-port-multi-action/"),
    ("inventory/urls.py", "port/<int:port_id>/payload/"),
]
for rel, marker in marker_checks:
    text = read_text(rel)
    check(f"marker:{rel}:{marker}", marker in text)

alarm_template = read_text("inventory/templates/inventory/alarm_center.html")
check(
    "alarm_filter_large_panel_removed",
    "phase79-9-alarm-filter-grid" not in alarm_template and "Filter Alarms</strong>" not in alarm_template,
)

# 2) Staticfiles sync markers after collectstatic.
static_marker_checks = [
    ("staticfiles/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
    ("staticfiles/inventory/switchmap.css", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
]
for rel, marker in static_marker_checks:
    path = ROOT / rel
    if not path.exists():
        warn(f"staticfiles_missing:{rel}", "collectstatic may not have copied this path")
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    check(f"staticfiles_marker:{rel}:{marker}", marker in text)

# 3) Python syntax checks for touched backend files.
for rel in ["inventory/ssh_tools.py", "inventory/views.py", "inventory/ssh_views.py", "inventory/urls.py"]:
    path = ROOT / rel
    if not path.exists():
        fail(f"py_compile_missing:{rel}")
        continue
    try:
        py_compile.compile(str(path), doraise=True)
        ok(f"py_compile:{rel}")
    except Exception as exc:
        fail(f"py_compile:{rel}", str(exc))

# 4) Django/ORM/read-only HTTP checks.
try:
    import django

    django.setup()
    ok("django_setup")

    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import resolve
    from inventory.models import AlarmNotification, Port, Switch

    switches = Switch.objects.count()
    ports = Port.objects.count()
    active_alarms = AlarmNotification.objects.filter(status="active").count()
    resolved_alarms = AlarmNotification.objects.filter(status="resolved").count()
    critical_alarms = AlarmNotification.objects.filter(status="active", severity="critical").count()
    warning_alarms = AlarmNotification.objects.filter(status="active", severity="warning").count()

    check("db_switch_count", switches > 0, f"switches={switches}", f"switches={switches}")
    check("db_port_count", ports > 0, f"ports={ports}", f"ports={ports}")
    ok("db_alarm_summary", f"active={active_alarms} resolved={resolved_alarms} critical={critical_alarms} warning={warning_alarms}")

    if active_alarms:
        warn("active_operational_alarms", f"active={active_alarms}; not a software failure")

    # URL resolver checks.
    for path, expected_name in [
        ("/ssh-port-multi-action/", "switchmap_ajax_multi_ssh_port_action"),
        ("/port/1/payload/", "port_payload_json"),
    ]:
        try:
            match = resolve(path)
            check(f"url_resolve:{path}", match.url_name == expected_name, match.url_name, f"got={match.url_name}")
        except Exception as exc:
            fail(f"url_resolve:{path}", str(exc))

    # Platform guard check without opening SSH.
    try:
        from inventory.ssh_tools import SshActionError, build_port_commands, unsupported_action_reason

        class DummyPortMode:
            TRUNK = "trunk"

        class DummySwitch:
            def __init__(self, name, model):
                self.name = name
                self.model = model
                self.vendor = "cisco"

        class DummyPort:
            PortMode = DummyPortMode

            def __init__(self, switch):
                self.switch = switch
                self.interface_name = "Ethernet1/1"
                self.port_mode = "access"

        nexus = DummySwitch("NEXUS", "Cisco Nexus")
        catalyst = DummySwitch("Edari-1", "WS-C3850-48P")

        reason = unsupported_action_reason(nexus, "poe_auto")
        check("platform_guard_nexus_poe_reason", bool(reason), detail_ok="reason_present")
        try:
            build_port_commands(DummyPort(nexus), "poe_auto", switch=nexus)
            fail("platform_guard_nexus_poe_block")
        except SshActionError:
            ok("platform_guard_nexus_poe_block")
        build_port_commands(DummyPort(nexus), "shutdown", switch=nexus)
        ok("platform_guard_nexus_shutdown_allowed")
        build_port_commands(DummyPort(catalyst), "poe_auto", switch=catalyst)
        ok("platform_guard_catalyst_poe_allowed")
    except Exception as exc:
        fail("platform_guard_check", f"{exc}\n{traceback.format_exc()}")

    # HTTP checks with superuser login.
    User = get_user_model()
    user = User.objects.filter(is_superuser=True, is_active=True).first() or User.objects.filter(is_active=True).first()
    if not user:
        fail("http_login_user", "no active user found")
    else:
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(user)
        ok("http_login_user", getattr(user, "username", "user"))

        http_targets = [
            ("/", "dashboard"),
            ("/alarms/?status=active", "alarm_center_active"),
            ("/alarms/?status=active&q=NEXUS", "alarm_center_query"),
        ]

        nexus_switch = Switch.objects.filter(management_ip="172.20.1.12").first() or Switch.objects.filter(model__icontains="nexus").first()
        if nexus_switch:
            http_targets.append((f"/switch/{nexus_switch.id}/", "nexus_switch_detail"))
        else:
            warn("nexus_switch_missing", "management_ip=172.20.1.12 not found")

        for url, label in http_targets:
            try:
                response = client.get(url)
                check(f"http_get:{label}", response.status_code == 200, f"status={response.status_code}", f"status={response.status_code}")
                if label.startswith("alarm_center") and response.status_code == 200:
                    body = response.content.decode("utf-8", errors="ignore")
                    check(f"alarm_compact_filter_rendered:{label}", "alarm-inline-filter-form" in body and "alarm-filter-icon" in body)
            except Exception as exc:
                fail(f"http_get:{label}", str(exc))

        # Payload and Last/Current connection checks for known Nexus ports where available.
        if nexus_switch:
            wanted = ["Ethernet1/1", "Ethernet1/32", "Ethernet1/35", "Ethernet1/40", "Ethernet1/43"]
            sample_ports = list(Port.objects.filter(switch=nexus_switch, interface_name__in=wanted).order_by("interface_name"))
            if not sample_ports:
                warn("nexus_payload_ports_missing", ",".join(wanted))
            for port in sample_ports:
                try:
                    response = client.get(f"/port/{port.id}/payload/")
                    check(f"payload_http:{port.interface_name}", response.status_code == 200, f"port_id={port.id}", f"status={response.status_code}")
                    data = response.json()
                    payload = data.get("port") if isinstance(data, dict) and isinstance(data.get("port"), dict) else data
                    check(f"payload_has_port_wrapper:{port.interface_name}", isinstance(payload, dict))
                    check(f"payload_has_last_connection:{port.interface_name}", isinstance(payload, dict) and "last_connection" in payload)
                    lc = (payload or {}).get("last_connection") or {}
                    identity = lc.get("identity") or lc.get("message") or "-"
                    ok(
                        f"payload_summary:{port.interface_name}",
                        f"status={port.status} neighbor={port.neighbor_device or '-'} lc_available={lc.get('available')} identity={identity}",
                    )
                except Exception as exc:
                    fail(f"payload_check:{port.interface_name}", str(exc))

except Exception as exc:
    fail("django_block", f"{exc}\n{traceback.format_exc()}")

print("")
print(f"FINAL_OK_COUNT={OK}")
print(f"FINAL_WARNING_COUNT={WARN}")
print(f"FINAL_FAIL_COUNT={FAIL}")
if FAIL:
    print("PHASE79_10_FINAL_VERIFY_FAIL")
    raise SystemExit(1)
print("PHASE79_10_FINAL_VERIFY_OK")
