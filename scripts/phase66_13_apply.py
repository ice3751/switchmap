import shutil
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(r'C:\SwitchMap')
PYTHON = ROOT / 'venv' / 'Scripts' / 'python.exe'
PATCH = ROOT / 'patches' / 'phase66_13_stable_dashboard_isolated'
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP = ROOT / 'backups' / f'phase66_13_{STAMP}'
FILES = [
    Path('inventory/templates/inventory/base.html'),
    Path('inventory/templates/inventory/switch_list.html'),
    Path('inventory/static/inventory/css/switchmap-dashboard-stable-main.css'),
    Path('smoke_tests/switchmap_66_13_stable_dashboard_isolated_smoke_test.py'),
    Path('docs/PHASE66_13_STABLE_DASHBOARD_ISOLATED.md'),
]

def run(cmd, label):
    print(f'PHASE66_13_RUN={label}', flush=True)
    result = subprocess.run(cmd, cwd=str(ROOT), shell=False)
    if result.returncode != 0:
        print(f'PHASE66_13_FAIL={label}', flush=True)
        print(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{ROOT}\\"', flush=True)
        sys.exit(result.returncode)

def copy_file(rel):
    src = PATCH / rel
    dst = ROOT / rel
    if not src.exists():
        raise SystemExit(f'PHASE66_13_FAIL missing patch file: {src}')
    if dst.exists():
        backup_dst = BACKUP / rel
        backup_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup_dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f'PHASE66_13_COPIED={rel}', flush=True)


def patch_manifest():
    manifest = ROOT / 'smoke_tests' / 'manifest.json'
    rel = 'smoke_tests/switchmap_66_13_stable_dashboard_isolated_smoke_test.py'
    if not manifest.exists():
        return
    backup_dst = BACKUP / 'smoke_tests' / 'manifest.json'
    backup_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, backup_dst)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    current = data.setdefault('current', [])
    if rel not in current:
        current.append(rel)
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print('PHASE66_13_MANIFEST_PATCHED', flush=True)
    else:
        print('PHASE66_13_MANIFEST_ALREADY_OK', flush=True)

def main():
    print(f'PHASE66_13_BACKUP_PATH={BACKUP}', flush=True)
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        copy_file(rel)
    patch_manifest()
    print('PHASE66_13_COPY_OK', flush=True)
    run([str(PYTHON), 'smoke_tests\\switchmap_66_13_stable_dashboard_isolated_smoke_test.py'], 'phase66.13 smoke')
    run([str(PYTHON), 'manage.py', 'check'], 'manage.py check')
    run([str(PYTHON), 'manage.py', 'collectstatic', '--noinput'], 'collectstatic')
    run([str(PYTHON), 'smoke_tests\\run_smoke.py', 'current'], 'run_smoke current')
    restart = ROOT / 'scripts' / '12_vm_restart_waitress_task.cmd'
    if restart.exists():
        run([str(restart)], 'restart Waitress')
    print('PHASE66_13_APPLY_OK', flush=True)

if __name__ == '__main__':
    main()
