from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.dont_write_bytecode = True

PHASE = "PHASE103"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase103_dashboard_cards_refine"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase103_dashboard_cards_refine_apply_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase103_dashboard_cards_refine_apply_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase103_dashboard_cards_refine_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css"),
    Path("inventory/management/commands/phase103_dashboard_cards_ui_check.py"),
    Path("inventory/static/inventory/brand/phase103/phase103-dashboard-cards-preview.png"),
    Path("inventory/static/inventory/brand/phase103/icons/card-connectivity.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-urgent.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-alarms.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-topology.svg"),
]
PAYLOAD_COPY_FILES = [
    Path("inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css"),
    Path("inventory/management/commands/phase103_dashboard_cards_ui_check.py"),
    Path("inventory/static/inventory/brand/phase103/phase103-dashboard-cards-preview.png"),
    Path("inventory/static/inventory/brand/phase103/icons/card-connectivity.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-urgent.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-alarms.svg"),
    Path("inventory/static/inventory/brand/phase103/icons/card-topology.svg"),
]

report: Dict[str, object] = {
    "phase": PHASE,
    "root": str(ROOT),
    "stamp": STAMP,
    "changed_files": [str(p).replace("\\", "/") for p in CHANGED_FILES],
    "steps": [],
    "rollback_performed": False,
    "service_restart": "YES_AFTER_VERIFY",
    "db_mutation": "NO",
    "migration_write": "NO",
    "restore_enable_change": "NO",
    "ssh_execution": "NO",
    "backup_write": "NO",
    "visible_test_data_created": "NO",
}

NEW_CARDS_SECTION = r'''    <section class="sm-main-grid phase103-dashboard-grid" aria-label="Dashboard command center cards" data-phase103-dashboard-cards-grid>
        <!-- Phase103 Dashboard Cards Visual Refine: focused four-card visual layer, no data/model change -->
        <article class="sm-main-card phase103-card phase103-card-connectivity is-blue phase74-connectivity-click-card" role="button" tabindex="0" data-dashboard-connectivity-card data-phase74-marker="phase74-connectivity-click-card">
            <span class="phase103-visual connectivity" aria-hidden="true"></span>
            <header class="phase103-card-top">
                <span class="phase103-detail-link" aria-label="جزئیات اتصال تجهیزات">جزئیات</span>
                <div class="phase103-card-titlebox">
                    <div>
                        <h2>اتصال تجهیزات</h2>
                        <p>وضعیت اتصال شبکه: <span class="phase103-status-dot"></span> سالم</p>
                    </div>
                    <span class="phase103-card-icon phase103-icon-connectivity" aria-hidden="true"></span>
                </div>
            </header>
            <div class="phase103-primary phase103-connectivity-primary">
                <div class="phase103-metric-stack">
                    <div>
                        <strong class="phase103-big-number"><span data-field="healthy">{{ dashboard_insight.counters.healthy }}</span>/<span data-field="total_devices">{{ dashboard_insight.counters.total_devices }}</span></strong>
                        <span class="phase103-metric-label">دستگاه متصل</span>
                    </div>
                    <div class="phase103-ring" style="--phase103-ring: {{ dashboard_insight.counters.coverage_percent|default:0 }}%">
                        <div class="phase103-ring-inner"><strong>{{ dashboard_insight.counters.coverage_percent|default:0 }}%</strong><span>نرخ اتصال</span></div>
                    </div>
                </div>
                <div class="phase103-connectivity-details">
                    <div class="phase103-meter"><span data-field-style="coverage_percent" style="width: {{ dashboard_insight.counters.coverage_percent|default:0 }}%"></span></div>
                    <div class="phase103-chips">
                        <span class="phase103-chip ok"><b data-field="healthy_inline">{{ dashboard_insight.counters.healthy }}</b> سالم <i class="dot"></i></span>
                        <span class="phase103-chip danger"><b data-field="snmp_failed">{{ dashboard_insight.counters.snmp_failed }}</b> ناموفق <i class="dot"></i></span>
                        <span class="phase103-chip muted"><b data-field="not_monitored_inline">{{ dashboard_insight.counters.not_monitored }}</b> خارج از پایش <i class="dot"></i></span>
                    </div>
                </div>
            </div>
            <p class="phase103-note sm-main-note" data-dashboard-connectivity-note>برای مشاهده وضعیت تک‌تک دستگاه‌ها کلیک کن.</p>
        </article>

        {% with first_action=dashboard_insight.actions.0 %}
            <article class="sm-main-card phase103-card phase103-card-critical is-critical severity-{% if first_action %}{{ first_action.severity }}{% else %}ok{% endif %}" role="button" tabindex="0" data-dashboard-detail data-dashboard-primary-action {% if first_action %}data-issue-id="{{ first_action.issue_id }}" data-detail-url="{{ first_action.detail_url }}" data-object-name="{{ first_action.object_name }}" data-object-type="{{ first_action.object_type }}" data-severity="{{ first_action.severity }}" data-last-check="{{ first_action.last_check_time }}" data-reason="{{ first_action.short_reason }}" data-action="{{ first_action.recommended_action }}"{% endif %}>
                <span class="phase103-visual radar" aria-hidden="true"></span>
                <header class="phase103-card-top">
                    <span class="phase103-detail-link" aria-label="جزئیات اقدام فوری">جزئیات</span>
                    <div class="phase103-card-titlebox">
                        <div>
                            <h2>اقدام فوری</h2>
                            <p><span class="phase103-status-dot"></span> نیازمند بررسی فوری</p>
                        </div>
                        <span class="phase103-card-icon phase103-icon-urgent" aria-hidden="true"></span>
                    </div>
                </header>
                <div class="phase103-primary">
                    <div>
                        <strong class="phase103-big-number is-red" data-field="attention">{{ dashboard_insight.counters.attention|default:0 }}</strong>
                        <span class="phase103-metric-label">مورد نیاز به اقدام</span>
                    </div>
                    <div class="phase103-chips">
                        <span class="phase103-chip danger"><b data-field="snmp_failed">{{ dashboard_insight.counters.snmp_failed|default:0 }}</b> ناموفق <i class="dot"></i></span>
                        <span class="phase103-chip muted"><b data-field="stale">{{ dashboard_insight.counters.stale|default:0 }}</b> قدیمی <i class="dot"></i></span>
                    </div>
                </div>
                <div class="phase103-list" data-dashboard-actions>
                    {% for item in dashboard_insight.actions|slice:":2" %}
                        <span class="sm-main-list-item phase66-list-item severity-{{ item.severity }}" data-dashboard-detail data-issue-id="{{ item.issue_id }}" data-detail-url="{{ item.detail_url }}" data-object-name="{{ item.object_name }}" data-object-type="{{ item.object_type }}" data-severity="{{ item.severity }}" data-last-check="{{ item.last_check_time }}" data-reason="{{ item.short_reason }}" data-action="{{ item.recommended_action }}">
                            <small>{{ item.compact_reason|default:item.short_reason }}</small>
                            <strong>{{ item.title }}</strong>
                        </span>
                    {% empty %}
                        <span class="phase103-empty phase66-empty">اقدام فوری لازم نیست.</span>
                    {% endfor %}
                </div>
                <p class="phase103-note">این موارد ممکن است بر پایداری شبکه تأثیر بگذارند.</p>
            </article>
        {% endwith %}

        <article class="sm-main-card phase103-card phase103-card-alarms is-neutral">
            <span class="phase103-visual bars" aria-hidden="true"></span>
            <header class="phase103-card-top">
                <a class="phase103-detail-link" href="{% url 'inventory:alarm_center' %}" aria-label="جزئیات آلارم‌ها">جزئیات</a>
                <div class="phase103-card-titlebox">
                    <div>
                        <h2>آلارم‌ها</h2>
                        <p><span class="phase103-status-dot"></span> مجموع هشدارهای فعال</p>
                    </div>
                    <span class="phase103-card-icon phase103-icon-alarms" aria-hidden="true"></span>
                </div>
            </header>
            <div class="phase103-primary">
                <div>
                    <strong class="phase103-big-number" data-field="active_alarms">{{ dashboard_insight.counters.active_alarms|default:0 }}</strong>
                    <span class="phase103-metric-label">آلارم فعال</span>
                </div>
                <div class="phase103-chips">
                    <span class="phase103-chip muted"><b data-field="warning_alarms">{{ dashboard_insight.counters.warning_alarms }}</b> هشدار <i class="dot"></i></span>
                    <span class="phase103-chip danger"><b data-field="critical_alarms">{{ dashboard_insight.counters.critical_alarms }}</b> بحرانی <i class="dot"></i></span>
                </div>
            </div>
            <div class="phase103-list" data-dashboard-alarms>
                {% for alarm in dashboard_insight.alarms|slice:":2" %}
                    <a class="sm-main-list-item phase66-list-item severity-{{ alarm.severity }}" href="{{ alarm.detail_url }}" data-dashboard-detail data-issue-id="{{ alarm.issue_id }}" data-detail-url="{{ alarm.detail_url }}" data-object-name="{{ alarm.object_name }}" data-object-type="{{ alarm.object_type }}" data-severity="{{ alarm.severity }}" data-last-check="{{ alarm.last_check_time }}" data-reason="{{ alarm.short_reason }}" data-action="{{ alarm.recommended_action }}">
                        <small>{{ alarm.compact_reason|default:"Alarm Active" }}</small>
                        <strong>{{ alarm.title }}</strong>
                    </a>
                {% empty %}
                    <span class="phase103-empty phase66-empty">آلارم فعالی ثبت نشده است.</span>
                {% endfor %}
            </div>
            <p class="phase103-note">لیست کامل آلارم‌ها را مشاهده کنید.</p>
        </article>

        <article class="sm-main-card phase103-card phase103-card-topology is-amber">
            <span class="phase103-topology-visual" aria-hidden="true"></span>
            <header class="phase103-card-top">
                <a class="phase103-detail-link" href="{% url 'inventory:topology' %}" aria-label="جزئیات توپولوژی">جزئیات</a>
                <div class="phase103-card-titlebox">
                    <div>
                        <h2>توپولوژی</h2>
                        <p><span class="phase103-status-dot"></span> وضعیت کشف و ارتباطات</p>
                    </div>
                    <span class="phase103-card-icon phase103-icon-topology" aria-hidden="true"></span>
                </div>
            </header>
            <div class="phase103-primary">
                <div>
                    <strong class="phase103-big-number" data-field="topology_issues">{{ dashboard_insight.counters.topology_issues }}</strong>
                    <span class="phase103-metric-label">مورد نیاز به بررسی</span>
                </div>
                <div class="phase103-topology-breakdown">
                    <span class="phase103-topology-pill">Discovery<small>بررسی</small></span>
                    <span class="phase103-topology-pill">SFP<small>ماژول</small></span>
                    <span class="phase103-topology-pill">Link<small>لینک</small></span>
                </div>
            </div>
            <div class="phase103-list" data-dashboard-topology-issues>
                {% for issue in dashboard_insight.topology_issues|slice:":2" %}
                    <a class="sm-main-list-item phase66-list-item severity-{{ issue.severity }}" href="{{ issue.detail_url }}" data-dashboard-detail data-issue-id="{{ issue.issue_id }}" data-detail-url="{{ issue.detail_url }}" data-object-name="{{ issue.object_name }}" data-object-type="{{ issue.object_type }}" data-severity="{{ issue.severity }}" data-last-check="{{ issue.last_check_time }}" data-reason="{{ issue.short_reason }}" data-action="{{ issue.recommended_action }}">
                        <small>{{ issue.compact_reason|default:issue.summary }}</small>
                        <strong>{{ issue.title }}</strong>
                    </a>
                {% empty %}
                    <span class="phase103-empty phase66-empty">Issue توپولوژی فعال نیست.</span>
                {% endfor %}
            </div>
            <p class="phase103-note">برای مشاهده توپولوژی کامل کلیک کنید.</p>
        </article>
    </section>'''


def log(line: str) -> None:
    print(line, flush=True)
    with REPORT_TXT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def record_step(name: str, rc: int, extra: Dict[str, object] | None = None) -> None:
    item = {"name": name, "rc": rc}
    if extra:
        item.update(extra)
    report["steps"].append(item)


def run_cmd(name: str, cmd: List[str], check: bool = True) -> int:
    log(f"STEP_START={name}")
    log("CMD=" + " ".join(cmd))
    cp = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if cp.stdout:
        for line in cp.stdout.splitlines():
            log(line)
    log(f"STEP_EXIT={name}:{cp.returncode}")
    record_step(name, cp.returncode)
    if check and cp.returncode != 0:
        raise RuntimeError(f"{name} failed rc={cp.returncode}")
    return cp.returncode


def backup_current_files() -> None:
    log("STEP_START=backup_current_files")
    BACKUP_FILES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for rel in CHANGED_FILES + [Path("staticfiles/inventory/css/switchmap-phase103-dashboard-cards.css"), Path("staticfiles/inventory/brand/phase103/phase103-dashboard-cards-preview.png"), Path("staticfiles/inventory/brand/phase103/icons/card-connectivity.svg"), Path("staticfiles/inventory/brand/phase103/icons/card-urgent.svg"), Path("staticfiles/inventory/brand/phase103/icons/card-alarms.svg"), Path("staticfiles/inventory/brand/phase103/icons/card-topology.svg")]:
        src = ROOT / rel
        dst = BACKUP_FILES / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
            manifest.append({"path": str(rel), "existed": True})
            log(f"BACKUP_FILE={rel}")
        else:
            manifest.append({"path": str(rel), "existed": False})
            log(f"BACKUP_NEW_FILE_MARKER={rel}")
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"BACKUP_MANIFEST={MANIFEST_JSON}")
    log("STEP_EXIT=backup_current_files:0")
    record_step("backup_current_files", 0)


def copy_payload_files() -> None:
    for rel in PAYLOAD_COPY_FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        if not src.exists():
            raise RuntimeError(f"missing payload file: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"APPLIED_FILE={rel}")


def patch_switch_list() -> None:
    rel = Path("inventory/templates/inventory/switch_list.html")
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    original = text

    css_line = "<link rel=\"stylesheet\" href=\"{% static 'inventory/css/switchmap-phase103-dashboard-cards.css' %}?v=phase103-dashboard-cards\">\n"
    if "switchmap-phase103-dashboard-cards.css" not in text:
        anchor = "<link rel=\"stylesheet\" href=\"{% static 'inventory/css/switchmap-dashboard-stable-main.css' %}?v=phase66-14-toolbar-only-fix\">\n"
        if anchor in text:
            text = text.replace(anchor, anchor + css_line, 1)
        else:
            text = text.replace("{% block extra_head %}\n{{ block.super }}\n", "{% block extra_head %}\n{{ block.super }}\n" + css_line, 1)

    if "data-phase103-dashboard-cards" not in text:
        text = text.replace('<section id="sm-main-dashboard" class="sm-main-dashboard" data-dashboard-live', '<section id="sm-main-dashboard" class="sm-main-dashboard" data-phase103-dashboard-cards data-dashboard-live', 1)

    # Remove an existing Phase103 card block or replace the current dashboard card section.
    pattern = re.compile(r'    <section class="sm-main-grid[^\n]*aria-label="Dashboard command center cards"[^>]*>.*?    </section>\s*\n\s*<aside class="phase66-detail-drawer', re.S)
    replacement = NEW_CARDS_SECTION + "\n\n    <aside class=\"phase66-detail-drawer"
    text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError("sm-main-grid dashboard cards section not found or ambiguous")

    if "Phase103 Dashboard Cards Visual Refine" not in text:
        raise RuntimeError("Phase103 dashboard card marker missing after patch")

    if text == original:
        log("PATCHED_FILE=no_change_needed:inventory/templates/inventory/switch_list.html")
    else:
        path.write_text(text, encoding="utf-8")
        log("PATCHED_FILE=inventory/templates/inventory/switch_list.html")


def sync_staticfiles() -> None:
    staticfiles = ROOT / "staticfiles"
    if not staticfiles.exists():
        return
    items = [
        (ROOT / "inventory/static/inventory/css/switchmap-phase103-dashboard-cards.css", staticfiles / "inventory/css/switchmap-phase103-dashboard-cards.css"),
        (ROOT / "inventory/static/inventory/brand/phase103/phase103-dashboard-cards-preview.png", staticfiles / "inventory/brand/phase103/phase103-dashboard-cards-preview.png"),
        (ROOT / "inventory/static/inventory/brand/phase103/icons/card-connectivity.svg", staticfiles / "inventory/brand/phase103/icons/card-connectivity.svg"),
        (ROOT / "inventory/static/inventory/brand/phase103/icons/card-urgent.svg", staticfiles / "inventory/brand/phase103/icons/card-urgent.svg"),
        (ROOT / "inventory/static/inventory/brand/phase103/icons/card-alarms.svg", staticfiles / "inventory/brand/phase103/icons/card-alarms.svg"),
        (ROOT / "inventory/static/inventory/brand/phase103/icons/card-topology.svg", staticfiles / "inventory/brand/phase103/icons/card-topology.svg"),
    ]
    for src, dst in items:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"SYNC_STATICFILES_FILE={dst}")


def apply_payload() -> None:
    log("STEP_START=apply_payload")
    if not PAYLOAD.exists():
        raise RuntimeError(f"missing payload: {PAYLOAD}")
    copy_payload_files()
    patch_switch_list()
    sync_staticfiles()
    log("STEP_EXIT=apply_payload:0")
    record_step("apply_payload", 0)


def rollback() -> None:
    log("STEP_START=rollback")
    report["rollback_performed"] = True
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.exists() else []
    for item in manifest:
        rel = Path(item["path"])
        dst = ROOT / rel
        bak = BACKUP_FILES / rel
        try:
            if item.get("existed"):
                if bak.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bak, dst)
                    log(f"ROLLBACK_RESTORED={rel}")
            else:
                if dst.exists():
                    dst.unlink()
                    log(f"ROLLBACK_REMOVED_NEW_FILE={rel}")
        except Exception as exc:
            log(f"ROLLBACK_WARNING={rel}:{exc}")
    log("STEP_EXIT=rollback:0")
    record_step("rollback", 0)


def verify_after_apply() -> None:
    log("STEP_START=verify_after_apply")
    py = str(ROOT / "venv/Scripts/python.exe")
    run_cmd("py_compile_changed", [py, "-m", "py_compile", "inventory/management/commands/phase103_dashboard_cards_ui_check.py"])
    run_cmd("django_manage_check", [py, "manage.py", "check"])
    run_cmd("phase103_dashboard_cards_ui_check", [py, "manage.py", "phase103_dashboard_cards_ui_check", "--strict", "--output", str(LOG_DIR / f"phase103_dashboard_cards_ui_check_{STAMP}.json")])
    run_cmd("phase94_smoke_runner", [py, "smoke_tests/run_smoke.py", "--strict", "--output", str(LOG_DIR / f"phase103_phase94_smoke_runner_{STAMP}.json")])
    run_cmd("phase98_100_final_release_lock_check", [py, "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", str(LOG_DIR / f"phase103_phase98_100_final_release_lock_{STAMP}.json")])
    log("STEP_EXIT=verify_after_apply:0")
    record_step("verify_after_apply", 0)


def restart_waitress() -> None:
    log("STEP_START=restart_waitress")
    run_cmd("waitress_task_query_before", ["schtasks", "/Query", "/TN", "SwitchMap Waitress", "/V", "/FO", "LIST"], check=False)
    run_cmd("waitress_task_end", ["schtasks", "/End", "/TN", "SwitchMap Waitress"], check=False)
    time.sleep(3)
    run_cmd("waitress_task_run", ["schtasks", "/Run", "/TN", "SwitchMap Waitress"], check=True)
    time.sleep(4)
    run_cmd("waitress_task_query_after", ["schtasks", "/Query", "/TN", "SwitchMap Waitress", "/V", "/FO", "LIST"], check=False)
    log("WAITRESS_RESTART_OK=True")
    log("STEP_EXIT=restart_waitress:0")
    record_step("restart_waitress", 0)


def save_report(final_ok: bool) -> None:
    report["final_ok"] = final_ok
    report["report_json"] = str(REPORT_JSON)
    report["report_txt"] = str(REPORT_TXT)
    report["rollback_source"] = str(BACKUP_ROOT)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    REPORT_TXT.write_text("", encoding="utf-8")
    log("PHASE103R9_DASHBOARD_CARDS_REFINE_START")
    log("MODE=file_only_dashboard_four_cards_visual_refine_verify_restart_after_success")
    log(f"ROOT={ROOT}")
    log("EXPECTED_RESULT=dashboard_four_summary_cards_compact_preview_matched_without_data_change")
    log("RISK=template_static_file_changes_and_brief_waitress_restart_after_verify_success")
    log("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        log("STEP_START=preflight")
        if not (ROOT / "venv/Scripts/python.exe").exists():
            raise RuntimeError("missing venv/Scripts/python.exe")
        if not (ROOT / "inventory/templates/inventory/switch_list.html").exists():
            raise RuntimeError("missing switch_list.html")
        log(f"PAYLOAD={PAYLOAD}")
        log(f"BACKUP_ROOT={BACKUP_ROOT}")
        log("STEP_EXIT=preflight:0")
        record_step("preflight", 0)
        backup_current_files()
        apply_payload()
        verify_after_apply()
        restart_waitress()
        save_report(True)
        log("PHASE103_FINAL_OK=True")
        log(f"REPORT_JSON={REPORT_JSON}")
        log(f"REPORT_TXT={REPORT_TXT}")
        log(f"ROLLBACK_SOURCE={BACKUP_ROOT}")
        log("SERVICE_RESTART=YES")
        log("DB_MUTATION=NO")
        log("MIGRATION_WRITE=NO")
        log("RESTORE_ENABLE_CHANGE=NO")
        log("SSH_EXECUTION=NO")
        log("BACKUP_WRITE=NO")
        log("VISIBLE_TEST_DATA_CREATED=NO")
        log("PHASE103_DASHBOARD_CARDS_REFINE_OK")
        return 0
    except Exception as exc:
        log(f"PHASE103_ERROR={type(exc).__name__}:{exc}")
        try:
            rollback()
        finally:
            save_report(False)
        log("PHASE103_FINAL_OK=False")
        log(f"REPORT_JSON={REPORT_JSON}")
        log(f"REPORT_TXT={REPORT_TXT}")
        log("SERVICE_RESTART=NO")
        log("DB_MUTATION=NO")
        log("MIGRATION_WRITE=NO")
        log("RESTORE_ENABLE_CHANGE=NO")
        log("SSH_EXECUTION=NO")
        log("BACKUP_WRITE=NO")
        log("VISIBLE_TEST_DATA_CREATED=NO")
        log("PHASE103_DASHBOARD_CARDS_REFINE_FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
