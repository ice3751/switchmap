from pathlib import Path
BASE = Path(__file__).resolve().parent
path = BASE / "inventory" / "templates" / "inventory" / "includes" / "nexus_svg.html"
if not path.exists():
    raise SystemExit("MISSING_NEXUS_TEMPLATE")
text = path.read_text(encoding="utf-8")
required = [
    "--nexus-main-w:clamp(16px,1.7vw,23px)",
    "grid-template-columns:repeat(24,var(--nexus-main-w))",
    "height:var(--nexus-main-h)",
    "grid-template-columns:max-content max-content",
    "NEXUS",
]
for item in required:
    if item not in text:
        raise SystemExit(f"NEXUS_TUNE_CHECK_FAILED: {item}")
print("NEXUS_DASHBOARD_TUNE_SMOKE_TEST_OK")
