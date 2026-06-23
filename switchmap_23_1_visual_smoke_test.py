from pathlib import Path

css_path = Path("inventory/static/inventory/switchmap.css")
text = css_path.read_text(encoding="utf-8")
required = [
    "SWITCHMAP_23_1_CISCO_3850_VISUAL_FIX_START",
    "width:1316px",
    "width:1460px",
    "nth-child(6n+7)",
    "sm-uplink-module",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("SMOKE_FAIL: missing " + ", ".join(missing))
print("SMOKE_TEST_OK")
