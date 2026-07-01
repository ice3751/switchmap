from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PHASE = "phase66_8_dashboard_visual_prototype"
FILES = [
    "inventory/templates/inventory/dashboard_visual_preview.html",
    "inventory/static/inventory/css/dashboard-visual-preview.css",
    "smoke_tests/switchmap_66_8_dashboard_visual_prototype_smoke_test.py",
    "docs/PHASE66_8_DASHBOARD_VISUAL_PROTOTYPE.md",
]
SMOKE_REL = "smoke_tests/switchmap_66_8_dashboard_visual_prototype_smoke_test.py"


def fail(message: str) -> None:
    print("PHASE66_8_COPY_FAIL=" + message)
    raise SystemExit(1)


def backup_file(root: Path, backup: Path, rel: str) -> None:
    dst = root / rel
    if dst.exists():
        b = backup / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, b)


def copy_files(root: Path, src: Path, backup: Path) -> None:
    for rel in FILES:
        s = src / rel
        d = root / rel
        if not s.exists():
            fail(f"source missing: {rel}")
        backup_file(root, backup, rel)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        print(f"PHASE66_8_COPIED={rel}")


def patch_urls(root: Path, backup: Path) -> None:
    rel = "inventory/urls.py"
    p = root / rel
    if not p.exists():
        fail("inventory/urls.py missing")
    text = p.read_text(encoding="utf-8", errors="replace")
    if "dashboard-preview/" in text and "dashboard_visual_preview" in text:
        print("PHASE66_8_URL_EXISTS")
        return
    backup_file(root, backup, rel)
    if "from django.views.generic import TemplateView" not in text:
        if "from django.urls import path" in text:
            text = text.replace("from django.urls import path\n", "from django.urls import path\nfrom django.views.generic import TemplateView\n", 1)
        else:
            text = "from django.views.generic import TemplateView\n" + text
    marker = "urlpatterns = [\n"
    route = "    path(\"dashboard-preview/\", view_required(TemplateView.as_view(template_name=\"inventory/dashboard_visual_preview.html\")), name=\"dashboard_visual_preview\"),\n"
    if marker not in text:
        fail("urlpatterns marker missing")
    text = text.replace(marker, marker + route, 1)
    p.write_text(text, encoding="utf-8")
    print("PHASE66_8_URL_PATCHED")


def patch_manifest(root: Path, backup: Path) -> None:
    rel = "smoke_tests/manifest.json"
    p = root / rel
    if not p.exists():
        print("PHASE66_8_MANIFEST_SKIPPED_MISSING")
        return
    backup_file(root, backup, rel)
    data = json.loads(p.read_text(encoding="utf-8"))
    current = data.setdefault("current", [])
    if SMOKE_REL not in current:
        current.append(SMOKE_REL)
    data["phase66_8"] = [SMOKE_REL]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PHASE66_8_MANIFEST_PATCHED")


def main() -> int:
    if len(sys.argv) != 4:
        fail("bad args")
    root = Path(sys.argv[1])
    src = Path(sys.argv[2])
    backup = Path(sys.argv[3])
    backup.mkdir(parents=True, exist_ok=True)
    copy_files(root, src, backup)
    patch_urls(root, backup)
    patch_manifest(root, backup)
    print("PHASE66_8_COPY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
