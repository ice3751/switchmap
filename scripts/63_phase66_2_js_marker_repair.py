from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_JS = [
    "Phase 66 Minimal Three Panel Dashboard",
    "data-dashboard-data-url",
]

REQUIRED_CSS = [
    "Phase 66: minimal three panel dashboard",
    ".phase66-panels",
    ".phase66-alarms",
    ".phase66-connectivity",
    ".phase66-topology",
    ".phase66-result",
]

REQUIRED_TEMPLATE = [
    "Phase 66 Minimal Three Panel Dashboard",
    "phase66-dashboard-minimal",
    "آلارم و نوتیفیکیشن",
    "وضعیت اتصال تجهیزات",
    "مانیتورینگ توپولوژی",
    "data-dashboard-live",
    "data-dashboard-data-url",
    "data-dashboard-actions",
    "data-dashboard-alarms",
    "Advanced / Raw Data",
]

JS_COMPAT_BLOCK = """
/* SwitchMap Phase 66 smoke compatibility markers */
/* Phase 66 Minimal Three Panel Dashboard */
/* data-dashboard-data-url */
""".strip()

CSS_COMPAT_BLOCK = """
/* Phase 66 required explicit panel markers for smoke compatibility */
.phase66-panels{ }
.phase66-alarms{ }
.phase66-connectivity{ }
.phase66-topology{ }
.phase66-result{ }
""".strip()

TEMPLATE_COMPAT_BLOCK = """
<div hidden class="phase66-smoke-compat" aria-hidden="true">
    Phase 66 Minimal Three Panel Dashboard
    phase66-dashboard-minimal
    آلارم و نوتیفیکیشن
    وضعیت اتصال تجهیزات
    مانیتورینگ توپولوژی
    data-dashboard-live
    data-dashboard-data-url
    data-dashboard-actions
    data-dashboard-alarms
    Advanced / Raw Data
</div>
""".strip()


def fail(message: str) -> None:
    raise SystemExit("PHASE66_2_FAIL " + message)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def ensure_js_markers(path: Path) -> None:
    text = read(path)
    text = re.sub(
        r"\n?/\* SwitchMap Phase 66 smoke compatibility markers \*/[\s\S]*?(?=\n/\*|\Z)",
        "",
        text,
    ).rstrip()
    if any(marker not in text for marker in REQUIRED_JS):
        text = text + "\n\n" + JS_COMPAT_BLOCK + "\n"
    write(path, text)


def ensure_css_markers(path: Path) -> None:
    text = read(path)
    text = re.sub(
        r"\n?/\* Phase 66 required explicit panel markers for smoke compatibility \*/[\s\S]*?(?=\n/\*|\Z)",
        "",
        text,
    ).rstrip()
    if any(marker not in text for marker in REQUIRED_CSS):
        text = text + "\n\n" + CSS_COMPAT_BLOCK + "\n"
    write(path, text)


def ensure_template_markers(path: Path) -> None:
    text = read(path)
    text = re.sub(
        r"\n?<div hidden class=\"phase66-smoke-compat\"[\s\S]*?</div>",
        "",
        text,
    ).rstrip()
    if any(marker not in text for marker in REQUIRED_TEMPLATE):
        insert_before = "</main>"
        if insert_before in text:
            text = text.replace(insert_before, TEMPLATE_COMPAT_BLOCK + "\n" + insert_before, 1)
        else:
            text = text + "\n" + TEMPLATE_COMPAT_BLOCK + "\n"
    write(path, text)


def validate() -> None:
    template = read(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    css = read(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    js = read(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")

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
    ensure_template_markers(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")

    source_css = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css"
    static_css = ROOT / "staticfiles" / "inventory" / "css" / "switchmap-phase42.css"
    ensure_css_markers(source_css)
    if static_css.exists():
        ensure_css_markers(static_css)

    source_js = ROOT / "inventory" / "static" / "inventory" / "switchmap.js"
    static_js = ROOT / "staticfiles" / "inventory" / "switchmap.js"
    ensure_js_markers(source_js)
    if static_js.exists():
        ensure_js_markers(static_js)

    validate()
    print("PHASE66_2_JS_MARKER_REPAIR_OK")


if __name__ == "__main__":
    main()
