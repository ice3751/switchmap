from pathlib import Path
from datetime import datetime
import hashlib
import os
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent
PHASE = "phase68_ui_static_resync"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PATCH_ROOT = PROJECT / "patches" / PHASE
TARGETS = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
]
STATIC_TARGETS = [
    Path("staticfiles/inventory/switchmap.js"),
    Path("staticfiles/inventory/css/switchmap-dashboard-stable-main.css"),
]

def log(msg):
    print(msg, flush=True)

def pyexe():
    if os.name == "nt":
        candidates = [PROJECT / "venv" / "Scripts" / "python.exe"]
    else:
        candidates = [PROJECT / "venv" / "bin" / "python"]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable

def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def copy_backup(rel: Path):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def copy_patch(rel: Path):
    src = PATCH_ROOT / rel
    dst = PROJECT / rel
    if not src.exists():
        raise SystemExit(f"RECOVERY_FAIL missing patch file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    log(f"RECOVERY_RESTORED={rel}")

def run(label, args):
    log(f"RECOVERY_RUN={label}")
    env = os.environ.copy()
    site = PROJECT / "venv" / "Lib" / "site-packages"
    if site.exists():
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(site) + (os.pathsep + old if old else "")
    result = subprocess.run(args, cwd=str(PROJECT), shell=False, env=env, capture_output=True, text=True, errors="replace")
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if result.returncode != 0:
        log(f"RECOVERY_FAIL={label}")
        if output:
            log(output[-4000:])
        log(f"ROLLBACK=xcopy /E /Y \"{BACKUP}\\*\" \"{PROJECT}\\\"")
        raise SystemExit(result.returncode)
    if label == "manage.py check" and output:
        for line in output.splitlines():
            if "System check" in line:
                log(line)
    if label == "collectstatic clear" and output:
        for line in output.splitlines()[::-1]:
            if "static file" in line or "static files" in line:
                log(line)
                break

def main():
    if not PATCH_ROOT.exists():
        raise SystemExit(f"RECOVERY_FAIL missing patch root: {PATCH_ROOT}")
    log(f"RECOVERY_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)

    for rel in TARGETS:
        copy_backup(rel)
    for rel in STATIC_TARGETS:
        copy_backup(rel)
        copy_backup(Path(str(rel) + ".gz"))
        copy_backup(Path(str(rel) + ".br"))

    for rel in TARGETS:
        copy_patch(rel)

    # Remove stale compressed/current static files so WhiteNoise cannot serve Phase 69 leftovers.
    for rel in STATIC_TARGETS:
        for candidate in [PROJECT / rel, PROJECT / Path(str(rel) + ".gz"), PROJECT / Path(str(rel) + ".br")]:
            if candidate.exists():
                candidate.unlink()
                log(f"RECOVERY_REMOVED_STALE={candidate.relative_to(PROJECT)}")

    python = pyexe()
    run("manage.py check", [python, "manage.py", "check"])
    run("collectstatic clear", [python, "manage.py", "collectstatic", "--clear", "--noinput"])

    for rel in [Path("inventory/static/inventory/switchmap.js"), Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")]:
        static_rel = Path("staticfiles") / Path(*rel.parts[2:])
        app = PROJECT / rel
        st = PROJECT / static_rel
        if not st.exists():
            raise SystemExit(f"RECOVERY_FAIL missing static output: {static_rel}")
        if md5(app) != md5(st):
            raise SystemExit(f"RECOVERY_FAIL static mismatch: {static_rel}")
        log(f"RECOVERY_STATIC_OK={static_rel}")

    restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
    if restart.exists() and os.name == "nt":
        run("restart Waitress", [str(restart)])
    else:
        log("RECOVERY_RESTART_SKIPPED=restart script not available or not Windows")

    log("RECOVERY_OK phase68_ui_static_resync")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
