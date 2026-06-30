from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path.cwd()
CSS = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase78.css"
MARKER = "PHASE78_2_ALARM_BADGE_LAYOUT_FIX"

CSS_BLOCK = r'''

/* PHASE78_2_ALARM_BADGE_LAYOUT_FIX: override generic .phase77-kpi span display:block. */
.phase77-kpi .phase78-severity-split {
    display: flex !important;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;
    direction: ltr;
    unicode-bidi: isolate;
    flex-wrap: wrap;
}
.phase77-kpi .phase78-severity-split .phase78-badge {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    gap: 5px;
    width: auto;
    min-width: 0;
    direction: ltr;
    unicode-bidi: isolate;
    white-space: nowrap;
    text-align: center;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 12px;
    line-height: 1.1;
    font-weight: 900;
}
.phase77-kpi .phase78-severity-split .phase78-badge .ltr {
    display: inline !important;
    margin: 0;
    font-size: 12px;
    color: inherit;
    line-height: 1.1;
}
'''


def fail(msg: str) -> None:
    print(f"PHASE78_2_FAIL {msg}")
    raise SystemExit(1)


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "backups" / f"phase78_2_alarm_badge_layout_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        rel = path.relative_to(ROOT)
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    return backup_dir


def main() -> None:
    if not CSS.exists():
        fail(f"missing css: {CSS}")

    css_text = CSS.read_text(encoding="utf-8")
    if "PHASE78_1_ALARM_BADGE_UI" not in css_text:
        fail("phase78.1 badge css marker not found; apply Phase78.1 first")

    backup_dir = backup(CSS)

    if MARKER not in css_text:
        CSS.write_text(css_text.rstrip() + CSS_BLOCK + "\n", encoding="utf-8", newline="\n")
        print("PHASE78_2_CSS_PATCHED")
    else:
        print("PHASE78_2_CSS_ALREADY_PATCHED")

    print(f"PHASE78_2_PATCH_OK backup_dir={backup_dir}")


if __name__ == "__main__":
    main()
