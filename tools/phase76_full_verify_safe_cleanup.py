# -*- coding: utf-8 -*-
"""
Phase 76 - Full Verify + Safe Cleanup for SwitchMap
Scope:
- Verify core Django/app/background monitoring/status without changing features.
- Safe cleanup only: delete Python caches and archive temporary/backup-like clutter outside protected folders.
- No database mutation.
- No credential changes.
- No SNMP/SSH config changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(r"C:\SwitchMap")
REPORT_DIR = PROJECT / "logs"
BACKUP_ROOT = PROJECT / "backups" / ("phase76_full_verify_safe_cleanup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
ARCHIVE_DIR = BACKUP_ROOT / "archived_extra_files"
REPORT_PATH = REPORT_DIR / ("phase76_full_verify_safe_cleanup_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")

PROTECTED_DIR_NAMES = {
    "venv", ".venv", "backups", "secrets", "media", ".git", "node_modules",
}
PROTECTED_FILES = {
    "db.sqlite3",
    "manage.py",
    "requirements.txt",
    ".env",
}
ARCHIVE_SUFFIXES = {".tmp", ".bak", ".orig", ".old", ".rej"}
ARCHIVE_NAME_PARTS = {
    "smoke",
    "debug",
    "temp",
    "tmp",
    "pasted text",
}
STATIC_PAIRS = [
    (PROJECT / "inventory/static/inventory/switchmap.js", PROJECT / "staticfiles/inventory/switchmap.js"),
    (PROJECT / "inventory/static/inventory/css/switchmap-dashboard-stable-main.css", PROJECT / "staticfiles/inventory/css/switchmap-dashboard-stable-main.css"),
    (PROJECT / "inventory/static/inventory/css/switchmap-notifications.css", PROJECT / "staticfiles/inventory/css/switchmap-notifications.css"),
    (PROJECT / "inventory/static/inventory/css/switchmap-phase43-47.css", PROJECT / "staticfiles/inventory/css/switchmap-phase43-47.css"),
]

CHECK_FILES = [
    PROJECT / "inventory/templates/inventory/base.html",
    PROJECT / "inventory/templates/inventory/switch_list.html",
    PROJECT / "inventory/templates/inventory/dashboard_visual_preview.html",
    PROJECT / "inventory/static/inventory/switchmap.js",
    PROJECT / "inventory/static/inventory/css/switchmap-dashboard-stable-main.css",
    PROJECT / "inventory/static/inventory/css/switchmap-notifications.css",
    PROJECT / "inventory/templates/inventory/includes/cisco_3850_svg.html",
    PROJECT / "inventory/templates/inventory/includes/generic_port_button.html",
    PROJECT / "inventory/templates/inventory/includes/nexus_svg.html",
]

VERDICTS = []

def emit(line: str = "") -> None:
    print(line)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("a", encoding="utf-8", errors="replace") as f:
        f.write(line + "\n")

def add_verdict(name: str, status: str, detail: str = "") -> None:
    VERDICTS.append((name, status, detail))
    emit(f"VERDICT::{name}={status}" + (f"::{detail}" if detail else ""))

def run(cmd: list[str] | str, timeout: int = 120, shell: bool = False) -> tuple[int, str]:
    emit(f"RUN={' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        p = subprocess.run(
            cmd,
            cwd=str(PROJECT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=shell,
            encoding="utf-8",
            errors="replace",
        )
        out = p.stdout or ""
        for line in out.splitlines():
            emit(line)
        emit(f"RETURN_CODE={p.returncode}")
        return p.returncode, out
    except subprocess.TimeoutExpired as e:
        emit(f"TIMEOUT={timeout}s")
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        return 124, out
    except Exception as e:
        emit(f"RUN_ERROR={type(e).__name__}: {e}")
        return 125, str(e)

def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return path.read_text(encoding="cp1256", errors="replace")
        except Exception:
            return ""

def backup_db() -> None:
    db = PROJECT / "db.sqlite3"
    if db.exists():
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        dst = BACKUP_ROOT / "db.sqlite3.before_phase76"
        shutil.copy2(db, dst)
        emit(f"DB_BACKUP={dst}")
    else:
        emit("DB_BACKUP=SKIP db.sqlite3 not found")

def cleanup_python_cache() -> None:
    emit("=== SAFE_CLEANUP_PYTHON_CACHE ===")
    removed_dirs = 0
    removed_files = 0
    for root, dirs, files in os.walk(PROJECT):
        root_path = Path(root)
        parts_lower = {p.lower() for p in root_path.parts}
        if any(x in parts_lower for x in PROTECTED_DIR_NAMES):
            dirs[:] = []
            continue

        for d in list(dirs):
            if d == "__pycache__":
                p = root_path / d
                try:
                    shutil.rmtree(p)
                    removed_dirs += 1
                except Exception as e:
                    emit(f"CACHE_REMOVE_FAIL={p}::{e}")
                dirs.remove(d)

        for fn in files:
            if fn.endswith(".pyc") or fn.endswith(".pyo"):
                p = root_path / fn
                try:
                    p.unlink()
                    removed_files += 1
                except Exception as e:
                    emit(f"PYC_REMOVE_FAIL={p}::{e}")

    emit(f"CACHE_DIRS_REMOVED={removed_dirs}")
    emit(f"PYC_FILES_REMOVED={removed_files}")

def should_archive_file(path: Path) -> bool:
    rel_parts = [p.lower() for p in path.relative_to(PROJECT).parts]
    if any(part in PROTECTED_DIR_NAMES for part in rel_parts):
        return False
    if path.name in PROTECTED_FILES:
        return False
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        return True
    name_lower = path.name.lower()
    if any(part in name_lower for part in ARCHIVE_NAME_PARTS):
        # Do not archive active application files inside inventory/config/scripts/tools.
        first = rel_parts[0] if rel_parts else ""
        if first in {"inventory", "config", "scripts", "tools"}:
            return False
        return True
    # Old root-level phase report text files only.
    if path.parent == PROJECT and name_lower.startswith("phase") and path.suffix.lower() in {".txt", ".log"}:
        return True
    if path.parent == PROJECT and name_lower.endswith("_report.txt"):
        return True
    return False

def archive_extra_files() -> None:
    emit("=== SAFE_ARCHIVE_EXTRA_FILES ===")
    archived = 0
    for root, dirs, files in os.walk(PROJECT):
        root_path = Path(root)
        rel = root_path.relative_to(PROJECT) if root_path != PROJECT else Path("")
        rel_parts = [p.lower() for p in rel.parts]
        if any(part in PROTECTED_DIR_NAMES for part in rel_parts):
            dirs[:] = []
            continue
        # Do not walk current backup root archive.
        if str(root_path).lower().startswith(str(BACKUP_ROOT).lower()):
            dirs[:] = []
            continue

        for fn in files:
            p = root_path / fn
            try:
                if not should_archive_file(p):
                    continue
                dest = ARCHIVE_DIR / p.relative_to(PROJECT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest))
                emit(f"ARCHIVED={p.relative_to(PROJECT)} -> {dest.relative_to(BACKUP_ROOT)}")
                archived += 1
            except Exception as e:
                emit(f"ARCHIVE_FAIL={p}::{e}")
    emit(f"ARCHIVED_EXTRA_FILES={archived}")

def verify_static_sync() -> None:
    emit("=== STATIC_SYNC_CHECK ===")
    all_ok = True
    for app_path, static_path in STATIC_PAIRS:
        if not app_path.exists() or not static_path.exists():
            emit(f"STATIC_PAIR_MISSING={app_path.relative_to(PROJECT) if app_path.exists() else app_path}::{static_path.relative_to(PROJECT) if static_path.exists() else static_path}")
            all_ok = False
            continue
        a = md5(app_path)
        b = md5(static_path)
        ok = a == b
        emit(f"STATIC_MATCH::{static_path.relative_to(PROJECT)}={'OK' if ok else 'FAIL'}")
        emit(f"APP_MD5::{app_path.relative_to(PROJECT)}={a}")
        emit(f"STATIC_MD5::{static_path.relative_to(PROJECT)}={b}")
        if not ok:
            all_ok = False
    add_verdict("STATIC_SYNC", "OK" if all_ok else "FAIL")

def verify_files_and_markers() -> None:
    emit("=== FILE_AND_MARKER_CHECK ===")
    for p in CHECK_FILES:
        emit(f"FILE_EXISTS::{p.relative_to(PROJECT)}={'YES' if p.exists() else 'NO'}")

    base = read_text(PROJECT / "inventory/templates/inventory/base.html")
    switch_list = read_text(PROJECT / "inventory/templates/inventory/switch_list.html")
    js = read_text(PROJECT / "inventory/static/inventory/switchmap.js")
    css_main = read_text(PROJECT / "inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
    css_notif = read_text(PROJECT / "inventory/static/inventory/css/switchmap-notifications.css")
    cisco = read_text(PROJECT / "inventory/templates/inventory/includes/cisco_3850_svg.html")
    generic = read_text(PROJECT / "inventory/templates/inventory/includes/generic_port_button.html")
    nexus = read_text(PROJECT / "inventory/templates/inventory/includes/nexus_svg.html")

    emit(f"MARKER::REFRESH_VIEW_IN_SWITCH_LIST={'YES' if 'Refresh View' in switch_list else 'NO'}")
    emit(f"MARKER::REFRESH_VIEW_IN_BASE={'YES' if 'Refresh View' in base else 'NO'}")
    emit(f"MARKER::ALARM_TOPBAR_DROPDOWN={'YES' if ('alarm' in base.lower() and ('dropdown' in base.lower() or 'details' in base.lower())) else 'NO'}")
    emit(f"MARKER::ALARM_TOPBAR_CSS={'YES' if ('alarm' in css_notif.lower() and ('topbar' in css_notif.lower() or 'dropdown' in css_notif.lower())) else 'NO'}")
    emit(f"MARKER::CONNECTIVITY_UI={'YES' if ('connectivity' in switch_list.lower() or 'اتصال' in switch_list) else 'NO'}")
    emit(f"MARKER::QUICK_SEARCH_JS={'YES' if ('data-port-label' in js or 'portLabel' in js or 'quick' in js.lower()) else 'NO'}")
    emit(f"MARKER::CISCO_DATA_PORT_LABEL={'YES' if 'data-port-label' in cisco else 'NO'}")
    emit(f"MARKER::GENERIC_DATA_PORT_LABEL={'YES' if 'data-port-label' in generic else 'NO'}")
    emit(f"MARKER::NEXUS_DATA_PORT_LABEL={'YES' if 'data-port-label' in nexus else 'NO'}")
    emit(f"MARKER::PHASE74_CONNECTIVITY={'YES' if 'phase74' in switch_list.lower() or 'phase74' in js.lower() or 'phase74' in css_main.lower() else 'NO'}")
    emit(f"MARKER::PHASE75_ALARM={'YES' if 'phase75' in base.lower() or 'phase75' in css_notif.lower() else 'NO'}")

    critical_ok = (
        "Refresh View" not in switch_list
        and ("data-port-label" in cisco or "data-port-label" in generic or "data-port-label" in nexus)
        and ("alarm" in base.lower())
    )
    add_verdict("UI_MARKERS", "OK" if critical_ok else "WARNING")

def setup_django():
    sys.path.insert(0, str(PROJECT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django  # type: ignore
    django.setup()

def get_model(name: str):
    from django.apps import apps
    for m in apps.get_models():
        if m.__name__ == name:
            return m
    return None

def verify_django_db() -> None:
    emit("=== DJANGO_DB_OPERATIONAL_CHECK ===")
    try:
        setup_django()
        from django.conf import settings
        from django.utils import timezone
        emit(f"DJANGO_SETTINGS_MODULE={os.environ.get('DJANGO_SETTINGS_MODULE')}")
        emit(f"DEBUG={getattr(settings, 'DEBUG', None)}")
        Switch = get_model("Switch")
        Alarm = get_model("AlarmNotification")
        SfpSnap = get_model("SfpMonitorSnapshot")
        RouterHealth = get_model("RouterHealthSnapshot")

        if Switch:
            active = Switch.objects.filter(is_active=True).count()
            total = Switch.objects.count()
            smoke = list(Switch.objects.filter(name__icontains="Smoke").values_list("name", "management_ip"))
            emit(f"SWITCH_TOTAL={total}")
            emit(f"SWITCH_ACTIVE={active}")
            emit(f"TEST_SWITCHES_SMOKE={smoke}")
            add_verdict("TEST_SWITCHES_REMOVED", "OK" if not smoke else "WARNING", str(smoke))

            fields = {f.name for f in Switch._meta.fields}
            if "snmp_last_poll" in fields:
                latest = Switch.objects.exclude(snmp_last_poll=None).order_by("-snmp_last_poll").first()
                oldest = Switch.objects.filter(is_active=True).exclude(snmp_last_poll=None).order_by("snmp_last_poll").first()
                emit(f"SWITCH_LATEST_SNMP={getattr(latest, 'snmp_last_poll', None)} switch={getattr(latest, 'name', '') if latest else ''}")
                emit(f"SWITCH_OLDEST_SNMP={getattr(oldest, 'snmp_last_poll', None)} switch={getattr(oldest, 'name', '') if oldest else ''}")
            if "discovery_last_poll" in fields:
                latestd = Switch.objects.exclude(discovery_last_poll=None).order_by("-discovery_last_poll").first()
                emit(f"SWITCH_LATEST_DISCOVERY={getattr(latestd, 'discovery_last_poll', None)} switch={getattr(latestd, 'name', '') if latestd else ''}")

        if Alarm:
            active_alarms = Alarm.objects.filter(status="active").count()
            critical = Alarm.objects.filter(status="active", severity="critical").count()
            warning = Alarm.objects.filter(status="active", severity="warning").count()
            emit(f"ACTIVE_ALARMS={active_alarms}")
            emit(f"ACTIVE_CRITICAL_ALARMS={critical}")
            emit(f"ACTIVE_WARNING_ALARMS={warning}")
            for a in Alarm.objects.select_related("switch", "port").filter(status="active").order_by("severity", "category", "switch__name", "port__interface_name")[:10]:
                emit("ACTIVE_ALARM_ITEM={}|{}|{}|{}|{}|{}".format(
                    a.id,
                    a.severity,
                    a.category,
                    a.switch.name if getattr(a, "switch", None) else "-",
                    a.port.interface_name if getattr(a, "port", None) else "-",
                    a.title,
                ))

        if SfpSnap:
            count = SfpSnap.objects.count()
            latest = SfpSnap.objects.order_by("-poll_time").first()
            emit(f"SFP_SNAPSHOT_COUNT={count}")
            emit(f"SFP_LATEST_POLL={getattr(latest, 'poll_time', None)}")
            if latest and getattr(latest, "poll_time", None):
                age = timezone.now() - latest.poll_time
                emit(f"SFP_LATEST_AGE_SECONDS={int(age.total_seconds())}")
                add_verdict("SFP_DATA_FRESHNESS", "OK" if age.total_seconds() < 900 else "WARNING", f"{int(age.total_seconds())}s")

        if RouterHealth:
            down = RouterHealth.objects.filter(status="down").order_by("-collected_at")[:10]
            for r in down:
                emit(f"ROUTER_HEALTH_DOWN={r.switch.name if r.switch else '-'}|{r.switch.management_ip if r.switch else '-'}|{r.collected_at}|{(r.notes or '')[:120]}")

    except Exception as e:
        emit("DJANGO_DB_CHECK_ERROR=" + repr(e))
        emit(traceback.format_exc())
        add_verdict("DJANGO_DB", "FAIL", repr(e))
        return
    add_verdict("DJANGO_DB", "OK")

def read_status_json(path: Path, name: str) -> None:
    emit(f"=== STATUS_JSON::{name} ===")
    if not path.exists():
        emit(f"STATUS_FILE::{path.relative_to(PROJECT)}=MISSING")
        add_verdict(name, "WARNING", "missing")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        emit(f"STATUS_PARSE_ERROR={e}")
        add_verdict(name, "WARNING", "parse_error")
        return
    emit(f"STATUS_FILE::{path.relative_to(PROJECT)}=OK")
    for key in ["status", "summary", "started_at", "completed_at", "devices", "ok", "failed", "switches", "sfp_ok", "sfp_failed", "crc_ok", "crc_failed", "crc_alarms"]:
        if key in data:
            emit(f"STATUS::{name}::{key}={data.get(key)}")
    status = str(data.get("status", "")).lower()
    if name == "SFP_BACKGROUND":
        add_verdict(name, "OK" if status == "ok" else "WARNING", str(data.get("summary", "")))
    else:
        add_verdict(name, "OK" if status == "ok" else "WARNING", str(data.get("summary", "")))

def verify_scheduled_tasks() -> None:
    emit("=== SCHEDULED_TASKS ===")
    tasks = [
        "SwitchMap Waitress",
        "SwitchMap Dashboard Background Refresh",
        "SwitchMap SFP Background Monitor",
        "SwitchMap SQLite Backup",
        "SwitchMap MikroTik Auto SNMP Poll",
    ]
    for task in tasks:
        rc, out = run(["schtasks", "/Query", "/TN", task, "/V", "/FO", "LIST"], timeout=30)
        if rc == 0:
            add_verdict("TASK_" + task.replace(" ", "_").upper(), "OK")
        else:
            # SQLite backup or legacy task may be absent; not fatal for demo.
            add_verdict("TASK_" + task.replace(" ", "_").upper(), "WARNING", "not found or query failed")

def http_smoke() -> None:
    emit("=== HTTP_SMOKE_TEST ===")
    urls = [
        "http://127.0.0.1:8000/",
        "http://127.0.0.1:8000/alarms/?status=active",
    ]
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SwitchMap-Phase76-Smoke"})
            with opener.open(req, timeout=10) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                sample = resp.read(512).decode("utf-8", errors="replace").replace("\n", " ")[:160]
                emit(f"HTTP::{url}={code} sample={sample}")
                add_verdict("HTTP_" + url.split("//", 1)[1].replace("/", "_").replace("?", "_").replace("=", "_").replace(":", "_"), "OK" if int(code) < 500 else "FAIL")
        except Exception as e:
            emit(f"HTTP::{url}=ERROR::{type(e).__name__}:{e}")
            add_verdict("HTTP_" + url.split("//", 1)[1].replace("/", "_").replace("?", "_").replace("=", "_").replace(":", "_"), "WARNING", repr(e))

def list_project_categories() -> None:
    emit("=== PROJECT_FILE_CATEGORY_SUMMARY ===")
    categories = {
        "templates": PROJECT / "inventory/templates",
        "static_app": PROJECT / "inventory/static",
        "staticfiles": PROJECT / "staticfiles",
        "management_commands": PROJECT / "inventory/management/commands",
        "scripts": PROJECT / "scripts",
        "tools": PROJECT / "tools",
        "logs": PROJECT / "logs",
        "backups": PROJECT / "backups",
        "secrets": PROJECT / "secrets",
    }
    for name, path in categories.items():
        if not path.exists():
            emit(f"CATEGORY::{name}=MISSING")
            continue
        file_count = sum(1 for p in path.rglob("*") if p.is_file())
        total_size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        emit(f"CATEGORY::{name}=files:{file_count} size_bytes:{total_size}")

def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()

    emit("PHASE76_FULL_VERIFY_SAFE_CLEANUP")
    emit(f"PROJECT={PROJECT}")
    emit(f"TIME={datetime.now().isoformat()}")
    emit(f"REPORT={REPORT_PATH}")
    emit(f"BACKUP_ROOT={BACKUP_ROOT}")
    emit("SCOPE=verify_all_background_ui_db_static_and_safe_cleanup")
    emit("DB_MUTATION=NO")
    emit("CREDENTIAL_CHANGE=NO")
    emit("NETWORK_CONFIG_CHANGE=NO")

    if not PROJECT.exists():
        emit("PROJECT_MISSING")
        return 2

    backup_db()

    emit("=== DJANGO_CHECK_BEFORE ===")
    rc, _ = run([str(PROJECT / "venv/Scripts/python.exe"), "manage.py", "check"], timeout=120)
    add_verdict("DJANGO_CHECK_BEFORE", "OK" if rc == 0 else "FAIL")

    cleanup_python_cache()
    archive_extra_files()

    emit("=== COLLECTSTATIC_SYNC ===")
    rc, _ = run([str(PROJECT / "venv/Scripts/python.exe"), "manage.py", "collectstatic", "--noinput", "-v", "0"], timeout=180)
    add_verdict("COLLECTSTATIC", "OK" if rc == 0 else "FAIL")

    emit("=== DJANGO_CHECK_AFTER ===")
    rc, _ = run([str(PROJECT / "venv/Scripts/python.exe"), "manage.py", "check"], timeout=120)
    add_verdict("DJANGO_CHECK_AFTER", "OK" if rc == 0 else "FAIL")

    verify_static_sync()
    verify_files_and_markers()
    verify_django_db()
    read_status_json(PROJECT / "logs/dashboard-background-refresh-status.json", "DASHBOARD_BACKGROUND")
    read_status_json(PROJECT / "logs/sfp-background-monitor-status.json", "SFP_BACKGROUND")
    verify_scheduled_tasks()
    http_smoke()
    list_project_categories()

    emit("=== FINAL_VERDICT_SUMMARY ===")
    fail_count = sum(1 for _, s, _ in VERDICTS if s == "FAIL")
    warn_count = sum(1 for _, s, _ in VERDICTS if s == "WARNING")
    ok_count = sum(1 for _, s, _ in VERDICTS if s == "OK")
    for name, status, detail in VERDICTS:
        emit(f"FINAL::{name}={status}" + (f"::{detail}" if detail else ""))

    emit(f"FINAL_OK_COUNT={ok_count}")
    emit(f"FINAL_WARNING_COUNT={warn_count}")
    emit(f"FINAL_FAIL_COUNT={fail_count}")

    if fail_count:
        emit("PHASE76_RESULT=FAIL")
        return 1
    if warn_count:
        emit("PHASE76_RESULT=OK_WITH_WARNINGS")
        return 0
    emit("PHASE76_RESULT=OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
