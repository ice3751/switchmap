from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import subprocess
import sys

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase69_1_corrected_mapping_continue"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / PHASE

COPY_FILES = [
    Path("inventory/data/office_port_labels_phase69.csv"),
    Path("inventory/management/commands/import_office_port_labels_phase69.py"),
    Path("smoke_tests/switchmap_69_correct_3850_port_labels_search_smoke_test.py"),
    Path("docs/PHASE69_1_CORRECTED_MAPPING_CONTINUE.md"),
]
TOUCH = [
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("smoke_tests/manifest.json"),
]

def log(msg):
    print(msg, flush=True)

def backup(rel: Path):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def read(rel: Path):
    return (PROJECT / rel).read_text(encoding="utf-8", errors="replace")

def write(rel: Path, text: str):
    (PROJECT / rel).write_text(text, encoding="utf-8", newline="")

def copy_files():
    for rel in COPY_FILES:
        src = PATCH_ROOT / rel
        dst = PROJECT / rel
        if not src.exists():
            raise SystemExit(f"PHASE69_1_FAIL missing patch file: {rel}")
        backup(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"PHASE69_1_COPIED={rel}")

def patch_switch_list_marker():
    rel = Path("inventory/templates/inventory/switch_list.html")
    text = read(rel)
    changed = False
    if "phase66-14-toolbar-only-fix" not in text:
        text += "\n{# phase66-14-toolbar-only-fix phase69-1-compat #}\n"
        changed = True
    if "phase69-1-corrected-mapping-continue" not in text:
        text += "\n{# phase69-1-corrected-mapping-continue #}\n"
        changed = True
    if changed:
        write(rel, text)
        log(f"PHASE69_1_PATCHED={rel}")
    else:
        log(f"PHASE69_1_ALREADY_OK={rel}")

def patch_css():
    rel = Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
    text = read(rel)
    block = r'''

/* Phase 69.1: keep switch cards visually stable while quick-search filters/highlights ports */
body.sm-main-dashboard-body .device-browser-shell.search-active .compact-device-grid{
    align-items:stretch!important;
}
body.sm-main-dashboard-body .device-browser-shell.search-active [data-switch-card]:not([hidden]){
    width:100%!important;
    max-width:100%!important;
    min-width:0!important;
}
body.sm-main-dashboard-body .device-browser-shell.search-active .sm-switch-extra[open],
body.sm-main-dashboard-body .device-browser-shell.search-active .switch-card-body,
body.sm-main-dashboard-body .device-browser-shell.search-active .switch-map-shell,
body.sm-main-dashboard-body .device-browser-shell.search-active .switch-visual-shell{
    max-width:100%!important;
    overflow-x:auto!important;
}
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight{
    transform:none!important;
    box-shadow:none!important;
}
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-frame,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-frame{
    stroke:#ef4444!important;
    stroke-width:3.2!important;
    filter:drop-shadow(0 0 5px rgba(239,68,68,.75))!important;
}
/* phase69-search-visual-stable */
/* phase69-1-corrected-mapping-continue */
'''
    text = re.sub(r"\n/\* Phase 69\.1: keep switch cards visually stable.*?phase69-1-corrected-mapping-continue \*/\n?", "", text, flags=re.S)
    if "phase69-search-visual-stable" not in text:
        # ensure old smoke marker if phase69 first script failed before marker was added
        text += "\n/* phase69-search-visual-stable */\n"
    text = text.rstrip() + block + "\n"
    write(rel, text)
    log(f"PHASE69_1_PATCHED={rel}")

def patch_js_marker():
    rel = Path("inventory/static/inventory/switchmap.js")
    text = read(rel)
    changed = False
    if "phase69-1-corrected-mapping-continue" not in text:
        text += "\n// phase69-1-corrected-mapping-continue\n"
        changed = True
    if "phase68-quick-search-port-labels" not in text:
        text += "\n// phase68-quick-search-port-labels search-port-highlight\n"
        changed = True
    if changed:
        write(rel, text)
        log(f"PHASE69_1_PATCHED={rel}")
    else:
        log(f"PHASE69_1_ALREADY_OK={rel}")

def patch_manifest():
    rel = Path("smoke_tests/manifest.json")
    p = PROJECT / rel
    if not p.exists():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    current = data.setdefault("current", [])
    smoke = "smoke_tests/switchmap_69_correct_3850_port_labels_search_smoke_test.py"
    if smoke not in current:
        current.append(smoke)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log("PHASE69_1_MANIFEST_PATCHED")
    else:
        log("PHASE69_1_MANIFEST_ALREADY_OK")

def run(label, args):
    log(f"PHASE69_1_RUN={label}")
    r = subprocess.run(args, cwd=str(PROJECT), shell=False)
    if r.returncode != 0:
        log(f"PHASE69_1_FAIL={label}")
        log(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        sys.exit(r.returncode)

def main():
    log(f"PHASE69_1_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in TOUCH:
        backup(rel)
    copy_files()
    patch_switch_list_marker()
    patch_css()
    patch_js_marker()
    patch_manifest()
    run("phase69 corrected smoke", [str(PYTHON), "smoke_tests\\switchmap_69_correct_3850_port_labels_search_smoke_test.py"])
    run("manage.py check", [str(PYTHON), "manage.py", "check"])
    run("dry-run corrected import", [str(PYTHON), "manage.py", "import_office_port_labels_phase69", "--clear-old-label-codes"])
    run("apply corrected import", [str(PYTHON), "manage.py", "import_office_port_labels_phase69", "--apply", "--backup-db", "--clear-old-label-codes"])
    run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
    run("run_smoke current", [str(PYTHON), "smoke_tests\\run_smoke.py", "current"])
    restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
    if restart.exists():
        run("restart Waitress", [str(restart)])
    log("PHASE69_1_APPLY_OK")

if __name__ == "__main__":
    main()
