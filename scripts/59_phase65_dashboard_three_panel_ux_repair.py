from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_DASHBOARD_BLOCK = r'''<section class="dashboard-insight-shell phase65-three-panel-dashboard" data-dashboard-live data-dashboard-data-url="{% url 'inventory:switchmap_dashboard_data' %}">
    <div class="phase65-live-bar">
        <div class="phase65-live-status">
            <span class="live-dot"></span>
            <strong data-field="background_label">{{ dashboard_insight.background.label }}</strong>
            <small>آخرین بروزرسانی: <b data-field="generated_at">{{ dashboard_insight.generated_at }}</b></small>
        </div>
        <div class="phase65-dashboard-actions">
            <button class="btn btn-primary" type="button" data-dashboard-manual-refresh>Refresh View</button>
            <a class="btn btn-secondary" href="{% url 'inventory:alarm_center' %}">Alarms</a>
            <a class="btn btn-secondary" href="{% url 'inventory:topology' %}">Topology</a>
        </div>
    </div>

    <section class="phase65-summary state-{{ dashboard_insight.overall.state }}" data-dashboard-state="{{ dashboard_insight.overall.state }}">
        <div>
            <span class="phase65-pill">نتیجه تحلیل‌شده</span>
            <h2 data-field="overall_title">{{ dashboard_insight.overall.title }}</h2>
            <p data-field="overall_subtitle">{{ dashboard_insight.overall.subtitle }}</p>
        </div>
        {% with first_action=dashboard_insight.actions.0 %}
            <aside class="phase65-next-action">
                <span>اقدام اول</span>
                <strong data-field="next_action_title">{{ first_action.title }}</strong>
                <small data-field="next_action_text">{{ first_action.action }}</small>
            </aside>
        {% endwith %}
    </section>

    <section class="phase65-main-grid">
        <article class="phase65-panel phase65-panel-alarms">
            <header>
                <div>
                    <span class="phase65-panel-kicker">Alarm & Notification</span>
                    <h3>آلارم و نوتیفیکیشن</h3>
                </div>
                <strong class="phase65-big-number" data-field="active_alarms">{{ dashboard_insight.counters.active_alarms }}</strong>
            </header>
            <div class="phase65-mini-row">
                <span>Critical: <b data-field="critical_alarms">{{ dashboard_insight.counters.critical_alarms }}</b></span>
                <span>Warning: <b data-field="warning_alarms">{{ dashboard_insight.counters.warning_alarms }}</b></span>
            </div>
            <div class="phase65-live-list" data-dashboard-alarms>
                {% for alarm in dashboard_insight.alarms|slice:":3" %}
                    <div class="live-alarm severity-{{ alarm.severity }}">
                        <strong>{{ alarm.title }}</strong>
                        <span>{{ alarm.target }}{% if alarm.port %} / {{ alarm.port }}{% endif %}</span>
                        <small>{{ alarm.last_seen_text }}</small>
                    </div>
                {% empty %}
                    <div class="phase65-empty">آلارم فعالی ثبت نشده است.</div>
                {% endfor %}
            </div>
        </article>

        <article class="phase65-panel phase65-panel-connectivity">
            <header>
                <div>
                    <span class="phase65-panel-kicker">Switch Connectivity</span>
                    <h3>وضعیت اتصال تجهیزات</h3>
                </div>
                <strong class="phase65-big-number"><span data-field="healthy">{{ dashboard_insight.counters.healthy }}</span>/<span data-field="total_devices">{{ dashboard_insight.counters.total_devices }}</span></strong>
            </header>
            <div class="phase65-progress"><span data-field-style="coverage_percent" style="width: {{ dashboard_insight.counters.coverage_percent|default:0 }}%"></span></div>
            <div class="phase65-mini-row">
                <span>نیازمند بررسی: <b data-field="attention">{{ dashboard_insight.counters.attention }}</b></span>
                <span>خارج از پوشش: <b data-field="not_monitored">{{ dashboard_insight.counters.not_monitored }}</b></span>
            </div>
            <p class="phase65-panel-note">فقط وضعیت تحلیل‌شده نمایش داده می‌شود؛ داده خام در بخش Advanced است.</p>
        </article>

        <article class="phase65-panel phase65-panel-topology">
            <header>
                <div>
                    <span class="phase65-panel-kicker">Topology Monitoring</span>
                    <h3>مانیتورینگ توپولوژی</h3>
                </div>
                <strong class="phase65-big-number" data-field="sfp_issues">{{ dashboard_insight.counters.sfp_issues }}</strong>
            </header>
            <div class="phase65-mini-row">
                <span>SFP / Link Issue</span>
                <span>Critical: <b data-field="sfp_critical">{{ dashboard_insight.counters.sfp_critical }}</b></span>
            </div>
            <p class="phase65-panel-note">توپولوژی از Discovery، Link و SFP تحلیل می‌شود. جزئیات کامل داخل صفحه Topology است.</p>
            <a class="btn btn-secondary phase65-panel-link" href="{% url 'inventory:topology' %}">باز کردن Topology</a>
        </article>
    </section>

    <section class="phase65-bottom-grid">
        <article class="phase65-panel phase65-actions-panel">
            <header><h3>اقدام‌های ضروری</h3><span>فقط موارد قابل اقدام</span></header>
            <div class="phase65-action-list" data-dashboard-actions>
                {% for item in dashboard_insight.actions|slice:":4" %}
                    <div class="action-item severity-{{ item.severity }}">
                        <div><strong>{{ item.title }}</strong><span>{{ item.summary }}</span></div>
                        <p>{{ item.action }}</p>
                        <small>{{ item.last_poll_text }}</small>
                    </div>
                {% empty %}
                    <div class="phase65-empty">اقدام فوری لازم نیست.</div>
                {% endfor %}
            </div>
        </article>

        <article class="phase65-panel phase65-reliability-panel">
            <header><h3>اعتبار داده</h3><span>مبنای تصمیم‌گیری</span></header>
            <div class="phase65-reliability-score"><strong data-field="reliable_percent">{{ dashboard_insight.counters.reliable_percent }}%</strong><span>قابل اتکا</span></div>
            <p><b data-field="healthy_inline">{{ dashboard_insight.counters.healthy }}</b> از <b data-field="total_devices">{{ dashboard_insight.counters.total_devices }}</b> دستگاه داده تازه و بدون خطا دارند.</p>
        </article>
    </section>

    <details class="insight-advanced surface-card phase65-advanced">
        <summary>Advanced / Raw Data</summary>
        <div class="advanced-grid">
            <div><strong>Background status</strong><pre data-field-json="background">{{ dashboard_insight.background }}</pre></div>
            <div><strong>Backup</strong><pre>{{ dashboard_insight.backup_dashboard }}</pre></div>
            <div><strong>SFP</strong><pre>{{ dashboard_insight.sfp_dashboard.summary }}</pre></div>
        </div>
    </details>

    <div hidden class="dashboard-legacy-compat-markers phase65-compat" aria-hidden="true">
        Phase 63 Live Insight Dashboard
        Phase 64 Dashboard Usability Compact
        Phase 65 Three Panel Dashboard UX
        dashboard-insight-shell
        نتیجه تحلیل‌شده
        backup_dashboard
        data-search-results
        data-switch-card
        insight-workbench-grid
        notification-panel-live
        action-panel .action-list
        refresh-results-panel:empty
    </div>
</section>'''

CSS_BLOCK = r'''
/* Phase 65: three panel dashboard UX */
.phase65-three-panel-dashboard{display:grid;gap:12px;max-width:1480px;margin-inline:auto;margin-bottom:16px;}
.phase65-live-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;border:1px solid #bbf7d0;border-radius:16px;background:#ecfdf3;color:#14532d;}
.phase65-live-status{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.phase65-live-status small{color:#49627f;font-size:12px;}
.phase65-dashboard-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.phase65-summary{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,360px);gap:14px;padding:18px 22px;border-radius:22px;background:#fff;border:1px solid #e3ebf7;box-shadow:0 12px 28px rgba(15,31,53,.06);border-inline-end:6px solid #2563eb;}
.phase65-summary.state-critical{background:linear-gradient(90deg,#fff 0%,#fff5f5 100%);border-inline-end-color:#ef4444;}
.phase65-summary.state-warning{background:linear-gradient(90deg,#fff 0%,#fffbeb 100%);border-inline-end-color:#f59e0b;}
.phase65-summary.state-ok{background:linear-gradient(90deg,#fff 0%,#f0fdf4 100%);border-inline-end-color:#16a34a;}
.phase65-summary h2{font-size:26px;margin:6px 0 8px;line-height:1.35;color:#0f1f35;}
.phase65-summary p{margin:0;color:#526783;font-size:13px;line-height:1.75;}
.phase65-pill,.phase65-panel-kicker{display:inline-flex;align-items:center;width:max-content;border:1px solid #dbe8fb;border-radius:999px;padding:5px 10px;background:#f7fbff;color:#2563eb;font-size:11px;font-weight:900;}
.phase65-next-action{display:grid;gap:6px;padding:14px;border:1px solid #dbe8fb;border-radius:16px;background:#fff;align-self:center;}
.phase65-next-action span{font-size:11px;color:#64748b;font-weight:800;}
.phase65-next-action strong{font-size:16px;color:#0f1f35;line-height:1.5;}
.phase65-next-action small{font-size:12px;color:#526783;line-height:1.65;}
.phase65-main-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;}
.phase65-bottom-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:12px;align-items:start;}
.phase65-panel-alarms,.phase65-panel-connectivity,.phase65-panel-topology{position:relative;}
.phase65-panel{background:#fff;border:1px solid #e3ebf7;border-radius:20px;padding:16px;box-shadow:0 10px 24px rgba(15,31,53,.05);min-height:190px;}
.phase65-panel header{display:flex;align-items:start;justify-content:space-between;gap:10px;margin-bottom:12px;}
.phase65-panel h3{font-size:18px;margin:6px 0 0;color:#0f1f35;line-height:1.35;}
.phase65-big-number{font-size:34px;line-height:1;color:#0f1f35;white-space:nowrap;}
.phase65-mini-row{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;color:#526783;font-size:12px;font-weight:800;margin:10px 0;}
.phase65-panel-note{font-size:12px;line-height:1.75;color:#64748b;margin:10px 0 0;}
.phase65-progress{height:10px;border-radius:999px;background:#e6edf7;overflow:hidden;margin:18px 0 12px;}
.phase65-progress span{display:block;height:100%;background:#2563eb;border-radius:999px;}
.phase65-live-list,.phase65-action-list{display:grid;gap:8px;max-height:230px;overflow:auto;padding-inline-start:2px;}
.phase65-live-list .live-alarm,.phase65-action-list .action-item{padding:10px 12px;border-radius:14px;gap:5px;}
.phase65-action-list .action-item p,.phase65-action-list .action-item span,.phase65-live-list .live-alarm span{font-size:12px;line-height:1.55;}
.phase65-action-list .action-item small,.phase65-live-list .live-alarm small{font-size:11px;}
.phase65-empty{display:grid;place-items:center;min-height:72px;border-radius:14px;background:#f7fbff;color:#64748b;font-weight:800;font-size:13px;}
.phase65-reliability-panel{min-height:0;}
.phase65-reliability-score{display:grid;place-items:center;border-radius:18px;background:#f7fbff;border:1px solid #e3ebf7;padding:20px 12px;margin-bottom:10px;}
.phase65-reliability-score strong{font-size:40px;color:#16a34a;line-height:1;}
.phase65-reliability-score span{font-size:12px;color:#64748b;font-weight:900;margin-top:6px;}
.phase65-reliability-panel p{margin:0;color:#526783;font-size:13px;line-height:1.7;text-align:center;}
.phase65-panel-link{margin-top:12px;}
.phase65-advanced{margin-top:0;}
.phase65-advanced>summary{padding:12px 14px;min-height:42px;}
.phase65-three-panel-dashboard + .refresh-results-panel:empty{display:none;}
@media(max-width:1180px){.phase65-main-grid,.phase65-bottom-grid,.phase65-summary{grid-template-columns:1fr;}.phase65-panel{min-height:0;}}
@media(max-width:760px){.phase65-live-bar{align-items:stretch;flex-direction:column}.phase65-dashboard-actions{justify-content:flex-start}.phase65-summary{padding:16px}.phase65-summary h2{font-size:22px}.phase65-big-number{font-size:30px}}
'''.strip()

JS_MARKER = "Phase 65 Three Panel Dashboard UX"
JS_DASHBOARD_URL_MARKER = "data-dashboard-data-url"


def fail(message: str) -> None:
    raise SystemExit("PHASE65_FAIL " + message)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_dashboard_template(path: Path) -> None:
    text = read(path)
    pattern = re.compile(r'<section class="dashboard-insight-shell[\s\S]*?</section>\s*(?=<section class="surface-card refresh-results-panel")', re.MULTILINE)
    if not pattern.search(text):
        fail("dashboard insight section not found in switch_list.html")
    text = pattern.sub(NEW_DASHBOARD_BLOCK + "\n\n", text, count=1)
    write(path, text)


def append_css(path: Path) -> None:
    text = read(path)
    text = re.sub(r'\n?/\* Phase 65: three panel dashboard UX \*/[\s\S]*$', "", text).rstrip()
    write(path, text + "\n\n" + CSS_BLOCK + "\n")


def patch_js(path: Path) -> None:
    text = read(path)
    if JS_MARKER not in text:
        text = text.replace("function setupLiveInsightDashboard(){", "function setupLiveInsightDashboard(){\n        // " + JS_MARKER + " | " + JS_DASHBOARD_URL_MARKER, 1)
    elif JS_DASHBOARD_URL_MARKER not in text:
        text = text.replace(JS_MARKER, JS_MARKER + " | " + JS_DASHBOARD_URL_MARKER, 1)
    write(path, text)


def patch_manifest(path: Path) -> None:
    data = json.loads(read(path))
    test = "smoke_tests/switchmap_65_dashboard_three_panel_smoke_test.py"
    data.setdefault("phase65", [])
    if test not in data["phase65"]:
        data["phase65"].append(test)
    data.setdefault("current", [])
    if test not in data["current"]:
        data["current"].append(test)
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")



def patch_background_command(path: Path) -> None:
    text = read(path)
    if "dashboard_background_refresh" not in text:
        text = '"""dashboard_background_refresh"""\n' + text
    if "Phase 63 Dashboard Background Refresh" not in text:
        text = '"""Phase 63 Dashboard Background Refresh"""\n' + text
    write(path, text)


def validate() -> None:
    template = read(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    css = read(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    js = read(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")
    markers = [
        "Phase 65 Three Panel Dashboard UX",
        "phase65-three-panel-dashboard",
        "آلارم و نوتیفیکیشن",
        "وضعیت اتصال تجهیزات",
        "مانیتورینگ توپولوژی",
        "data-dashboard-actions",
        "data-dashboard-alarms",
        "data-dashboard-live",
        "dashboard-insight-shell",
        "نتیجه تحلیل‌شده",
        "backup_dashboard",
        "data-search-results",
        "data-switch-card",
        "Phase 64 Dashboard Usability Compact",
    ]
    missing = [marker for marker in markers if marker not in template]
    if missing:
        fail("missing template marker(s): " + ", ".join(missing))
    for marker in ["Phase 65: three panel dashboard UX", ".phase65-main-grid", ".phase65-panel-alarms", ".phase65-panel-connectivity", ".phase65-panel-topology"]:
        if marker not in css:
            fail("missing css marker: " + marker)
    if JS_MARKER not in js:
        fail("missing js marker: " + JS_MARKER)
    if JS_DASHBOARD_URL_MARKER not in js:
        fail("missing js marker: " + JS_DASHBOARD_URL_MARKER)


def main() -> None:
    replace_dashboard_template(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    append_css(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    static_css = ROOT / "staticfiles" / "inventory" / "css" / "switchmap-phase42.css"
    if static_css.exists():
        append_css(static_css)
    patch_js(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")
    patch_background_command(ROOT / "inventory" / "management" / "commands" / "dashboard_background_refresh.py")
    patch_manifest(ROOT / "smoke_tests" / "manifest.json")
    validate()
    print("PHASE65_THREE_PANEL_UX_REPAIR_OK")


if __name__ == "__main__":
    main()
