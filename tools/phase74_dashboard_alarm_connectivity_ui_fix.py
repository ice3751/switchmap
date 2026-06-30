from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PHASE = "phase74_dashboard_alarm_connectivity_ui_fix"
PROJECT = Path.cwd().resolve()
BACKUP_ROOT = PROJECT / "backups" / f"{PHASE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

SWITCH_LIST = PROJECT / "inventory" / "templates" / "inventory" / "switch_list.html"
CSS_TOPBAR = PROJECT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase43-47.css"
CSS_DASH = PROJECT / "inventory" / "static" / "inventory" / "css" / "switchmap-dashboard-stable-main.css"
JS_FILE = PROJECT / "inventory" / "static" / "inventory" / "switchmap.js"

MARKER_TEMPLATE = "phase74-connectivity-click-card"
MARKER_CSS_TOPBAR = "Phase 74 alarm notification topbar fix"
MARKER_CSS_DASH = "Phase 74 dashboard detail drawer and connectivity card fix"
MARKER_JS = "Phase 74 connectivity card detail drawer fix"

CSS_TOPBAR_SNIPPET = r'''

/* Phase 74 alarm notification topbar fix */
body .topbar-user.command-topbar-user{
    display:flex!important;
    align-items:center!important;
    justify-content:flex-end!important;
    gap:10px!important;
    flex:0 0 auto!important;
    min-width:max-content!important;
    overflow:visible!important;
    position:relative!important;
    z-index:900!important;
}
body .topbar-user.command-topbar-user .command-user-dropdown,
body .topbar-user.command-topbar-user .command-alarm-menu{
    flex:0 0 auto!important;
    overflow:visible!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip,
body .topbar-user.command-topbar-user .command-alarm-menu .alarm-mini-summary{
    width:42px!important;
    height:42px!important;
    min-width:42px!important;
    min-height:42px!important;
    max-width:42px!important;
    max-height:42px!important;
    padding:0!important;
    margin:0!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    border-radius:999px!important;
    background:#f59e0b!important;
    color:#111827!important;
    font-size:13px!important;
    line-height:1!important;
    font-weight:900!important;
    text-align:center!important;
    box-shadow:0 10px 24px rgba(245,158,11,.25)!important;
    white-space:nowrap!important;
    overflow:hidden!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip.is-critical,
body .topbar-user.command-topbar-user .command-alarm-menu .alarm-mini-summary.is-critical{
    background:#ef4444!important;
    color:#fff!important;
    box-shadow:0 10px 24px rgba(239,68,68,.26)!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip::after,
body .topbar-user.command-topbar-user .command-alarm-menu .alarm-mini-summary::after{
    display:none!important;
    content:""!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel,
body .topbar-user.command-topbar-user .alarm-mini-panel{
    position:absolute!important;
    top:calc(100% + 10px)!important;
    right:auto!important;
    left:0!important;
    min-width:250px!important;
    max-width:min(340px,90vw)!important;
    padding:14px!important;
    border-radius:18px!important;
    background:#fff!important;
    color:#0f172a!important;
    border:1px solid #dbe7f5!important;
    box-shadow:0 24px 55px rgba(15,23,42,.24)!important;
    z-index:2200!important;
    display:grid!important;
    gap:10px!important;
    text-align:right!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel strong,
body .topbar-user.command-topbar-user .alarm-mini-panel strong{
    font-size:14px!important;
    font-weight:850!important;
    color:#0f172a!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel a,
body .topbar-user.command-topbar-user .alarm-mini-panel a{
    min-height:36px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    border-radius:12px!important;
    background:#eff6ff!important;
    color:#1d4ed8!important;
    font-size:13px!important;
    font-weight:820!important;
    text-decoration:none!important;
}
'''

CSS_DASH_SNIPPET = r'''

/* Phase 74 dashboard detail drawer and connectivity card fix */
body.sm-main-dashboard-body .sm-main-card[data-dashboard-connectivity-card]{
    cursor:pointer!important;
}
body.sm-main-dashboard-body .sm-main-card[data-dashboard-connectivity-card]:hover{
    border-color:#93c5fd!important;
    box-shadow:0 20px 44px rgba(37,99,235,.12)!important;
}
body.sm-main-dashboard-body .sm-main-card[data-dashboard-connectivity-card]:focus-visible{
    outline:3px solid rgba(37,99,235,.35)!important;
    outline-offset:3px!important;
}
body.sm-main-dashboard-body .sm-main-card[data-dashboard-connectivity-card] .sm-main-summary span{
    cursor:pointer!important;
}
body.sm-main-dashboard-body .sm-main-card[data-dashboard-connectivity-card] .sm-main-note{
    margin-top:16px!important;
    color:#35537a!important;
    background:#f8fbff!important;
}
body.sm-main-dashboard-body .sm-main-detail-drawer{
    padding:18px!important;
    overflow:visible!important;
}
body.sm-main-dashboard-body .sm-main-detail-drawer dl{
    display:grid!important;
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
    gap:10px!important;
}
body.sm-main-dashboard-body .sm-main-detail-drawer dl>div{
    min-width:0!important;
    border:1px solid #e2ecf8!important;
    border-radius:14px!important;
    background:#f8fbff!important;
    padding:10px 12px!important;
}
body.sm-main-dashboard-body .sm-main-detail-drawer dt{
    margin-bottom:4px!important;
    color:#64748b!important;
    font-size:12px!important;
    font-weight:750!important;
}
body.sm-main-dashboard-body .sm-main-detail-drawer dd{
    margin:0!important;
    color:#0f172a!important;
    font-size:13px!important;
    font-weight:760!important;
    overflow-wrap:anywhere!important;
}
body.sm-main-dashboard-body .phase74-detail-extra{
    margin-top:14px!important;
    display:grid!important;
    gap:14px!important;
}
body.sm-main-dashboard-body .phase74-connectivity-group{
    border:1px solid #dbe7f5!important;
    border-radius:16px!important;
    background:#fff!important;
    overflow:hidden!important;
}
body.sm-main-dashboard-body .phase74-connectivity-group-title{
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:10px!important;
    padding:10px 13px!important;
    background:#f8fbff!important;
    border-bottom:1px solid #e5edf7!important;
    font-size:13px!important;
    font-weight:850!important;
    color:#0f172a!important;
}
body.sm-main-dashboard-body .phase74-connectivity-group-title b{
    min-width:24px!important;
    height:24px!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    border-radius:999px!important;
    background:#e0ecff!important;
    color:#1d4ed8!important;
    font-size:12px!important;
}
body.sm-main-dashboard-body .phase74-connectivity-list{
    display:grid!important;
    gap:0!important;
    max-height:310px!important;
    overflow:auto!important;
}
body.sm-main-dashboard-body .phase74-connectivity-item{
    display:grid!important;
    grid-template-columns:minmax(140px,1fr) minmax(90px,auto) minmax(120px,1.2fr)!important;
    align-items:center!important;
    gap:10px!important;
    padding:9px 13px!important;
    border-bottom:1px solid #eef3f9!important;
    color:#0f172a!important;
    text-decoration:none!important;
}
body.sm-main-dashboard-body .phase74-connectivity-item:last-child{border-bottom:0!important;}
body.sm-main-dashboard-body .phase74-connectivity-item:hover{background:#f8fbff!important;}
body.sm-main-dashboard-body .phase74-connectivity-item strong{
    min-width:0!important;
    font-size:13.4px!important;
    font-weight:850!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .phase74-connectivity-item small{
    direction:ltr!important;
    text-align:left!important;
    color:#64748b!important;
    font-size:12px!important;
    font-weight:700!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .phase74-connectivity-item span{
    min-width:0!important;
    color:#475569!important;
    font-size:12px!important;
    font-weight:650!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .phase74-connectivity-status-healthy .phase74-connectivity-group-title b{background:#dcfce7!important;color:#15803d!important;}
body.sm-main-dashboard-body .phase74-connectivity-status-poll_failed .phase74-connectivity-group-title b{background:#fee2e2!important;color:#b91c1c!important;}
body.sm-main-dashboard-body .phase74-connectivity-status-discovery_warning .phase74-connectivity-group-title b,
body.sm-main-dashboard-body .phase74-connectivity-status-stale .phase74-connectivity-group-title b{background:#fef3c7!important;color:#b45309!important;}
body.sm-main-dashboard-body .phase74-connectivity-status-not_monitored .phase74-connectivity-group-title b{background:#e2e8f0!important;color:#475569!important;}
@media (max-width:760px){
    body.sm-main-dashboard-body .sm-main-detail-drawer dl{grid-template-columns:1fr!important;}
    body.sm-main-dashboard-body .phase74-connectivity-item{grid-template-columns:1fr!important;gap:4px!important;}
    body.sm-main-dashboard-body .phase74-connectivity-item small{text-align:right!important;}
}
'''

JS_SNIPPET = r'''

/* Phase 74 connectivity card detail drawer fix */
(function(){
    if(window.__switchMapPhase74ConnectivityFixLoaded) return;
    window.__switchMapPhase74ConnectivityFixLoaded = true;

    function escapeHtml(value){
        return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch){
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch] || ch;
        });
    }
    function valueOrDash(value){
        value = String(value == null ? '' : value).trim();
        return value || '-';
    }
    function statusTitle(status){
        const map = {
            healthy:'سالم',
            poll_failed:'ناموفق',
            discovery_warning:'هشدار Discovery',
            stale:'داده قدیمی',
            not_monitored:'خارج از پایش'
        };
        return map[status] || status || 'نامشخص';
    }
    function statusOrder(status){
        const order = {poll_failed:0, discovery_warning:1, stale:2, not_monitored:3, healthy:4};
        return Object.prototype.hasOwnProperty.call(order, status) ? order[status] : 9;
    }
    function ensureExtra(drawer){
        let extra = drawer.querySelector('[data-phase74-detail-extra]');
        if(!extra){
            extra = document.createElement('div');
            extra.className = 'phase74-detail-extra';
            extra.setAttribute('data-phase74-detail-extra', '');
            const link = drawer.querySelector('[data-detail-url]');
            if(link && link.parentNode){
                link.parentNode.insertBefore(extra, link);
            }else{
                drawer.appendChild(extra);
            }
        }
        return extra;
    }
    function setDrawerText(drawer, selector, value){
        const el = drawer.querySelector(selector);
        if(el) el.textContent = valueOrDash(value);
    }
    function groupDevices(items){
        const groups = {};
        (items || []).forEach(function(item){
            const status = item.status || 'unknown';
            if(!groups[status]) groups[status] = [];
            groups[status].push(item);
        });
        return Object.keys(groups).sort(function(a,b){return statusOrder(a)-statusOrder(b);}).map(function(status){
            groups[status].sort(function(a,b){return String(a.name || '').localeCompare(String(b.name || ''), 'fa');});
            return {status:status, title:statusTitle(status), items:groups[status]};
        });
    }
    function renderConnectivity(items){
        const groups = groupDevices(items);
        if(!groups.length){
            return '<div class="phase66-empty modern-empty-state">داده اتصال تجهیزات هنوز آماده نیست.</div>';
        }
        return groups.map(function(group){
            const rows = group.items.map(function(item){
                const url = item.detail_url || '#';
                const reason = item.snmp_error || item.discovery_error || item.compact_reason || item.short_reason || item.conclusion || '';
                return '<a class="phase74-connectivity-item" href="' + escapeHtml(url) + '">' +
                    '<strong>' + escapeHtml(item.name || item.object_name || '-') + '</strong>' +
                    '<small>' + escapeHtml(item.ip || '-') + '</small>' +
                    '<span title="' + escapeHtml(reason) + '">' + escapeHtml(reason || item.last_poll_text || '-') + '</span>' +
                '</a>';
            }).join('');
            return '<section class="phase74-connectivity-group phase74-connectivity-status-' + escapeHtml(group.status) + '">' +
                '<div class="phase74-connectivity-group-title"><span>' + escapeHtml(group.title) + '</span><b>' + group.items.length + '</b></div>' +
                '<div class="phase74-connectivity-list">' + rows + '</div>' +
            '</section>';
        }).join('');
    }
    function openConnectivityDrawer(dashboard){
        const drawer = document.querySelector('[data-dashboard-detail-drawer]');
        if(!drawer) return;
        const counters = dashboard && dashboard.counters ? dashboard.counters : {};
        const items = dashboard && dashboard.device_items ? dashboard.device_items : [];
        const extra = ensureExtra(drawer);
        setDrawerText(drawer, '[data-detail-severity]', (counters.snmp_failed || counters.stale || 0) ? 'warning' : 'ok');
        setDrawerText(drawer, '[data-detail-title]', 'اتصال تجهیزات');
        setDrawerText(drawer, '[data-detail-object]', 'Devices / SNMP / Discovery');
        setDrawerText(drawer, '[data-detail-issue-id]', 'connectivity-summary');
        setDrawerText(drawer, '[data-detail-last-check]', dashboard && dashboard.generated_at ? dashboard.generated_at : 'ثبت نشده');
        setDrawerText(drawer, '[data-detail-reason]', 'لیست وضعیت تک‌تک دستگاه‌ها بر اساس آخرین Background Refresh.');
        setDrawerText(drawer, '[data-detail-action]', 'برای جزئیات هر دستگاه روی همان ردیف کلیک کن.');
        const link = drawer.querySelector('[data-detail-url]');
        if(link){
            link.href = '#';
            link.textContent = 'جزئیات دستگاه‌ها در همین پنل نمایش داده شده است';
            link.setAttribute('aria-disabled', 'true');
        }
        extra.hidden = false;
        extra.innerHTML = renderConnectivity(items);
        drawer.hidden = false;
        drawer.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
    function clearExtraForNormalDetails(target){
        if(target && target.closest && target.closest('[data-dashboard-connectivity-card]')) return;
        const drawer = document.querySelector('[data-dashboard-detail-drawer]');
        if(!drawer) return;
        const extra = drawer.querySelector('[data-phase74-detail-extra]');
        if(extra){ extra.hidden = true; extra.innerHTML = ''; }
        const link = drawer.querySelector('[data-detail-url]');
        if(link){
            link.textContent = 'Open exact detail';
            link.removeAttribute('aria-disabled');
        }
    }
    function fetchDashboard(root){
        const url = root && root.dataset ? root.dataset.dashboardDataUrl : '';
        if(!url) return Promise.resolve(null);
        return fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}})
            .then(function(response){return response.json();})
            .then(function(payload){return payload && payload.dashboard ? payload.dashboard : null;});
    }
    document.addEventListener('click', function(event){
        const card = event.target.closest('[data-dashboard-connectivity-card]');
        if(card){
            event.preventDefault();
            const root = document.querySelector('[data-dashboard-live]');
            fetchDashboard(root).then(function(dashboard){openConnectivityDrawer(dashboard || {});});
            return;
        }
        if(event.target.closest('[data-dashboard-detail]')) clearExtraForNormalDetails(event.target);
    }, true);
    document.addEventListener('keydown', function(event){
        if(event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('[data-dashboard-connectivity-card]');
        if(!card) return;
        event.preventDefault();
        card.click();
    });
})();
'''


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT))


def backup(path: Path) -> None:
    if not path.exists():
        return
    target = BACKUP_ROOT / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def append_once(path: Path, marker: str, snippet: str, changed: list[str]) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    text = read(path)
    if marker in text:
        print(f"SKIP_MARKER_EXISTS={rel(path)}::{marker}")
        return
    backup(path)
    write(path, text.rstrip() + snippet + "\n")
    changed.append(rel(path))
    print(f"APPENDED={rel(path)}")


def patch_switch_list(changed: list[str]) -> None:
    if not SWITCH_LIST.exists():
        raise FileNotFoundError(SWITCH_LIST)
    text = read(SWITCH_LIST)
    original = text

    if MARKER_TEMPLATE not in text:
        text = text.replace(
            '<article class="sm-main-card is-blue">',
            '<article class="sm-main-card is-blue phase74-connectivity-click-card" role="button" tabindex="0" data-dashboard-connectivity-card data-phase74-marker="phase74-connectivity-click-card">',
            1,
        )
        text = text.replace(
            '<p class="sm-main-note">جزئیات خطا فقط با کلیک نمایش داده می‌شود.</p>',
            '<p class="sm-main-note" data-dashboard-connectivity-note>برای مشاهده وضعیت تک‌تک دستگاه‌ها کلیک کن.</p>',
            1,
        )
    else:
        print("SKIP_MARKER_EXISTS=inventory/templates/inventory/switch_list.html::phase74-connectivity-click-card")

    # If Refresh View survived earlier phases, hide it at template level without touching background refresh.
    text = text.replace(
        '<button class="sm-main-refresh-btn btn btn-primary" type="button" data-dashboard-manual-refresh title="Refresh dashboard view">\n                <strong data-dashboard-background-icon aria-hidden="true">!</strong>\n                <span>Refresh View</span>\n            </button>\n            ',
        '',
        1,
    )

    if text != original:
        backup(SWITCH_LIST)
        write(SWITCH_LIST, text)
        changed.append(rel(SWITCH_LIST))
        print(f"PATCHED={rel(SWITCH_LIST)}")
    else:
        print(f"NO_TEMPLATE_CHANGE={rel(SWITCH_LIST)}")


def run(cmd: list[str]) -> int:
    print("RUN=" + " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(PROJECT), text=True)
    print(f"RETURN_CODE={completed.returncode}")
    return completed.returncode


def apply() -> int:
    print("PHASE74_DASHBOARD_ALARM_CONNECTIVITY_UI_FIX")
    print(f"PROJECT={PROJECT}")
    print(f"BACKUP={BACKUP_ROOT}")
    changed: list[str] = []
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    patch_switch_list(changed)
    append_once(CSS_TOPBAR, MARKER_CSS_TOPBAR, CSS_TOPBAR_SNIPPET, changed)
    append_once(CSS_DASH, MARKER_CSS_DASH, CSS_DASH_SNIPPET, changed)
    append_once(JS_FILE, MARKER_JS, JS_SNIPPET, changed)

    (BACKUP_ROOT / "changed_files.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
    print("CHANGED_FILES=" + str(len(changed)))
    for item in changed:
        print("CHANGED=" + item)

    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    if code != 0:
        return code
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "collectstatic", "--noinput", "-v", "0"])
    if code != 0:
        return code

    print("PHASE74_DASHBOARD_ALARM_CONNECTIVITY_UI_FIX_DONE")
    return 0


def verify() -> int:
    print("PHASE74_DASHBOARD_ALARM_CONNECTIVITY_UI_VERIFY")
    print(f"PROJECT={PROJECT}")
    checks = [
        (SWITCH_LIST, MARKER_TEMPLATE),
        (CSS_TOPBAR, MARKER_CSS_TOPBAR),
        (CSS_DASH, MARKER_CSS_DASH),
        (JS_FILE, MARKER_JS),
        (PROJECT / "staticfiles" / "inventory" / "css" / "switchmap-phase43-47.css", MARKER_CSS_TOPBAR),
        (PROJECT / "staticfiles" / "inventory" / "css" / "switchmap-dashboard-stable-main.css", MARKER_CSS_DASH),
        (PROJECT / "staticfiles" / "inventory" / "switchmap.js", MARKER_JS),
    ]
    ok = True
    for path, marker in checks:
        exists = path.exists()
        has = exists and marker in read(path)
        print(f"CHECK::{rel(path) if path.exists() or str(path).startswith(str(PROJECT)) else path}::EXISTS={'YES' if exists else 'NO'}::HAS_MARKER={'YES' if has else 'NO'}")
        ok = ok and has
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    ok = ok and code == 0
    print("PHASE74_VERIFY_RESULT=" + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        return verify()
    return apply()


if __name__ == "__main__":
    raise SystemExit(main())
