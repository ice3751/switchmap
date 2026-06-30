from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = ROOT / "backups" / f"phase78_alarm_cleanup_{STAMP}"

URLS = ROOT / "inventory" / "urls.py"
BASE = ROOT / "inventory" / "templates" / "inventory" / "base.html"


def backup_file(path):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def patch_urls():
    text = URLS.read_text(encoding="utf-8")
    original = text
    if "phase78_views" not in text:
        text = text.replace("    phase77_views,\n", "    phase77_views,\n    phase78_views,\n")
    phase78_block = '''    path("alarms/cleanup/", view_required(phase78_views.phase78_alarm_cleanup_view), name="phase78_alarm_cleanup"),
    path("alarms/cleanup/recheck/", operator_or_admin_required(phase78_views.phase78_alarm_recheck_view), name="phase78_alarm_recheck"),
    path("alarms/cleanup/resolve-stale/", operator_or_admin_required(phase78_views.phase78_alarm_resolve_stale_view), name="phase78_alarm_resolve_stale"),
    path("phase78/alarm-cleanup/status.json", view_required(phase78_views.phase78_alarm_cleanup_status_json), name="phase78_alarm_cleanup_status_json"),
'''
    if "phase78_alarm_cleanup" not in text:
        marker = '    path("alarms/", view_required(alarm_views.alarm_center_view), name="alarm_center"),\n'
        if marker not in text:
            raise RuntimeError("Cannot patch urls.py: alarm_center marker not found")
        text = text.replace(marker, marker + phase78_block)
    if text != original:
        backup_file(URLS)
        URLS.write_text(text, encoding="utf-8")


def patch_base():
    text = BASE.read_text(encoding="utf-8")
    original = text
    css_line = "    <link rel=\"stylesheet\" href=\"{% static 'inventory/css/switchmap-phase78.css' %}?v=phase78-alarm-cleanup\">\n"
    if "switchmap-phase78.css" not in text:
        marker = "    <link rel=\"stylesheet\" href=\"{% static 'inventory/css/switchmap-phase77.css' %}?v=phase77-seven-step\">\n"
        if marker not in text:
            raise RuntimeError("Cannot patch base.html: phase77 css marker not found")
        text = text.replace(marker, marker + css_line)

    text = text.replace(
        "current == 'phase77_noc_dashboard' or current == 'alarm_center' or current == 'sfp_monitor'",
        "current == 'phase77_noc_dashboard' or current == 'alarm_center' or current == 'phase78_alarm_cleanup' or current == 'sfp_monitor'",
    )

    alarm_item = """                        <a class=\"command-dropdown-item {% if current == 'alarm_center' %}active{% endif %}\" href=\"{% url 'inventory:alarm_center' %}\">آلارم‌ها{% if swmap_alarm_active_count %}<b class=\"topbar-badge {% if swmap_alarm_critical_count %}is-critical{% endif %}\">{{ swmap_alarm_active_count }}</b>{% endif %}</a>\n"""
    cleanup_item = """                        <a class=\"command-dropdown-item {% if current == 'phase78_alarm_cleanup' %}active{% endif %}\" href=\"{% url 'inventory:phase78_alarm_cleanup' %}\">Alarm Cleanup</a>\n"""
    if "phase78_alarm_cleanup" not in text:
        if alarm_item not in text:
            raise RuntimeError("Cannot patch base.html: alarm menu marker not found")
        text = text.replace(alarm_item, alarm_item + cleanup_item)
    elif cleanup_item not in text:
        # If phase78 appears only in the active-state expression, still add menu item.
        if alarm_item in text:
            text = text.replace(alarm_item, alarm_item + cleanup_item)

    if text != original:
        backup_file(BASE)
        BASE.write_text(text, encoding="utf-8")


def main():
    for path in (URLS, BASE):
        if not path.exists():
            raise RuntimeError(f"Missing required file: {path}")
    patch_urls()
    patch_base()
    print(f"PHASE78_PATCH_OK backup_dir={BACKUP_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PHASE78_PATCH_FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
