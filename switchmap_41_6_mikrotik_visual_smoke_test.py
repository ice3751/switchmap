from pathlib import Path

BASE = Path(__file__).resolve().parent
css = (BASE / "inventory" / "static" / "inventory" / "switchmap.css").read_text(encoding="utf-8")
tpl = (BASE / "inventory" / "templates" / "inventory" / "includes" / "mikrotik_dynamic_panel.html").read_text(encoding="utf-8")
extras = (BASE / "inventory" / "templatetags" / "switchmap_extras.py").read_text(encoding="utf-8")

required_css = [
    "Phase 41.6 - MikroTik visual tuning",
    ".mikrotik-crs354.is-dashboard .dynamic-device-face",
    ".mikrotik-rb5009.is-dashboard .dynamic-port",
    ".mikrotik-brand-chip",
    ".mikrotik-port-bay",
]
required_tpl = [
    "mikrotik-brand-bar",
    "mikrotik-brand-title",
    "mikrotik-identity-panel",
    "mikrotik-role-panel",
]
required_extras = [
    "mikrotik_ether = re.match",
    "return f\"e{mikrotik_ether.group(1)}\"",
    "return f\"sfp+{mikrotik_sfp.group(1)}\"",
]

missing = []
for token in required_css:
    if token not in css:
        missing.append(f"CSS:{token}")
for token in required_tpl:
    if token not in tpl:
        missing.append(f"TPL:{token}")
for token in required_extras:
    if token not in extras:
        missing.append(f"EXTRAS:{token}")

if missing:
    raise SystemExit("PHASE41_6_MIKROTIK_VISUAL_SMOKE_FAIL " + ", ".join(missing))
print("PHASE41_6_MIKROTIK_VISUAL_OK")
