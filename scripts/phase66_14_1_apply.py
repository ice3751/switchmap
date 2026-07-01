from pathlib import Path
from datetime import datetime
import shutil, subprocess, json

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase66_14_1"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
SRC_ROOT = Path(__file__).resolve().parents[1] / "patches" / "phase66_14_1_toolbar_smoke_continue"

def log(msg):
    print(msg, flush=True)

def backup_file(rel):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def copy_file(rel):
    src = SRC_ROOT / rel
    dst = PROJECT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_file(rel)
    shutil.copy2(src, dst)
    log(f"PHASE66_14_1_COPIED={rel}")

def patch_manifest():
    rel = Path('smoke_tests/manifest.json')
    path = PROJECT / rel
    if not path.exists():
        log('PHASE66_14_1_WARN missing manifest')
        return
    backup_file(rel)
    text = path.read_text(encoding='utf-8', errors='replace')
    try:
        data = json.loads(text)
        item = 'smoke_tests/switchmap_66_14_1_toolbar_smoke_continue_test.py'
        if isinstance(data, list) and item not in data:
            data.append(item)
            path.write_text(json.dumps(data, indent=2), encoding='utf-8', newline='')
            log('PHASE66_14_1_MANIFEST_PATCHED')
        elif isinstance(data, dict):
            cur = data.get('current')
            if isinstance(cur, list) and item not in cur:
                cur.append(item)
                path.write_text(json.dumps(data, indent=2), encoding='utf-8', newline='')
                log('PHASE66_14_1_MANIFEST_PATCHED')
    except Exception:
        if 'switchmap_66_14_1_toolbar_smoke_continue_test.py' not in text:
            text = text.rstrip() + '\n# smoke_tests/switchmap_66_14_1_toolbar_smoke_continue_test.py\n'
            path.write_text(text, encoding='utf-8', newline='')
            log('PHASE66_14_1_MANIFEST_COMMENT_PATCHED')

def run(label, args):
    log(f"PHASE66_14_1_RUN={label}")
    p = subprocess.run(args, cwd=str(PROJECT), text=True)
    if p.returncode != 0:
        log(f"PHASE66_14_1_FAIL={label}")
        log('Rollback example:')
        log(f'xcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        raise SystemExit(p.returncode)

log(f"PHASE66_14_1_BACKUP_PATH={BACKUP}")
BACKUP.mkdir(parents=True, exist_ok=True)
for rel in [
    Path('smoke_tests/switchmap_66_14_toolbar_only_smoke_test.py'),
    Path('smoke_tests/switchmap_66_14_1_toolbar_smoke_continue_test.py'),
    Path('docs/PHASE66_14_1_TOOLBAR_SMOKE_CONTINUE.md'),
]:
    copy_file(rel)
patch_manifest()
run('phase66.14 smoke', [str(PYTHON), 'smoke_tests\\switchmap_66_14_toolbar_only_smoke_test.py'])
run('phase66.14.1 smoke', [str(PYTHON), 'smoke_tests\\switchmap_66_14_1_toolbar_smoke_continue_test.py'])
run('manage.py check', [str(PYTHON), 'manage.py', 'check'])
run('collectstatic', [str(PYTHON), 'manage.py', 'collectstatic', '--noinput'])
run('run_smoke current', [str(PYTHON), 'smoke_tests\\run_smoke.py', 'current'])
restart = PROJECT / 'scripts' / '12_vm_restart_waitress_task.cmd'
if restart.exists():
    run('restart waitress', [str(restart)])
else:
    log('PHASE66_14_1_WARN missing waitress restart script')
log('PHASE66_14_1_APPLY_OK')
