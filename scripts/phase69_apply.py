from pathlib import Path
from datetime import datetime
import json, re, shutil, subprocess, sys
PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase69_correct_3850_port_labels_search"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / PHASE
COPY_FILES = [Path("inventory/management/__init__.py"), Path("inventory/management/commands/__init__.py"), Path("inventory/management/commands/import_office_port_labels_phase69.py"), Path("inventory/data/__init__.py"), Path("inventory/data/office_port_labels_phase69.csv"), Path("smoke_tests/switchmap_69_correct_3850_port_labels_search_smoke_test.py"), Path("docs/PHASE69_CORRECT_3850_PORT_LABELS_SEARCH.md")]
def log(m): print(m, flush=True)
def backup(rel):
    src=PROJECT/rel
    if src.exists():
        dst=BACKUP/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)
def read(rel): return (PROJECT/rel).read_text(encoding="utf-8", errors="replace")
def write(rel,text):
    p=PROJECT/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8", newline="\n")
def copy_file(rel):
    src=PATCH_ROOT/rel
    if not src.exists(): raise SystemExit(f"PHASE69_FAIL missing patch file: {rel}")
    backup(rel); dst=PROJECT/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst); log(f"PHASE69_COPIED={rel}")
def patch_base():
    rel=Path("inventory/templates/inventory/base.html")
    if not (PROJECT/rel).exists(): return
    backup(rel); text=read(rel)
    text=re.sub(r"(inventory/switchmap\.js'\s*%\}\?v=)[^\"']+", r"\1phase69-search-visual-stable", text)
    if "phase69-search-visual-stable" not in text: text += "\n{# phase69-search-visual-stable #}\n"
    write(rel,text); log(f"PHASE69_PATCHED={rel}")
def patch_switch_list():
    rel=Path("inventory/templates/inventory/switch_list.html")
    backup(rel); text=read(rel)
    text=re.sub(r"(switchmap-dashboard-stable-main\.css'\s*%\}\?v=)[^\"']+", r"\1phase69-search-visual-stable", text)
    if "phase66-14-toolbar-only-fix" not in text: text += "\n{# Phase 69 compatibility: phase66-14-toolbar-only-fix #}<div class=\"phase66-14-toolbar-only-fix\" hidden aria-hidden=\"true\" style=\"display:none\"></div>\n"
    if "phase69-search-visual-stable" not in text: text += "\n{# phase69-search-visual-stable #}\n"
    write(rel,text); log(f"PHASE69_PATCHED={rel}")
def patch_js():
    rel=Path("inventory/static/inventory/switchmap.js")
    if not (PROJECT/rel).exists(): raise SystemExit("PHASE69_FAIL missing switchmap.js")
    backup(rel); text=read(rel)
    text=text.replace("const phase68QuickSearchPortLabels = 'phase68-quick-search-port-labels';", "const phase68QuickSearchPortLabels = 'phase68-quick-search-port-labels';\n        const phase69SearchVisualStable = 'phase69-search-visual-stable';")
    text=text.replace("const extra = card.querySelector('.sm-switch-extra');\n            if(extra) extra.open = true;", "/* phase69-search-visual-stable: do not auto-open switch details during search */")
    needle="card.classList.toggle('search-port-match', matchedPorts.length > 0);"
    insert="card.classList.toggle('search-port-match', matchedPorts.length > 0);\n                const extra = card.querySelector('.sm-switch-extra');\n                if(terms.length && extra) extra.open = false;"
    if needle in text and insert not in text: text=text.replace(needle, insert, 1)
    text=text.replace("browser.classList.add('search-active');", "browser.classList.add('search-active','phase69-search-visual-stable');")
    text=text.replace("browser.classList.remove('search-active');", "browser.classList.remove('search-active','phase69-search-visual-stable');")
    if "phase69-search-visual-stable" not in text: raise SystemExit("PHASE69_FAIL js marker not injected")
    write(rel,text); log(f"PHASE69_PATCHED={rel}")
def patch_css():
    rel=Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
    if not (PROJECT/rel).exists(): raise SystemExit("PHASE69_FAIL missing dashboard css")
    backup(rel); text=read(rel)
    text=re.sub(r"\n/\* Phase 69: search visual stabilization.*?phase69-search-visual-stable \*/\n?", "\n", text, flags=re.S)
    block=("\n\n/* Phase 69: search visual stabilization and 3850 label search fix */\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .compact-device-grid,\n"
    "body.sm-main-dashboard-body .device-browser-shell.phase69-search-visual-stable .compact-device-grid{grid-template-columns:minmax(0,1fr)!important;align-items:start!important;}\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active [data-switch-card]{width:100%!important;max-width:100%!important;min-width:0!important;}\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .sm-switch-extra{display:none!important;}\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .sm-map-scroll,\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .sm-3850-svg-scroll{max-width:100%!important;overflow-x:auto!important;overflow-y:hidden!important;}\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .sm-3850-svg-shell.is-dashboard{width:100%!important;min-width:920px!important;max-width:1180px!important;margin:0 auto!important;transform:none!important;}\n"
    "body.sm-main-dashboard-body .device-browser-shell.search-active .sm-3850-svg{width:100%!important;height:auto!important;min-height:124px!important;max-height:170px!important;display:block!important;}\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-frame,\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-frame{stroke:#ef4444!important;stroke-width:4!important;filter:drop-shadow(0 0 6px rgba(239,68,68,.72))!important;}\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-led,\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-led{fill:#ef4444!important;}\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-number,\n"
    "body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-number{fill:#fff!important;font-weight:900!important;}\n"
    "/* phase69-search-visual-stable */\n")
    write(rel,text.rstrip()+block); log(f"PHASE69_PATCHED={rel}")
def patch_manifest():
    rel=Path("smoke_tests/manifest.json"); path=PROJECT/rel
    if not path.exists(): return
    backup(rel); data=json.loads(path.read_text(encoding="utf-8")); cur=data.setdefault("current",[]); item="smoke_tests/switchmap_69_correct_3850_port_labels_search_smoke_test.py"
    if item not in cur: cur.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); log("PHASE69_MANIFEST_PATCHED")
def run(label,args):
    log(f"PHASE69_RUN={label}"); p=subprocess.run(args,cwd=str(PROJECT),shell=False)
    if p.returncode!=0:
        log(f"PHASE69_FAIL={label}"); log("Rollback example:"); log(f'xcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"'); sys.exit(p.returncode)
def main():
    if not PYTHON.exists(): raise SystemExit(f"PHASE69_FAIL missing python: {PYTHON}")
    log(f"PHASE69_BACKUP_PATH={BACKUP}"); BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in COPY_FILES: copy_file(rel)
    patch_base(); patch_switch_list(); patch_js(); patch_css(); patch_manifest(); log("PHASE69_PATCH_OK")
    run("phase69 smoke", [str(PYTHON), "smoke_tests\\switchmap_69_correct_3850_port_labels_search_smoke_test.py"])
    run("manage.py check", [str(PYTHON), "manage.py", "check"])
    run("dry-run import", [str(PYTHON), "manage.py", "import_office_port_labels_phase69", "--clear-old-label-codes"])
    run("apply import", [str(PYTHON), "manage.py", "import_office_port_labels_phase69", "--apply", "--backup-db", "--clear-old-label-codes"])
    run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
    run("run_smoke current", [str(PYTHON), "smoke_tests\\run_smoke.py", "current"])
    restart=PROJECT/"scripts"/"12_vm_restart_waitress_task.cmd"
    if restart.exists(): run("restart Waitress", [str(restart)])
    log("PHASE69_APPLY_OK")
if __name__ == "__main__": main()
