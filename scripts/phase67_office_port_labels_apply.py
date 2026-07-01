from pathlib import Path
from datetime import datetime
import shutil
import subprocess
import sys

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase67_office_port_labels"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / "phase67_office_port_labels"

FILES = [
    Path("inventory/management/__init__.py"),
    Path("inventory/management/commands/__init__.py"),
    Path("inventory/management/commands/import_office_port_labels.py"),
    Path("inventory/data/__init__.py"),
    Path("inventory/data/office_port_labels_phase67.csv"),
    Path("smoke_tests/switchmap_67_office_port_labels_smoke_test.py"),
    Path("docs/PHASE67_OFFICE_PORT_LABELS.md"),
]


def log(msg):
    print(msg, flush=True)


def backup_file(rel: Path):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_file(rel: Path):
    src = PATCH_ROOT / rel
    if not src.exists():
        raise SystemExit(f"PHASE67_FAIL missing patch file: {rel}")
    dst = PROJECT / rel
    backup_file(rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    log(f"PHASE67_COPIED={rel}")


def run(label, args):
    log(f"PHASE67_RUN={label}")
    p = subprocess.run(args, cwd=str(PROJECT), text=True)
    if p.returncode != 0:
        raise SystemExit(f"PHASE67_FAIL={label}")


def main():
    if not PYTHON.exists():
        raise SystemExit(f"PHASE67_FAIL missing python: {PYTHON}")
    log(f"PHASE67_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        copy_file(rel)
    log("PHASE67_COPY_OK")

    run("phase67 smoke", [str(PYTHON), "smoke_tests\\switchmap_67_office_port_labels_smoke_test.py"])
    run("manage.py check", [str(PYTHON), "manage.py", "check"])
    run("dry-run import", [str(PYTHON), "manage.py", "import_office_port_labels"])
    run("apply import", [str(PYTHON), "manage.py", "import_office_port_labels", "--apply", "--backup-db"])
    log("PHASE67_APPLY_OK")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if not isinstance(exc.code, int) and exc.code:
            log(str(exc.code))
        log("Rollback example:")
        log(f'xcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        sys.exit(code)
