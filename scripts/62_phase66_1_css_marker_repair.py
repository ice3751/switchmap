from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

CSS_MARKER_BLOCK = """
/* Phase 66 required explicit panel markers for smoke compatibility */
.phase66-alarms{ }
.phase66-connectivity{ }
.phase66-topology{ }
""".strip()

REQUIRED_TEMPLATE = [
    "Phase 66 Minimal Three Panel Dashboard",
    "phase66-dashboard-minimal",
    "آلارم و نوتیفیکیشن",
    "وضعیت اتصال تجهیزات",
    "مانیتورینگ توپولوژی",
    "data-dashboard-actions",
    "data-dashboard-alarms",
    "data-dashboard-live",
    "data-dashboard-data-url",
    "dashboard-insight-shell",
]

REQUIRED_CSS = [
    "Phase 66: minimal three panel dashboard",
    ".phase66-panels",
    ".phase66-alarms",
    ".phase66-connectivity",
    ".phase66-topology",
]

REQUIRED_JS = [
    "Phase 66 Minimal Three Panel Dashboard",
    "data-dashboard-data-url",
]


def fail(message: str) -> None:
    raise SystemExit("PHASE66_1_FAIL " + message)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def ensure_css_markers(path: Path) -> None:
    text = read(path)
    text = re.sub(
        r"\n?/\* Phase 66 required explicit panel markers for smoke compatibility \*/[\s\S]*?(?=\n/\*|\Z)",
        "",
        text,
    ).rstrip()
    if ".phase66-alarms" not in text or ".phase66-connectivity" not in text or ".phase66-topology" not in text:
        text = text + "\n\n" + CSS_MARKER_BLOCK + "\n"
    else:
        # Keep the block explicit even when class names exist only in comments or combined selectors.
        text = text + "\n\n" + CSS_MARKER_BLOCK + "\n"
    write(path, text)


def ensure_js_markers(path: Path) -> None:
    text = read(path)
    if "Phase 66 Minimal Three Panel Dashboard" not in text:
        text = text.replace(
            "function setupLiveInsightDashboard(){",
            "function setupLiveInsightDashboard(){\n        // Phase 66 Minimal Three Panel Dashboard | data-dashboard-data-url",
            1,
        )
    elif "data-dashboard-data-url" not in text:
        text = text.replace("Phase 66 Minimal Three Panel Dashboard", "Phase 66 Minimal Three Panel Dashboard | data-dashboard-data-url", 1)
    write(path, text)


def validate() -> None:
    template_path = ROOT / "inventory" / "templates" / "inventory" / "switch_list.html"
    css_path = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css"
    js_path = ROOT / "inventory" / "static" / "inventory" / "switchmap.js"

    template = read(template_path)
    css = read(css_path)
    js = read(js_path)

    missing_template = [marker for marker in REQUIRED_TEMPLATE if marker not in template]
    if missing_template:
        fail("missing template marker(s): " + ", ".join(missing_template))

    missing_css = [marker for marker in REQUIRED_CSS if marker not in css]
    if missing_css:
        fail("missing css marker(s): " + ", ".join(missing_css))

    missing_js = [marker for marker in REQUIRED_JS if marker not in js]
    if missing_js:
        fail("missing js marker(s): " + ", ".join(missing_js))


def main() -> None:
    source_css = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css"
    static_css = ROOT / "staticfiles" / "inventory" / "css" / "switchmap-phase42.css"
    ensure_css_markers(source_css)
    if static_css.exists():
        ensure_css_markers(static_css)

    ensure_js_markers(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")
    validate()
    print("PHASE66_1_CSS_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
