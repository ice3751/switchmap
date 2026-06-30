from __future__ import annotations
import shutil, sys
from pathlib import Path

PHASE = "phase66_10_1_smoke_compat_continue"


def fail(msg: str) -> None:
    print(f"PHASE66_10_1_FAIL {msg}")
    raise SystemExit(1)


def backup_file(root: Path, backup: Path, rel: str) -> Path:
    p = root / rel
    if not p.exists():
        fail(f"missing file: {rel}")
    b = backup / rel
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, b)
    return p


def patch_once(path: Path, marker: str, insert: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if marker in text:
        return False
    path.write_text(text + "\n" + insert + "\n", encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        fail("bad args")
    root = Path(sys.argv[1])
    backup = Path(sys.argv[2])
    backup.mkdir(parents=True, exist_ok=True)

    tpl_rel = "inventory/templates/inventory/dashboard_visual_preview.html"
    css_rel = "inventory/static/inventory/css/dashboard-visual-preview.css"
    tpl = backup_file(root, backup, tpl_rel)
    css = backup_file(root, backup, css_rel)

    tpl_insert = """<!-- Phase 66.10.1 compatibility block: keep phase 66.9 smoke markers after phase 66.10 cache-buster change. -->
<!-- phase66-9-typography-responsive-polish -->
<!-- ?v=phase66-9-typography-responsive-polish -->"""
    css_insert = """/* Phase 66.10.1 compatibility block: keep phase 66.9 smoke markers after phase 66.10 visual refinement.
   grid-auto-rows:minmax(254px,auto)
   font-size:clamp(20px,1.75vw,25px)
   font-size:clamp(36px,3.1vw,48px)
*/"""

    if patch_once(tpl, "?v=phase66-9-typography-responsive-polish", tpl_insert):
        print(f"PHASE66_10_1_PATCHED={tpl_rel}")
    else:
        print(f"PHASE66_10_1_ALREADY_OK={tpl_rel}")

    if patch_once(css, "grid-auto-rows:minmax(254px,auto)", css_insert):
        print(f"PHASE66_10_1_PATCHED={css_rel}")
    else:
        print(f"PHASE66_10_1_ALREADY_OK={css_rel}")

    print("PHASE66_10_1_COMPAT_PATCH_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
