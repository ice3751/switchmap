from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
os.chdir(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def fail(message: str) -> None:
    print(f"PHASE38_FAIL {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"PHASE38_OK {message}")


def check_socket(host: str = "127.0.0.1", port: int = 8000) -> None:
    try:
        with socket.create_connection((host, port), timeout=3):
            ok(f"port {host}:{port} is listening")
    except OSError as exc:
        fail(f"port {host}:{port} is not listening: {exc}")


def check_windows_task(task_name: str) -> None:
    if os.name != "nt":
        ok(f"skip Windows task check for {task_name}")
        return
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    )
    if result.returncode != 0:
        fail(f"scheduled task missing: {task_name}")
    ok(f"scheduled task exists: {task_name}")


def main() -> None:
    import django
    from django.conf import settings
    from django.test import Client

    django.setup()

    if settings.DEBUG:
        fail("DEBUG must be False on VM production")
    ok("DEBUG=False")

    allowed_hosts = set(getattr(settings, "ALLOWED_HOSTS", []))
    required_any = {"localhost", "127.0.0.1"}
    if not allowed_hosts.intersection(required_any):
        fail("ALLOWED_HOSTS must include localhost or 127.0.0.1")
    ok("ALLOWED_HOSTS basic local host is present")

    static_root = Path(settings.STATIC_ROOT)
    if not static_root.exists():
        fail(f"STATIC_ROOT missing: {static_root}")
    if not any(static_root.rglob("*")):
        fail(f"STATIC_ROOT is empty: {static_root}")
    ok(f"STATIC_ROOT exists and is not empty: {static_root}")

    db_name = settings.DATABASES["default"].get("NAME")
    db_path = Path(db_name)
    if not db_path.exists():
        fail(f"SQLite database missing: {db_path}")
    with sqlite3.connect(db_path) as conn:
        quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
    if quick_check != "ok":
        fail(f"SQLite quick_check failed: {quick_check}")
    ok("SQLite quick_check=ok")

    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    test_log = logs_dir / "phase38-write-test.tmp"
    test_log.write_text("ok", encoding="utf-8")
    test_log.unlink(missing_ok=True)
    ok("logs directory is writable")

    backup_dir = BASE_DIR / "backups" / "sqlite"
    if not backup_dir.exists():
        fail(f"backup dir missing: {backup_dir}")
    ok(f"backup dir exists: {backup_dir}")

    client = Client(HTTP_HOST="localhost")
    paths = [
        "/",
        "/sfp-live/",
        "/alarms/",
        "/backup/",
        "/topology/",
    ]
    allowed_status = {200, 301, 302, 403}
    for path in paths:
        response = client.get(path)
        if response.status_code not in allowed_status:
            fail(f"unexpected status {response.status_code} for {path}")
        ok(f"url {path} status={response.status_code}")

    check_windows_task("SwitchMap Waitress")
    check_windows_task("SwitchMap SQLite Backup")
    check_socket()

    print("PHASE38_VM_PRODUCTION_OK")


if __name__ == "__main__":
    main()
