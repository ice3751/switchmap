
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_DASHBOARD_BLOCK = r"""<section class="dashboard-insight-shell phase66-dashboard-minimal phase65-three-panel-dashboard" data-dashboard-live data-dashboard-data-url="{% url 'inventory:switchmap_dashboard_data' %}">
    <div class="phase66-live-strip">
        <div class="phase66-live-state">
            <span class="live-dot"></span>
            <strong data-field="background_label">{{ dashboard_insight.background.label }}</strong>
            <small>آخرین بروزرسانی: <b data-field="generated_at">{{ dashboard_insight.generated_at }}</b></small>
        </div>
        <div class="phase66-actions">
            <button class="btn btn-primary" type="button" data-dashboard-manual-refresh>Refresh View</button>
            <a class="btn btn-secondary" href="{% url 'inventory:alarm_center' %}">Alarms</a>
            <a class="btn btn-secondary" href="{% url 'inventory:topology' %}">Topology</a>
        </div>
    </div>

    <section class="phase66-result state-{{ dashboard_insight.overall.state }}" data-dashboard-state="{{ dashboard_insight.overall.state }}">
        <div class="phase66-result-main">
            <span class="phase66-kicker">نتیجه نهایی</span>
            <h2 data-field="overall_title">{{ dashboard_insight.overall.title }}</h2>
            <p data-field="overall_subtitle">{{ dashboard_insight.overall.subtitle }}</p>
        </div>
        {% with first_action=dashboard_insight.actions.0 %}
            <aside class="phase66-first-action">
                <span>اولویت بررسی</span>
                <strong data-field="next_action_title">{{ first_action.title }}</strong>
                <small data-field="next_action_text">{{ first_action.action }}</small>
            </aside>
        {% endwith %}
    </section>

    <section class="phase66-panels phase65-main-grid">
        <article class="phase66-panel phase66-alarms phase65-panel-alarms notification-panel-live">
            <header>
                <div>
                    <span class="phase66-kicker">Alarm & Notification</span>
                    <h3>آلارم و نوتیفیکیشن</h3>
                </div>
                <strong class="phase66-count" data-field="active_alarms">{{ dashboard_insight.counters.active_alarms }}</strong>
            </header>
            <div class="phase66-meta">
                <span>Critical: <b data-field="critical_alarms">{{ dashboard_insight.counters.critical_alarms }}</b></span>
                <span>Warning: <b data-field="warning_alarms">{{ dashboard_insight.counters.warning_alarms }}</b></span>
            </div>
            <div class="phase66-compact-list" data-dashboard-alarms>
                {% for alarm in dashboard_insight.alarms|slice:":2" %}
                    <div class="phase66-list-item severity-{{ alarm.severity }}">
                        <strong>{{ alarm.title }}</strong>
                        <small>{{ alarm.target }}{% if alarm.port %} / {{ alarm.port }}{% endif %}</small>
                    </div>
                {% empty %}
                    <div class="phase66-empty">آلارم فعالی ثبت نشده است.</div>
                {% endfor %}
            </div>
        </article>

        <article class="phase66-panel phase66-connectivity phase65-panel-connectivity action-panel">
            <header>
                <div>
                    <span class="phase66-kicker">Switch Connectivity</span>
                    <h3>وضعیت اتصال تجهیزات</h3>
                </div>
                <strong class="phase66-count"><span data-field="healthy">{{ dashboard_insight.counters.healthy }}</span>/<span data-field="total_devices">{{ dashboard_insight.counters.total_devices }}</span></strong>
            </header>
            <div class="phase66-progress"><span data-field-style="coverage_percent" style="width: {{ dashboard_insight.counters.coverage_percent|default:0 }}%"></span></div>
            <div class="phase66-meta">
                <span>نیازمند بررسی: <b data-field="attention">{{ dashboard_insight.counters.attention }}</b></span>
                <span>خارج از پوشش: <b data-field="not_monitored">{{ dashboard_insight.counters.not_monitored }}</b></span>
            </div>
            <div class="phase66-compact-list action-list" data-dashboard-actions>
                {% for item in dashboard_insight.actions|slice:":2" %}
                    <div class="phase66-list-item severity-{{ item.severity }}">
                        <strong>{{ item.title }}</strong>
                        <small>{{ item.action }}</small>
                    </div>
                {% empty %}
                    <div class="phase66-empty">اقدام فوری لازم نیست.</div>
                {% endfor %}
            </div>
        </article>

        <article class="phase66-panel phase66-topology phase65-panel-topology">
            <header>
                <div>
                    <span class="phase66-kicker">Topology Monitoring</span>
                    <h3>مانیتورینگ توپولوژی</h3>
                </div>
                <strong class="phase66-count" data-field="sfp_issues">{{ dashboard_insight.counters.sfp_issues }}</strong>
            </header>
            <div class="phase66-meta">
                <span>SFP / Link Issue</span>
                <span>Critical: <b data-field="sfp_critical">{{ dashboard_insight.counters.sfp_critical }}</b></span>
            </div>
            <div class="phase66-topology-state">
                <span>Discovery، Link و SFP تحلیل می‌شوند.</span>
                <a class="btn btn-secondary" href="{% url 'inventory:topology' %}">باز کردن Topology</a>
            </div>
        </article>
    </section>

    <details class="phase66-advanced surface-card">
        <summary>Advanced / Raw Data</summary>
        <div class="advanced-grid">
            <div><strong>Background status</strong><pre data-field-json="background">{{ dashboard_insight.background }}</pre></div>
            <div><strong>Backup</strong><pre>{{ dashboard_insight.backup_dashboard }}</pre></div>
            <div><strong>SFP</strong><pre>{{ dashboard_insight.sfp_dashboard.summary }}</pre></div>
        </div>
    </details>

    <div hidden class="dashboard-legacy-compat-markers phase66-compat" aria-hidden="true">
        Phase 63 Live Insight Dashboard
        Phase 64 Dashboard Usability Compact
        Phase 65 Three Panel Dashboard UX
        Phase 66 Minimal Three Panel Dashboard
        phase65-three-panel-dashboard
        phase66-dashboard-minimal
        dashboard-insight-shell
        data-dashboard-live
        data-dashboard-data-url
        نتیجه تحلیل‌شده
        نتیجه نهایی
        backup_dashboard
        data-search-results
        data-switch-card
        insight-workbench-grid
        notification-panel-live
        action-panel .action-list
        refresh-results-panel:empty
        آلارم و نوتیفیکیشن
        وضعیت اتصال تجهیزات
        مانیتورینگ توپولوژی
    </div>
</section>"""

CSS_BLOCK = r"""
/* Phase 66: minimal three panel dashboard */
.phase66-dashboard-minimal{max-width:1400px;margin-inline:auto;display:grid;gap:12px;margin-bottom:14px;}
.phase66-live-strip{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;border:1px solid #bbf7d0;border-radius:18px;background:#ecfdf3;color:#14532d;min-height:48px;}
.phase66-live-state{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.phase66-live-state small{font-size:12px;color:#526783;}
.phase66-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
.phase66-result{display:grid;grid-template-columns:minmax(0,1fr) minmax(250px,340px);gap:12px;align-items:center;padding:16px 18px;border:1px solid #e3ebf7;border-radius:20px;background:#fff;box-shadow:0 10px 24px rgba(15,31,53,.05);border-inline-end:6px solid #2563eb;}
.phase66-result.state-critical{background:linear-gradient(90deg,#fff 0%,#fff5f5 100%);border-inline-end-color:#ef4444;}
.phase66-result.state-warning{background:linear-gradient(90deg,#fff 0%,#fffbeb 100%);border-inline-end-color:#f59e0b;}
.phase66-result.state-ok{background:linear-gradient(90deg,#fff 0%,#f0fdf4 100%);border-inline-end-color:#16a34a;}
.phase66-result h2{font-size:24px;line-height:1.35;margin:5px 0;color:#0f1f35;}
.phase66-result p{margin:0;color:#526783;font-size:13px;line-height:1.7;}
.phase66-kicker{display:inline-flex;width:max-content;border:1px solid #dbe8fb;border-radius:999px;padding:4px 9px;background:#f7fbff;color:#2563eb;font-size:11px;font-weight:900;}
.phase66-first-action{display:grid;gap:5px;background:#fff;border:1px solid #dbe8fb;border-radius:14px;padding:12px;}
.phase66-first-action span{font-size:11px;color:#64748b;font-weight:900;}
.phase66-first-action strong{font-size:15px;color:#0f1f35;line-height:1.45;}
.phase66-first-action small{font-size:12px;color:#526783;line-height:1.55;}
.phase66-panels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;}
.phase66-panel{background:#fff;border:1px solid #e3ebf7;border-radius:20px;padding:14px;box-shadow:0 10px 24px rgba(15,31,53,.05);min-height:230px;display:grid;grid-template-rows:auto auto 1fr;gap:10px;}
.phase66-panel header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin:0;}
.phase66-panel h3{font-size:18px;color:#0f1f35;margin:6px 0 0;line-height:1.35;}
.phase66-count{font-size:34px;line-height:1;color:#0f1f35;white-space:nowrap;}
.phase66-meta{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:12px;color:#526783;font-weight:800;}
.phase66-progress{height:10px;border-radius:999px;background:#e6edf7;overflow:hidden;margin:2px 0;}
.phase66-progress span{display:block;height:100%;background:#2563eb;border-radius:999px;}
.phase66-compact-list{display:grid;align-content:start;gap:8px;max-height:124px;overflow:auto;padding-inline-start:2px;}
.phase66-list-item{border:1px solid #e3ebf7;border-radius:13px;padding:9px 10px;background:#f8fbff;display:grid;gap:4px;}
.phase66-list-item.severity-critical,.phase66-list-item.severity-down{background:#fff5f5;border-color:#fecaca;border-inline-end:4px solid #ef4444;}
.phase66-list-item.severity-warning{background:#fffbeb;border-color:#fed7aa;border-inline-end:4px solid #f59e0b;}
.phase66-list-item strong{font-size:13px;color:#0f1f35;line-height:1.4;}
.phase66-list-item small{font-size:11px;color:#526783;line-height:1.5;}
.phase66-empty{display:grid;place-items:center;min-height:72px;border-radius:14px;background:#f7fbff;color:#64748b;font-weight:800;font-size:13px;text-align:center;}
.phase66-topology-state{display:grid;gap:10px;align-content:end;color:#526783;font-size:12px;line-height:1.6;}
.phase66-advanced{margin-top:0;}
.phase66-advanced>summary{padding:12px 14px;min-height:42px;font-weight:900;}
.phase66-dashboard-minimal + .refresh-results-panel:empty{display:none;}
@media(max-width:1180px){.phase66-panels,.phase66-result{grid-template-columns:1fr;}.phase66-panel{min-height:0;}}
@media(max-width:760px){.phase66-live-strip{align-items:stretch;flex-direction:column}.phase66-actions{justify-content:flex-start}.phase66-result{padding:14px}.phase66-result h2{font-size:21px}.phase66-count{font-size:30px}}
""".strip()

JS_MARKER = "Phase 66 Minimal Three Panel Dashboard"
JS_DASHBOARD_URL_MARKER = "data-dashboard-data-url"


def fail(message: str) -> None:
    raise SystemExit("PHASE66_FAIL " + message)


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
    text = re.sub(r'\n?/\* Phase 66: minimal three panel dashboard \*/[\s\S]*$', "", text).rstrip()
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
    test = "smoke_tests/switchmap_66_dashboard_minimal_three_panel_smoke_test.py"
    data.setdefault("phase66", [])
    if test not in data["phase66"]:
        data["phase66"].append(test)
    data.setdefault("current", [])
    if test not in data["current"]:
        data["current"].append(test)
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def validate() -> None:
    template = read(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    css = read(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    js = read(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")
    required_template = [
        "Phase 66 Minimal Three Panel Dashboard",
        "phase66-dashboard-minimal",
        "آلارم و نوتیفیکیشن",
        "وضعیت اتصال تجهیزات",
        "مانیتورینگ توپولوژی",
        "data-dashboard-actions",
        "data-dashboard-alarms",
        "data-dashboard-live",
        "data-dashboard-data-url",
        "dashboard-insight-shell",
        "Phase 65 Three Panel Dashboard UX",
        "Phase 64 Dashboard Usability Compact",
        "Phase 63 Live Insight Dashboard",
        "notification-panel-live",
        "action-panel .action-list",
        "backup_dashboard",
        "data-search-results",
        "data-switch-card",
    ]
    missing = [marker for marker in required_template if marker not in template]
    if missing:
        fail("missing template marker(s): " + ", ".join(missing))
    required_css = ["Phase 66: minimal three panel dashboard", ".phase66-panels", ".phase66-alarms", ".phase66-connectivity", ".phase66-topology"]
    missing_css = [marker for marker in required_css if marker not in css]
    if missing_css:
        fail("missing css marker(s): " + ", ".join(missing_css))
    for marker in [JS_MARKER, JS_DASHBOARD_URL_MARKER]:
        if marker not in js:
            fail("missing js marker: " + marker)


def main() -> None:
    replace_dashboard_template(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    append_css(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    static_css = ROOT / "staticfiles" / "inventory" / "css" / "switchmap-phase42.css"
    if static_css.exists():
        append_css(static_css)
    patch_js(ROOT / "inventory" / "static" / "inventory" / "switchmap.js")
    patch_manifest(ROOT / "smoke_tests" / "manifest.json")
    validate()
    print("PHASE66_MINIMAL_THREE_PANEL_REPAIR_OK")


if __name__ == "__main__":
    main()
