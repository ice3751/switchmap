from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
checks = [
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
    ("inventory/static/inventory/switchmap.css", "PHASE79_8_2_PLATFORM_ACTION_GUARD"),
    ("inventory/templates/inventory/base.html", "phase79-8-2-platform-action-guard"),
    ("inventory/ssh_tools.py", "PLATFORM_UNSUPPORTED_ACTIONS"),
    ("inventory/ssh_tools.py", "unsupported_action_reason"),
]
fail = 0
for rel, marker in checks:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        print(f"OK marker:{rel}:{marker}")
    else:
        print(f"FAIL marker:{rel}:{marker}")
        fail += 1

try:
    py_compile.compile(str(ROOT / "inventory/ssh_tools.py"), doraise=True)
    print("OK py_compile:inventory/ssh_tools.py")
except Exception as exc:
    print(f"FAIL py_compile:inventory/ssh_tools.py:{exc}")
    fail += 1

try:
    from inventory.ssh_tools import build_port_commands, SshActionError, unsupported_action_reason

    class PortMode:
        TRUNK = "trunk"

    class Switch:
        def __init__(self, name, model):
            self.name = name
            self.model = model
            self.vendor = "cisco"

    class Port:
        PortMode = PortMode
        def __init__(self, switch):
            self.switch = switch
            self.interface_name = "Ethernet1/1"
            self.port_mode = "access"

    nexus = Switch("NEXUS", "Cisco Nexus")
    catalyst = Switch("Edari-1", "WS-C3850-48P")

    if not unsupported_action_reason(nexus, "poe_auto"):
        raise RuntimeError("nexus_poe_reason_missing")
    try:
        build_port_commands(Port(nexus), "poe_auto", switch=nexus)
        raise RuntimeError("nexus_poe_was_not_blocked")
    except SshActionError:
        pass
    build_port_commands(Port(nexus), "shutdown", switch=nexus)
    build_port_commands(Port(catalyst), "poe_auto", switch=catalyst)
    print("OK platform_guard:nexus_poe_blocked_shutdown_allowed")
except Exception as exc:
    print(f"FAIL platform_guard:{exc}")
    fail += 1

if fail:
    print("PHASE79_8_2_VERIFY_FAIL")
    raise SystemExit(1)
print("PHASE79_8_2_VERIFY_OK")
