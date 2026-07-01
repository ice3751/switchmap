from pathlib import Path
import shutil, subprocess, sys, os
from datetime import datetime

ROOT = Path(r"C:\SwitchMap")
PATCH = ROOT / "patches" / "phase66_12_stable_main_dashboard"
PY = ROOT / "venv" / "Scripts" / "python.exe"
BACKUP = ROOT / "backups" / ("phase66_12_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
FILES = [
    "inventory/templates/inventory/switch_list.html",
    "inventory/static/inventory/css/switchmap-dashboard-v12.css",
    "smoke_tests/switchmap_66_12_stable_main_dashboard_smoke_test.py",
    "docs/PHASE66_12_STABLE_MAIN_DASHBOARD.md",
]

def run(cmd, label):
    print(label)
    p = subprocess.run(cmd, cwd=str(ROOT), shell=True)
    if p.returncode != 0:
        print("PHASE66_12_APPLY_FAILED")
        print(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{ROOT}\\"')
        sys.exit(p.returncode)

def main():
    print(f"PHASE66_12_BACKUP_PATH={BACKUP}")
    for rel in FILES:
        src = PATCH / rel
        dst = ROOT / rel
        if dst.exists():
            b = BACKUP / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"PHASE66_12_COPIED={rel}")
    run(f'"{PY}" smoke_tests\\switchmap_66_12_stable_main_dashboard_smoke_test.py', "PHASE66_12_SMOKE")
    # Quick compatibility checks before full smoke run
    for test in [
        "smoke_tests\\switchmap_66_8_dashboard_visual_prototype_smoke_test.py",
        "smoke_tests\\switchmap_66_9_preview_typography_responsive_smoke_test.py",
        "smoke_tests\\switchmap_66_10_preview_font_menu_quicksearch_smoke_test.py",
        "smoke_tests\\switchmap_66_11_dashboard_final_main_smoke_test.py",
    ]:
        if (ROOT / test).exists():
            run(f'"{PY}" {test}', f"PHASE66_12_COMPAT={test}")
    run(f'"{PY}" manage.py check', "PHASE66_12_DJANGO_CHECK")
    run(f'"{PY}" manage.py collectstatic --noinput', "PHASE66_12_COLLECTSTATIC")
    if (ROOT / "smoke_tests" / "run_smoke.py").exists():
        run(f'"{PY}" smoke_tests\\run_smoke.py current', "PHASE66_12_FULL_SMOKE")
    restart = ROOT / "scripts" / "12_vm_restart_waitress_task.cmd"
    if restart.exists():
        run(f'"{restart}"', "PHASE66_12_RESTART_WAITRESS")
    print("PHASE66_12_APPLY_OK")
    print("PHASE66_12_NOTE=Open http://it-tools.winac-co.com:8000/ and press Ctrl+F5")

if __name__ == "__main__":
    main()
