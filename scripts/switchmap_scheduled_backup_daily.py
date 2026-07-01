import subprocess
import datetime
import getpass
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
LOG = ROOT / "logs" / "scheduled_backup_daily.log"
PY = ROOT / "venv" / "Scripts" / "python.exe"

COMMANDS = [
    ("DYNAMIC_SCHEDULED_BACKUP", [str(PY), "manage.py", "scheduled_backup_dynamic"]),
]

def write(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def append_output(text: str) -> None:
    if not text:
        return
    with LOG.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")

def run_step(name: str, cmd: list[str]) -> int:
    write(f"----- {name} START -----")
    try:
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4500,
        )
        append_output(p.stdout)
        write(f"{name}_EXIT={p.returncode}")
        write(f"----- {name} END -----")
        return p.returncode
    except Exception as exc:
        write(f"{name}_EXCEPTION={type(exc).__name__}: {exc}")
        write(f"{name}_EXIT=999")
        write(f"----- {name} END -----")
        return 999

def main() -> int:
    write("===== SwitchMap Scheduled Backup START =====")
    write("PHASE=89 dynamic auto-include backup schedule")
    write("DATE_TIME=" + datetime.datetime.now().isoformat(sep=" ", timespec="seconds"))
    write("WINDOWS_USER=" + getpass.getuser())

    final_code = 0
    for name, cmd in COMMANDS:
        code = run_step(name, cmd)
        if code != 0:
            final_code = code

    write("FINAL_EXIT=" + str(final_code))
    write("===== SwitchMap Scheduled Backup END =====")
    return final_code

if __name__ == "__main__":
    raise SystemExit(main())
