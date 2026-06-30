from pathlib import Path
import shutil, sys, datetime, subprocess, json
ROOT = Path(r'C:\SwitchMap')
PHASE = 'phase66_11_1_main_visual_repair'
SRC = ROOT / 'patches' / PHASE
FILES = [
    'inventory/templates/inventory/switch_list.html',
    'inventory/static/inventory/css/switchmap-dashboard-command-final.css',
    'smoke_tests/switchmap_66_11_1_main_visual_repair_smoke_test.py',
    'docs/PHASE66_11_1_MAIN_VISUAL_REPAIR.md',
]
now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = ROOT / 'backups' / ('phase66_11_1_' + now)
print('PHASE66_11_1_BACKUP_PATH=' + str(backup))
backup.mkdir(parents=True, exist_ok=True)
for rel in FILES:
    dst = ROOT / rel
    src = SRC / rel
    if not src.exists():
        print('PHASE66_11_1_MISSING_SRC=' + rel)
        sys.exit(1)
    if dst.exists():
        b = backup / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, b)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print('PHASE66_11_1_COPIED=' + rel)
# patch manifest
mf = ROOT / 'smoke_tests' / 'manifest.json'
if mf.exists():
    data = json.loads(mf.read_text(encoding='utf-8'))
    test = 'smoke_tests/switchmap_66_11_1_main_visual_repair_smoke_test.py'
    cur = data.setdefault('current', [])
    if test not in cur:
        cur.append(test)
    data['phase66_11_1'] = [test]
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PHASE66_11_1_MANIFEST_PATCHED')
print('PHASE66_11_1_COPY_OK')
PY = ROOT / 'venv' / 'Scripts' / 'python.exe'
def run(args, label):
    p = subprocess.run([str(PY)] + args, cwd=str(ROOT), text=True)
    if p.returncode != 0:
        print('PHASE66_11_1_FAILED_AT=' + label)
        sys.exit(p.returncode)
run(['smoke_tests/switchmap_66_11_1_main_visual_repair_smoke_test.py'], 'phase66_11_1_smoke')
run(['smoke_tests/run_smoke.py', 'current'], 'run_smoke_current')
run(['manage.py', 'check'], 'manage_check')
run(['manage.py', 'collectstatic', '--noinput'], 'collectstatic')
restart = ROOT / 'scripts' / '12_vm_restart_waitress_task.cmd'
if restart.exists():
    p = subprocess.run([str(restart)], cwd=str(ROOT), shell=True, text=True)
    if p.returncode != 0:
        print('PHASE66_11_1_WAITRESS_RESTART_WARN')
print('PHASE66_11_1_APPLY_OK')
