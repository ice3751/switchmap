from __future__ import annotations

import ast
import json
import py_compile
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
PAYLOAD = ROOT / "scripts" / "phase90_payload"
BACKUP_DIR = ROOT / "backups" / ("phase90_4_comprehensive_safe_refine_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
REPORT_PATH = ROOT / "logs" / "phase90_4_install_review_report_latest.json"
MARK_URL = "# PHASE90_BACKUP_HEALTH_UI_URL"
MARK_MENU = "PHASE90_BACKUP_HEALTH_UI_MENU"

changed_files: list[str] = []
checks: list[str] = []


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path)


def backup_file(path: Path) -> None:
    if path.exists():
        dst = BACKUP_DIR / path.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def restore_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    for src in sorted(BACKUP_DIR.rglob("*")):
        if src.is_file():
            dst = ROOT / src.relative_to(BACKUP_DIR)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def write_report(status: str, error: str = "") -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "marker": "PHASE90_4_COMPREHENSIVE_SAFE_REFINE_INSTALL",
        "status": status,
        "error": error,
        "backup_dir": str(BACKUP_DIR),
        "changed_files": changed_files,
        "checks": checks,
        "safety": {
            "restore_real_enabled": False,
            "direct_delete_enabled": False,
            "cleanup_mode": "quarantine only via management command",
            "protected_paths": ["venv", ".git", "node_modules", "backups", "logs", "secrets"],
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_payload(rel: str) -> None:
    src = PAYLOAD / rel
    dst = ROOT / rel
    if not src.exists():
        raise RuntimeError(f"payload file missing: {src}")
    backup_file(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    changed_files.append(rel)


def _compile(path: Path) -> None:
    py_compile.compile(str(path), doraise=True)


def _remove_backup_health_noise(text: str) -> str:
    # Remove every previous Phase90 backup-health insertion, including malformed attempts.
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if "backup-health/" in line or MARK_URL in line:
            continue
        if "backup_health_views.backup_health_dashboard" in line:
            continue
        if stripped == "from . import backup_health_views":
            continue
        if stripped in {"backup_health_views", "backup_health_views,"}:
            continue
        if "from . import" in line and "backup_health_views" in line:
            # Preserve normal import lines if possible; remove only backup_health_views token.
            line = re.sub(r"\bbackup_health_views\b\s*,?", "", line)
            line = re.sub(r",\s*,", ",", line)
            line = re.sub(r"\(\s*,", "(", line)
            line = re.sub(r",\s*\)", ")", line)
            line = line.rstrip()
            # Known malformed leftovers must be dropped.
            if stripped.startswith("from . import (") and not line.strip().endswith(")"):
                # A multiline import opener should remain as `from . import (` only.
                line = "from . import ("
            if line.strip() in {"from . import", "from . import (", "from . import ()"}:
                # Keep a clean multiline opener only if the original line was exactly an opener.
                if stripped.startswith("from . import ("):
                    out.append("from . import (")
                continue
        out.append(line.rstrip())
    cleaned = "\n".join(out).rstrip() + "\n"
    cleaned = cleaned.replace("from . import (,", "from . import (")
    cleaned = cleaned.replace("from . import ( ,", "from . import (")
    cleaned = cleaned.replace("from . import ()", "")
    return cleaned


def _ensure_import(text: str) -> str:
    if re.search(r"^\s*from\s+\.\s+import\s+backup_health_views\s*$", text, flags=re.M):
        return text
    lines = text.splitlines()
    insert_at = None
    # Insert after the last import block before urlpatterns, not inside urlpatterns.
    urlpatterns_at = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*urlpatterns\s*=", line):
            urlpatterns_at = i
            break
    if urlpatterns_at is None:
        raise RuntimeError("urlpatterns assignment not found in inventory/urls.py")
    insert_at = urlpatterns_at
    lines.insert(insert_at, "from . import backup_health_views")
    return "\n".join(lines).rstrip() + "\n"


def _ensure_route(text: str) -> str:
    if "backup-health/" in text:
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*urlpatterns\s*=\s*\[", line):
            route = "    path('backup-health/', backup_health_views.backup_health_dashboard, name='backup_health_dashboard'),  " + MARK_URL
            lines.insert(i + 1, route)
            return "\n".join(lines).rstrip() + "\n"
    raise RuntimeError("urlpatterns list opener not found in inventory/urls.py")


def _validate_urls(path: Path) -> None:
    _compile(path)
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    route_found = "backup-health/" in path.read_text(encoding="utf-8", errors="replace")
    import_found = "backup_health_views" in path.read_text(encoding="utf-8", errors="replace")
    if not route_found or not import_found:
        raise RuntimeError("backup-health route/import not present after patch")
    checks.append("inventory/urls.py py_compile+ast OK")


def patch_urls() -> None:
    path = ROOT / "inventory" / "urls.py"
    if not path.exists():
        raise RuntimeError("inventory/urls.py not found")
    backup_file(path)
    original = path.read_text(encoding="utf-8", errors="replace")
    cleaned = _remove_backup_health_noise(original)
    # Check cleaned file first; if current damage is unrelated, stop and restore instead of guessing.
    tmp_clean = BACKUP_DIR / "inventory" / "urls.cleaned.preview.py"
    tmp_clean.parent.mkdir(parents=True, exist_ok=True)
    tmp_clean.write_text(cleaned, encoding="utf-8")
    try:
        py_compile.compile(str(tmp_clean), doraise=True)
    except Exception:
        # If cleaned preview still fails, restore current backup and fail clearly.
        raise RuntimeError("inventory/urls.py still invalid after removing Phase90 fragments; no unsafe rewrite applied")
    patched = _ensure_import(cleaned)
    patched = _ensure_route(patched)
    path.write_text(patched, encoding="utf-8")
    _validate_urls(path)
    changed_files.append("inventory/urls.py")
    print("URLS_PATCH=ok")


def patch_base_menu() -> None:
    # Non-critical. Add link only when a safe backup anchor exists. Otherwise leave menus untouched.
    path = ROOT / "inventory" / "templates" / "inventory" / "base.html"
    if not path.exists():
        print("BASE_MENU_PATCH=skipped missing base.html")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if MARK_MENU in text or "/backup-health/" in text:
        print("BASE_MENU_PATCH=already-present")
        return
    anchors = ["/backup-storage/", "/backup-credentials/", "/mikrotik-backups/", "/cisco-backups/", "backup-storage", "backup-credentials", "mikrotik-backups", "cisco-backups"]
    lines = text.splitlines()
    target = None
    for i, line in enumerate(lines):
        low = line.lower()
        if any(a in low for a in anchors):
            target = i
    if target is None:
        print("BASE_MENU_PATCH=skipped no safe backup anchor")
        return
    backup_file(path)
    indent = lines[target][: len(lines[target]) - len(lines[target].lstrip())]
    lines.insert(target + 1, indent + '<a class="dropdown-item phase90-backup-health-link" href="/backup-health/">Backup Health</a> <!-- ' + MARK_MENU + ' -->')
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    changed_files.append("inventory/templates/inventory/base.html")
    print("BASE_MENU_PATCH=patched")


def main() -> int:
    print("PHASE90_4_INSTALL_COMPREHENSIVE_SAFE_REVIEW_START")
    print(f"BACKUP_DIR={BACKUP_DIR}")
    if not PAYLOAD.exists():
        print(f"FAIL missing payload: {PAYLOAD}")
        return 1
    try:
        for rel in [
            "inventory/backup_health_views.py",
            "inventory/templates/inventory/backup_health_dashboard.html",
            "inventory/management/commands/project_refine_audit.py",
        ]:
            copy_payload(rel)
            print(f"COPIED={rel}")
        patch_urls()
        patch_base_menu()
        for rel in [
            "inventory/backup_health_views.py",
            "inventory/management/commands/project_refine_audit.py",
        ]:
            _compile(ROOT / rel)
            checks.append(f"py_compile OK {rel}")
            print(f"PY_COMPILE_OK={rel}")
        write_report("ok")
        print(f"INSTALL_REPORT={REPORT_PATH}")
        print("PHASE90_4_INSTALL_COMPREHENSIVE_SAFE_REVIEW_OK")
        return 0
    except Exception as exc:
        print(f"PHASE90_4_INSTALL_ERROR={type(exc).__name__}: {exc}")
        restore_backups()
        write_report("failed_restored", str(exc))
        print("ROLLBACK=restored files from backup dir")
        print(f"INSTALL_REPORT={REPORT_PATH}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
