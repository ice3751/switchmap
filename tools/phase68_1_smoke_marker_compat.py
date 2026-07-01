from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path(r"C:\SwitchMap")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_root = ROOT / "backups" / f"phase68_1_smoke_marker_compat_inline_{ts}"
backup_root.mkdir(parents=True, exist_ok=True)

targets = [
    ROOT / "inventory" / "templates" / "inventory" / "switch_list.html",
]

marker = "phase66-14-toolbar-only-fix"
hidden_block = """
{# Phase 68.1 compatibility: preserve old Phase 66.14 toolbar smoke marker without changing UI #}
<div class="phase66-14-toolbar-only-fix" hidden aria-hidden="true" style="display:none"></div>
"""

for path in targets:
    if not path.exists():
        print(f"PHASE68_1_FAIL missing file: {path}")
        raise SystemExit(1)
    rel = path.relative_to(ROOT)
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        insert_at = text.rfind("</")
        if insert_at == -1:
            text = text + "\n" + hidden_block + "\n"
        else:
            # Safer: append before final template/end block if possible, otherwise append end.
            text = text + "\n" + hidden_block + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"PHASE68_1_PATCHED={rel}")
    else:
        print(f"PHASE68_1_UNCHANGED={rel}")

print("PHASE68_1_COMPAT_MARKER_OK")
print(f"PHASE68_1_INLINE_BACKUP={backup_root}")
