from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.dont_write_bytecode = True

PHASE = "PHASE102"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase102_brand_icons"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase102_brand_icons_apply_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase102_brand_icons_apply_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase102_brand_icons_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/static/inventory/css/switchmap-phase102-brand-icons.css"),
    Path("inventory/management/commands/phase102_brand_icons_ui_check.py"),
]
ASSET_DIR = Path("inventory/static/inventory/brand/phase102")
PAYLOAD_COPY_FILES = [
    Path("inventory/static/inventory/css/switchmap-phase102-brand-icons.css"),
    Path("inventory/management/commands/phase102_brand_icons_ui_check.py"),
]

report: Dict[str, object] = {
    "phase": PHASE,
    "root": str(ROOT),
    "stamp": STAMP,
    "changed_files": [str(p).replace("\\", "/") for p in CHANGED_FILES] + [str(ASSET_DIR).replace("\\", "/")],
    "steps": [],
    "rollback_performed": False,
    "service_restart": "YES_AFTER_VERIFY",
    "db_mutation": "NO",
    "migration_write": "NO",
    "restore_enable_change": "NO",
    "ssh_execution": "NO",
    "backup_write": "NO",
    "visible_test_data_created": "NO",
}

def log(line: str) -> None:
    print(line, flush=True)
    with REPORT_TXT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def record_step(name: str, rc: int, extra: Dict[str, object] | None = None) -> None:
    item = {"name": name, "rc": rc}
    if extra:
        item.update(extra)
    report["steps"].append(item)

def run_cmd(name: str, cmd: List[str], check: bool = True) -> int:
    log(f"STEP_START={name}")
    log("CMD=" + " ".join(cmd))
    cp = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if cp.stdout:
        for line in cp.stdout.splitlines():
            log(line)
    log(f"STEP_EXIT={name}:{cp.returncode}")
    record_step(name, cp.returncode)
    if check and cp.returncode != 0:
        raise RuntimeError(f"{name} failed rc={cp.returncode}")
    return cp.returncode

def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(str(src))
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

def backup_current_files() -> None:
    log("STEP_START=backup_current_files")
    BACKUP_FILES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for rel in CHANGED_FILES:
        src = ROOT / rel
        dst = BACKUP_FILES / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
            manifest.append({"path": str(rel), "existed": True})
            log(f"BACKUP_FILE={rel}")
        else:
            manifest.append({"path": str(rel), "existed": False})
            log(f"BACKUP_NEW_FILE_MARKER={rel}")
    # asset dirs are new phase-owned; back up if they already exist.
    for rel in [ASSET_DIR, Path("staticfiles/inventory/brand/phase102"), Path("staticfiles/inventory/css/switchmap-phase102-brand-icons.css")]:
        src = ROOT / rel
        dst = BACKUP_FILES / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            manifest.append({"path": str(rel), "existed": True, "static_asset": True})
            log(f"BACKUP_ASSET={rel}")
        else:
            manifest.append({"path": str(rel), "existed": False, "static_asset": True})
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"BACKUP_MANIFEST={MANIFEST_JSON}")
    log("STEP_EXIT=backup_current_files:0")
    record_step("backup_current_files", 0)

def patch_base_html() -> None:
    rel = Path("inventory/templates/inventory/base.html")
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    original = text

    # Add favicon and CSS once.
    favicon_block = '''    <link rel="icon" type="image/svg+xml" href="{% static 'inventory/brand/phase102/favicon.svg' %}?v=phase102-brand-icons" data-phase102-brand-icons>\n'''
    if "data-phase102-brand-icons" not in text:
        text = text.replace("    <title>{% block title %}SwitchMap{% endblock %}</title>\n", "    <title>{% block title %}SwitchMap{% endblock %}</title>\n" + favicon_block)
    css_line = "    <link rel=\"stylesheet\" href=\"{% static 'inventory/css/switchmap-phase102-brand-icons.css' %}?v=phase102-brand-icons\">\n"
    if "switchmap-phase102-brand-icons.css" not in text:
        text = text.replace("    {% block extra_head %}{% endblock %}", css_line + "    {% block extra_head %}{% endblock %}")

    new_brand = '''                <a class="brand-link phase102-brand-link" href="{% url 'inventory:switch_list' %}" aria-label="SwitchMap Dashboard" data-phase102-brand-header>
                    <span class="brand-mark phase102-brand-mark"><img src="{% static 'inventory/brand/phase102/switchmap-app-icon.svg' %}" alt="" width="38" height="38"></span>
                    <span class="brand-copy phase102-brand-copy">
                        <strong class="phase102-brand-word"><span class="phase102-brand-switch">Switch</span><span class="phase102-brand-map">Map</span></strong>
                        <small class="phase102-brand-subtitle">Production Monitoring</small>
                    </span>
                </a>'''
    if "data-phase102-brand-header" in text:
        text = re.sub(r'<a class="brand-link phase102-brand-link".*?</a>', new_brand, text, flags=re.S)
    else:
        text, n = re.subn(r'                <a class="brand-link" href="\{% url \'inventory:switch_list\' %\}" aria-label="SwitchMap Dashboard">.*?                </a>', new_brand, text, count=1, flags=re.S)
        if n != 1:
            # More tolerant replacement for already modified brand link.
            text, n = re.subn(r'                <a class="brand-link[^\"]*" href="\{% url \'inventory:switch_list\' %\}" aria-label="SwitchMap Dashboard"[^>]*>.*?                </a>', new_brand, text, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError("brand link block not found in base.html")

    if "data-phase102-navigation-icons" not in text:
        text = text.replace('<header class="app-topbar command-topbar">', '<header class="app-topbar command-topbar" data-phase102-navigation-icons>')

    if text == original:
        log("PATCHED_FILE=no_change_needed:inventory/templates/inventory/base.html")
    else:
        path.write_text(text, encoding="utf-8")
        log("PATCHED_FILE=inventory/templates/inventory/base.html")

def apply_payload() -> None:
    log("STEP_START=apply_payload")
    if not PAYLOAD.exists():
        raise RuntimeError(f"missing payload: {PAYLOAD}")
    # assets
    copy_tree(PAYLOAD / ASSET_DIR, ROOT / ASSET_DIR)
    log(f"APPLIED_ASSET_DIR={ASSET_DIR}")
    # payload files
    for rel in PAYLOAD_COPY_FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        if not src.exists():
            raise RuntimeError(f"missing payload file: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"APPLIED_FILE={rel}")
    patch_base_html()
    # Staticfiles sync for WhiteNoise deployments without collectstatic.
    staticfiles = ROOT / "staticfiles"
    if staticfiles.exists():
        sf_asset_dir = staticfiles / "inventory/brand/phase102"
        copy_tree(ROOT / ASSET_DIR, sf_asset_dir)
        log(f"SYNC_STATICFILES_DIR={sf_asset_dir}")
        sf_css = staticfiles / "inventory/css/switchmap-phase102-brand-icons.css"
        sf_css.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "inventory/static/inventory/css/switchmap-phase102-brand-icons.css", sf_css)
        log(f"SYNC_STATICFILES_FILE={sf_css}")
    log("STEP_EXIT=apply_payload:0")
    record_step("apply_payload", 0)

def rollback() -> None:
    log("STEP_START=rollback")
    report["rollback_performed"] = True
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.exists() else []
    for item in manifest:
        rel = Path(item["path"])
        dst = ROOT / rel
        bak = BACKUP_FILES / rel
        try:
            if item.get("existed"):
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                if bak.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if bak.is_dir():
                        shutil.copytree(bak, dst)
                    else:
                        shutil.copy2(bak, dst)
                log(f"ROLLBACK_RESTORED={rel}")
            else:
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                    log(f"ROLLBACK_REMOVED_NEW={rel}")
        except Exception as exc:
            log(f"ROLLBACK_WARNING={rel}:{exc}")
    log("STEP_EXIT=rollback:0")
    record_step("rollback", 0)

def restart_waitress() -> None:
    log("STEP_START=restart_waitress")
    # Restart only after all verifications pass. This applies the template change.
    for name, cmd, check in [
        ("waitress_task_query_before", ["schtasks", "/Query", "/TN", "SwitchMap Waitress", "/V", "/FO", "LIST"], False),
        ("waitress_task_end", ["schtasks", "/End", "/TN", "SwitchMap Waitress"], False),
    ]:
        try:
            run_cmd(name, cmd, check=check)
        except Exception as exc:
            log(f"WARNING={name}:{exc}")
    time.sleep(3)
    run_cmd("waitress_task_run", ["schtasks", "/Run", "/TN", "SwitchMap Waitress"], check=True)
    time.sleep(4)
    run_cmd("waitress_task_query_after", ["schtasks", "/Query", "/TN", "SwitchMap Waitress", "/V", "/FO", "LIST"], check=False)
    log("WAITRESS_RESTART_OK=True")
    log("STEP_EXIT=restart_waitress:0")
    record_step("restart_waitress", 0)

def verify_after_apply() -> None:
    log("STEP_START=verify_after_apply")
    py = str(ROOT / "venv/Scripts/python.exe")
    run_cmd("py_compile_changed", [py, "-m", "py_compile", "inventory/management/commands/phase102_brand_icons_ui_check.py"])
    run_cmd("django_manage_check", [py, "manage.py", "check"])
    run_cmd("phase102_brand_icons_ui_check", [py, "manage.py", "phase102_brand_icons_ui_check", "--strict", "--output", str(LOG_DIR / f"phase102_brand_icons_ui_check_{STAMP}.json")])
    run_cmd("phase94_smoke_runner", [py, "smoke_tests/run_smoke.py", "--strict", "--output", str(LOG_DIR / f"phase102_phase94_smoke_runner_{STAMP}.json")])
    run_cmd("phase98_100_final_release_lock_check", [py, "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", str(LOG_DIR / f"phase102_phase98_100_final_release_lock_{STAMP}.json")])
    log("STEP_EXIT=verify_after_apply:0")
    record_step("verify_after_apply", 0)

def main() -> int:
    REPORT_TXT.write_text("", encoding="utf-8")
    log("PHASE102_BRAND_ICONS_APPLY_START")
    log("MODE=brand_assets_header_favicon_navigation_icons_verify_restart_after_success")
    log(f"ROOT={ROOT}")
    log("EXPECTED_RESULT=brand_assets_in_project_header_favicon_and_menu_icons_applied")
    log("RISK=template_static_file_changes_and_brief_waitress_restart_after_verify_success")
    log("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        log("STEP_START=preflight")
        if not (ROOT / "venv/Scripts/python.exe").exists():
            raise RuntimeError("missing venv python")
        if not PAYLOAD.exists():
            raise RuntimeError("missing payload directory")
        log(f"PAYLOAD={PAYLOAD}")
        log(f"BACKUP_ROOT={BACKUP_ROOT}")
        log("STEP_EXIT=preflight:0")
        record_step("preflight", 0)
        backup_current_files()
        apply_payload()
        verify_after_apply()
        restart_waitress()
        report["final_ok"] = True
        report["rollback_source"] = str(BACKUP_ROOT)
        log("PHASE102_FINAL_OK=True")
        log(f"REPORT_JSON={REPORT_JSON}")
        log(f"REPORT_TXT={REPORT_TXT}")
        log(f"ROLLBACK_SOURCE={BACKUP_ROOT}")
        log("SERVICE_RESTART=YES")
        log("DB_MUTATION=NO")
        log("MIGRATION_WRITE=NO")
        log("RESTORE_ENABLE_CHANGE=NO")
        log("SSH_EXECUTION=NO")
        log("BACKUP_WRITE=NO")
        log("VISIBLE_TEST_DATA_CREATED=NO")
        log("PHASE102_BRAND_ICONS_APPLY_OK")
        return 0
    except Exception as exc:
        log(f"PHASE102_ERROR={type(exc).__name__}:{exc}")
        try:
            rollback()
        except Exception as rb_exc:
            log(f"PHASE102_ROLLBACK_ERROR={type(rb_exc).__name__}:{rb_exc}")
        report["final_ok"] = False
        log("PHASE102_FINAL_OK=False")
        log(f"REPORT_JSON={REPORT_JSON}")
        log(f"REPORT_TXT={REPORT_TXT}")
        log("SERVICE_RESTART=NO")
        log("DB_MUTATION=NO")
        log("MIGRATION_WRITE=NO")
        log("RESTORE_ENABLE_CHANGE=NO")
        log("SSH_EXECUTION=NO")
        log("BACKUP_WRITE=NO")
        log("VISIBLE_TEST_DATA_CREATED=NO")
        log("PHASE102_BRAND_ICONS_APPLY_FAIL")
        return 1
    finally:
        REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    raise SystemExit(main())
