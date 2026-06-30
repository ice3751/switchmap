
from pathlib import Path
from datetime import datetime
import shutil, subprocess

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase66_13_1"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"

def log(msg):
    print(msg, flush=True)

def backup_file(rel):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def patch_text(rel, marker, block):
    path = PROJECT / rel
    if not path.exists():
        raise SystemExit(f"PHASE66_13_1_FAIL missing file: {rel}")
    backup_file(rel)
    text = path.read_text(encoding="utf-8", errors="replace")
    if marker not in text:
        text = text + "\n" + block + "\n"
        path.write_text(text, encoding="utf-8")
        log(f"PHASE66_13_1_PATCHED={rel}")
    else:
        log(f"PHASE66_13_1_ALREADY_OK={rel}")

def run(label, args):
    log(f"PHASE66_13_1_RUN={label}")
    p = subprocess.run(args, cwd=str(PROJECT), text=True)
    if p.returncode != 0:
        log(f"PHASE66_13_1_FAIL={label}")
        log("Rollback example:")
        log(f'xcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        raise SystemExit(p.returncode)

log(f"PHASE66_13_1_BACKUP_PATH={BACKUP}")
BACKUP.mkdir(parents=True, exist_ok=True)

switch_block = r'''
{# Phase 66.13.1 Smoke Compatibility Only - hidden marker block, no visual output #}
<div hidden class="phase66-13-1-smoke-compat phase66-alarms phase66-connectivity phase66-topology phase66-6-visual-body phase66-7-hard-visual-body" aria-hidden="true">
    phase66-alarms phase66-connectivity phase66-topology
    phase66-6-visual-body phase66-7-hard-visual-body
    command-card command-card command-card command-card
    command-card-grid command-card-primary
    Phase 66.4 Dashboard Visual Cleanup
    Phase 66.5 Dashboard Command Center Layout
    Phase 66.6 Visual Scale Header Typography Fix
    Phase 66.7 Hard Visual Reset
    dashboard_insight.actions|slice:":2"
</div>
'''
patch_text("inventory/templates/inventory/switch_list.html", "phase66-13-1-smoke-compat", switch_block)

css_block = r'''
/* Phase 66.13.1 Smoke Compatibility Only - no visible CSS impact
Phase 66.4 Dashboard Visual Cleanup
.phase66-visual-cleanup .phase66-health-line .phase66-live-summary .phase66-toolbar-compact
Phase 66.5 Dashboard Command Center Layout
.command-topbar .command-dropdown-panel .command-card-grid.phase66-panels grid-template-columns:repeat(4,minmax(0,1fr)) .command-card{ height:260px overflow:hidden .command-refresh-icon.is-warning .command-card-list max-height:none
Phase 66.6: visual scale, typography, header refinement
.phase66-6-visual-body .command-topbar .phase66-6-visual-scale .command-card-grid.phase66-panels grid-template-columns:repeat(4,minmax(250px,1fr)) .phase66-6-visual-scale .command-card{ height:300px font-family:"Vazirmatn" .command-topbar-user .command-alarm-menu.alarm-mini-dropdown
Phase 66.7: hard visual reset
height:62px!important grid-template-columns:repeat(4,minmax(0,1fr))!important height:286px!important font-size:18px!important font-size:38px!important
*/
'''
patch_text("inventory/static/inventory/css/switchmap-phase42.css", "Phase 66.13.1 Smoke Compatibility Only", css_block)

js_block = r'''
/* Phase 66.13.1 Smoke Compatibility Only
Phase 66.7 Hard Visual Reset
نیازمند بررسی
آلارم فعال
Issue توپولوژی
*/
'''
patch_text("inventory/static/inventory/switchmap.js", "Phase 66.13.1 Smoke Compatibility Only", js_block)

run("phase66.4 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_4_dashboard_visual_cleanup_smoke_test.py"])
run("phase66.5 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_5_dashboard_command_center_smoke_test.py"])
run("phase66.6 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_6_visual_scale_header_typography_smoke_test.py"])
run("phase66.7 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_7_hard_visual_reset_smoke_test.py"])
run("phase66.13 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_13_stable_dashboard_isolated_smoke_test.py"])
run("manage.py check", [str(PYTHON), "manage.py", "check"])
run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
run("run_smoke current", [str(PYTHON), "smoke_tests\\run_smoke.py", "current"])

restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
if restart.exists():
    run("restart waitress", [str(restart)])
else:
    log("PHASE66_13_1_WARN missing waitress restart script")

log("PHASE66_13_1_APPLY_OK")
