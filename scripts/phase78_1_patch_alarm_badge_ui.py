from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path.cwd()
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "phase78" / "alarm_cleanup.html"
CSS = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase78.css"
MARKER = "PHASE78_1_ALARM_BADGE_UI"

OLD = '<span>{{ summary.critical_count }} Critical / {{ summary.warning_count }} Warning</span>'
NEW = '''<span class="phase78-severity-split" aria-label="Critical and warning alarm totals">
                <!-- PHASE78_1_ALARM_BADGE_UI -->
                <span class="phase78-badge phase78-badge-critical"><span class="ltr">{{ summary.critical_count }}</span> Critical</span>
                <span class="phase78-badge phase78-badge-warning"><span class="ltr">{{ summary.warning_count }}</span> Warning</span>
            </span>'''

CSS_BLOCK = r'''

/* PHASE78_1_ALARM_BADGE_UI: isolate mixed English/number text in RTL cards. */
.phase78-severity-split {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    direction: ltr;
    unicode-bidi: isolate;
    flex-wrap: wrap;
}
.phase78-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    direction: ltr;
    unicode-bidi: isolate;
    white-space: nowrap;
    border-radius: 999px;
    padding: 4px 9px;
    font-size: 12px;
    line-height: 1.2;
    font-weight: 900;
    border: 1px solid transparent;
}
.phase78-badge-critical {
    background: #fee2e2;
    color: #991b1b;
    border-color: #fecaca;
}
.phase78-badge-warning {
    background: #fef3c7;
    color: #92400e;
    border-color: #fde68a;
}
'''


def fail(msg: str) -> None:
    print(f"PHASE78_1_FAIL {msg}")
    raise SystemExit(1)


def backup(paths):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "backups" / f"phase78_1_alarm_badge_ui_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            rel = path.relative_to(ROOT)
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
    return backup_dir


def main() -> None:
    if not TEMPLATE.exists():
        fail(f"missing template: {TEMPLATE}")
    if not CSS.exists():
        fail(f"missing css: {CSS}")

    backup_dir = backup([TEMPLATE, CSS])

    text = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in text:
        if OLD not in text:
            fail("target active-alarm critical/warning text not found; template may be changed")
        text = text.replace(OLD, NEW, 1)
        TEMPLATE.write_text(text, encoding="utf-8", newline="\n")
        print("PHASE78_1_TEMPLATE_PATCHED")
    else:
        print("PHASE78_1_TEMPLATE_ALREADY_PATCHED")

    css_text = CSS.read_text(encoding="utf-8")
    if MARKER not in css_text:
        CSS.write_text(css_text.rstrip() + CSS_BLOCK + "\n", encoding="utf-8", newline="\n")
        print("PHASE78_1_CSS_PATCHED")
    else:
        print("PHASE78_1_CSS_ALREADY_PATCHED")

    print(f"PHASE78_1_PATCH_OK backup_dir={backup_dir}")


if __name__ == "__main__":
    main()
