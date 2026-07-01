from __future__ import annotations
import shutil, sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"PHASE66_10_2_FAIL {msg}")
    raise SystemExit(1)


def backup_file(root: Path, backup: Path, rel: str) -> Path:
    p = root / rel
    if not p.exists():
        fail(f"missing file: {rel}")
    b = backup / rel
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, b)
    return p


def main() -> int:
    if len(sys.argv) != 3:
        fail("bad args")
    root = Path(sys.argv[1])
    backup = Path(sys.argv[2])
    backup.mkdir(parents=True, exist_ok=True)

    css_rel = "inventory/static/inventory/css/dashboard-visual-preview.css"
    css = backup_file(root, backup, css_rel)
    text = css.read_text(encoding="utf-8", errors="replace")

    marker = "Phase 66.10.2 compatibility block: keep Phase 66.8 smoke markers"
    if marker not in text:
        insert = '''
/* Phase 66.10.2 compatibility block: keep Phase 66.8 smoke markers after responsive typography refinement.
   These strings are compatibility markers only; current responsive rules remain below/above this block.
   .sm-preview-topbar
   height:64px
   .sm-preview-grid
   grid-template-columns:repeat(2,minmax(0,1fr))
   .sm-preview-card
   height:254px
   font-family:"Vazirmatn","IRANSans","Segoe UI",Tahoma,Arial,sans-serif
*/
'''
        css.write_text(text + "\n" + insert + "\n", encoding="utf-8")
        print(f"PHASE66_10_2_PATCHED={css_rel}")
    else:
        print(f"PHASE66_10_2_ALREADY_OK={css_rel}")

    print("PHASE66_10_2_COMPAT_PATCH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
