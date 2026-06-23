from pathlib import Path
BASE = Path(__file__).resolve().parent
path = BASE / "inventory" / "templates" / "inventory" / "includes" / "nexus_svg.html"
if not path.exists():
    raise SystemExit("MISSING_NEXUS_TEMPLATE")
text = path.read_text(encoding="utf-8")
required = [
    "nexus-map-dashboard",
    "grid-template-columns:repeat(24,minmax(0,1fr))",
    "aspect-ratio:1.45/1",
    "nexus-uplink-zone",
    "forloop.counter <= 48",
    "forloop.counter > 48",
]
for item in required:
    if item not in text:
        raise SystemExit(f"NEXUS_VISUAL_CHECK_FAILED: {item}")
print("NEXUS_VISUAL_SMOKE_TEST_OK")
