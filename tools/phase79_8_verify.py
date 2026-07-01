from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = [
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_MULTI_SSH_ACTION"),
    ("inventory/static/inventory/switchmap.css", "PHASE79_8_MULTI_SSH_ACTION"),
    ("inventory/templates/inventory/base.html", "phase79-8-multi-ssh-action"),
    ("inventory/ssh_tools.py", "def run_port_multi_actions"),
    ("inventory/views.py", "def switchmap_ajax_multi_ssh_port_action"),
    ("inventory/ssh_views.py", "switchmap_ajax_multi_ssh_port_action"),
    ("inventory/urls.py", "ssh-port-multi-action/"),
]
fail = 0
for rel, marker in checks:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        print(f"OK marker:{rel}:{marker}")
    else:
        print(f"FAIL marker:{rel}:{marker}")
        fail += 1
if fail:
    raise SystemExit("PHASE79_8_VERIFY_FAIL")
print("PHASE79_8_VERIFY_OK")
