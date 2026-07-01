from pathlib import Path
from datetime import datetime
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
PHASE = "phase70_limited_quick_search_fix"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"

FILES = [
    "inventory/templates/inventory/includes/cisco_3850_svg.html",
    "inventory/templates/inventory/includes/generic_port_button.html",
    "inventory/templates/inventory/includes/nexus_svg.html",
    "inventory/static/inventory/switchmap.js",
    "inventory/static/inventory/css/switchmap-dashboard-stable-main.css",
]

def fail(msg):
    print(f"PHASE70_FAIL {msg}")
    sys.exit(1)

def read(rel):
    p = PROJECT / rel
    if not p.exists():
        fail(f"missing {rel}")
    return p.read_text(encoding="utf-8")

def write(rel, text):
    (PROJECT / rel).write_text(text, encoding="utf-8", newline="")

def backup_files():
    for rel in FILES:
        src = PROJECT / rel
        if src.exists():
            dst = BACKUP / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    print(f"PHASE70_BACKUP={BACKUP}")

def patch_cisco():
    rel = "inventory/templates/inventory/includes/cisco_3850_svg.html"
    text = read(rel)
    if "PHASE70_LIMITED_QUICK_SEARCH_FIX" not in text:
        if 'data-port-label=' not in text:
            text = text.replace(
                'data-interface="{{ port|port_label }}"\n',
                'data-interface="{{ port|port_label }}"\n'
                '                       data-port-label="{{ port.description|default_if_none:\'\' }}"\n'
                '                       data-port-description="{{ port|port_description }}"\n',
            )
        text = text.rstrip() + "\n\n{# PHASE70_LIMITED_QUICK_SEARCH_FIX: data attributes only; no layout/render change #}\n"
    write(rel, text)

def patch_generic():
    rel = "inventory/templates/inventory/includes/generic_port_button.html"
    text = read(rel)
    if "PHASE70_LIMITED_QUICK_SEARCH_FIX" not in text:
        if 'data-port-label=' not in text:
            text = text.replace(
                '        data-interface="{{ port|port_label }}"\n',
                '        data-interface="{{ port|port_label }}"\n'
                '        data-port-label="{{ port.description|default_if_none:\'\' }}"\n'
                '        data-port-description="{{ port|port_description }}"\n'
                '        data-search-code="{{ port.description|default_if_none:\'\' }} {{ port.cable_label|default_if_none:\'\' }} {{ port.outlet|default_if_none:\'\' }}"\n',
            )
        text = text.rstrip() + "\n{# PHASE70_LIMITED_QUICK_SEARCH_FIX: data attributes only; no layout/render change #}\n"
    write(rel, text)

def patch_nexus():
    rel = "inventory/templates/inventory/includes/nexus_svg.html"
    text = read(rel)
    if "PHASE70_LIMITED_QUICK_SEARCH_FIX" not in text:
        if 'data-port-label=' not in text:
            text = text.replace(
                '                                        data-interface-name="{{ port.interface_name }}"\n',
                '                                        data-interface-name="{{ port.interface_name }}"\n'
                '                                        data-interface="{{ port.interface_name }}"\n'
                '                                        data-port-label="{{ port.description|default_if_none:\'\' }}"\n'
                '                                        data-port-description="{{ port.description|default_if_none:\'\' }}"\n'
                '                                        data-search-code="{{ port.description|default_if_none:\'\' }} {{ port.cable_label|default_if_none:\'\' }} {{ port.outlet|default_if_none:\'\' }}"\n',
            )
        text = text.rstrip() + "\n{# PHASE70_LIMITED_QUICK_SEARCH_FIX: data attributes only; no layout/render change #}\n"
    write(rel, text)

def patch_js():
    rel = "inventory/static/inventory/switchmap.js"
    text = read(rel)
    marker = "PHASE70_LIMITED_QUICK_SEARCH_FIX"
    if marker in text:
        write(rel, text)
        return
    start = text.find("    function setupSearch(){")
    end = text.find("    function setupLiveInsightDashboard(){", start)
    if start == -1 or end == -1:
        fail("setupSearch block not found")
    new_func = r'''    function setupSearch(){
        /* PHASE70_LIMITED_QUICK_SEARCH_FIX: data-only search; no port re-render; no layout change */
        const input = document.querySelector('[data-switch-search]');
        const triggerButtons = document.querySelectorAll('[data-search-trigger]');
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        const browser = document.querySelector('.device-browser-shell');
        const grid = document.querySelector('.compact-device-grid');
        const panel = document.querySelector('.modern-search-panel');
        const browserInitialOpen = browser ? browser.open : false;
        if(!input && !triggerButtons.length) return;

        let state = panel ? panel.querySelector('[data-search-result-state]') : null;
        if(panel && !state){
            state = document.createElement('div');
            state.className = 'search-result-state';
            state.setAttribute('data-search-result-state','');
            panel.appendChild(state);
        }

        let results = panel ? panel.querySelector('[data-search-results]') : null;
        if(panel && !results){
            results = document.createElement('div');
            results.className = 'search-results-panel';
            results.setAttribute('data-search-results','');
            results.hidden = true;
            panel.appendChild(results);
        }

        let empty = grid ? grid.querySelector('[data-search-empty-state]') : null;
        if(grid && !empty){
            empty = document.createElement('section');
            empty.className = 'surface-card empty-card search-empty-state';
            empty.setAttribute('data-search-empty-state','');
            empty.textContent = 'نتیجه‌ای برای این جستجو پیدا نشد.';
            empty.hidden = true;
            grid.appendChild(empty);
        }

        const normalize = function(value){
            const fa = '۰۱۲۳۴۵۶۷۸۹';
            const ar = '٠١٢٣٤٥٦٧٨٩';
            return String(value || '')
                .replace(/[۰-۹]/g, function(ch){ return String(fa.indexOf(ch)); })
                .replace(/[٠-٩]/g, function(ch){ return String(ar.indexOf(ch)); })
                .toLowerCase()
                .replace(/[\u200c\u200f\u202a-\u202e]/g,' ')
                .replace(/[_\-\/\\:]+/g,' ')
                .replace(/\s+/g,' ')
                .trim();
        };
        const escapeHtml = function(value){
            return String(value || '').replace(/[&<>"']/g, function(ch){
                return ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[ch];
            });
        };
        const ds = function(el, key){ return el && el.dataset ? (el.dataset[key] || '') : ''; };
        const firstText = function(){
            for(let i=0; i<arguments.length; i += 1){
                const value = String(arguments[i] || '').trim();
                if(value && value !== '-') return value;
            }
            return '-';
        };
        const matchesAll = function(text, terms){
            const haystack = normalize(text);
            return !terms.length || terms.every(function(term){ return haystack.includes(term); });
        };
        const portText = function(btn){
            if(!btn) return '';
            return [
                ds(btn,'portLabel'), ds(btn,'portDescription'), ds(btn,'searchCode'), ds(btn,'officeLabel'),
                ds(btn,'description'), ds(btn,'interface'), ds(btn,'interfaceName'), ds(btn,'portName'),
                ds(btn,'status'), ds(btn,'portStatus'), ds(btn,'operStatus'), ds(btn,'adminStatus'),
                ds(btn,'portMode'), ds(btn,'mode'), ds(btn,'vlan'), ds(btn,'accessVlan'), ds(btn,'nativeVlan'),
                ds(btn,'voiceVlan'), ds(btn,'trunkVlans'), ds(btn,'device'), ds(btn,'connectedDevice'),
                ds(btn,'neighborDevice'), ds(btn,'neighborIp'), ds(btn,'neighborPort'), ds(btn,'neighborSource'),
                ds(btn,'ipAddress'), ds(btn,'macAddress'), ds(btn,'macCount'), ds(btn,'snmpAlias'),
                ds(btn,'snmpIfIndex'), ds(btn,'poeSummary')
            ].join(' ');
        };
        const switchText = function(card){
            if(!card) return '';
            const title = card.querySelector('.switch-title-link') || card.querySelector('h2');
            const ip = card.querySelector('.sm-switch-title .ltr');
            const model = card.querySelector('.switch-avatar strong');
            return [
                card.getAttribute('data-search') || '', card.dataset.switchName || '', card.dataset.switchId || '',
                title ? title.textContent : '', ip ? ip.textContent : '', model ? model.textContent : ''
            ].join(' ');
        };
        const clearHighlights = function(card){
            const root = card || document;
            root.querySelectorAll('[data-sm-port-button]').forEach(function(port){
                port.classList.remove('search-port-highlight','search-port-focus');
            });
        };
        const resetSearchView = function(){
            cards.forEach(function(card){
                card.hidden = false;
                card.style.display = '';
                card.classList.remove('search-match');
                clearHighlights(card);
            });
            if(browser){
                browser.classList.remove('search-active');
                browser.open = browserInitialOpen;
            }
            if(empty) empty.hidden = true;
            if(state) state.textContent = '';
            if(results){ results.hidden = true; results.innerHTML = ''; }
        };
        const renderResults = function(items, query, totalPorts){
            if(!results) return;
            if(!query){ results.hidden = true; results.innerHTML = ''; return; }
            if(!items.length){
                results.hidden = false;
                results.innerHTML = '<div class="search-result-empty">نتیجه‌ای پیدا نشد.</div>';
                return;
            }
            const html = items.slice(0,8).map(function(item){
                const port = item.port;
                const label = port ? firstText(ds(port,'portLabel'), ds(port,'officeLabel'), ds(port,'searchCode')) : '';
                const iface = port ? firstText(ds(port,'interface'), ds(port,'interfaceName'), ds(port,'portName')) : '';
                const device = port ? firstText(ds(port,'device'), ds(port,'connectedDevice'), ds(port,'neighborDevice'), ds(port,'portDescription'), ds(port,'description')) : '';
                const meta = [item.ip, item.model, label, iface, device].filter(function(v){ return v && v !== '-'; }).join(' · ');
                return '<button type="button" class="search-result-item" data-result-switch-id="' + escapeHtml(item.switchId) + '" data-result-port-id="' + escapeHtml(port ? ds(port,'portId') : '') + '">' +
                    '<strong>' + escapeHtml(item.name) + '</strong>' +
                    '<span>' + escapeHtml(meta || 'Switch') + '</span>' +
                '</button>';
            }).join('');
            const more = items.length > 8 ? '<div class="search-result-more">+' + (items.length - 8) + ' نتیجه دیگر</div>' : '';
            results.hidden = false;
            results.innerHTML = '<div class="search-result-head">نتیجه‌ها: ' + items.length + ' دستگاه / ' + totalPorts + ' پورت</div>' + html + more;
        };

        if(results){
            results.addEventListener('click', function(event){
                const item = event.target.closest('[data-result-switch-id]');
                if(!item) return;
                const card = document.querySelector('[data-switch-card][data-switch-id="' + item.dataset.resultSwitchId + '"]');
                if(!card) return;
                if(browser) browser.open = true;
                card.hidden = false;
                card.style.display = '';
                card.scrollIntoView({behavior:'smooth', block:'center'});
                const portId = item.dataset.resultPortId;
                if(portId){
                    const port = card.querySelector('[data-sm-port-button][data-port-id="' + portId + '"]');
                    if(port){
                        port.classList.add('search-port-focus','search-port-highlight');
                        window.setTimeout(function(){ port.classList.remove('search-port-focus'); }, 1800);
                        port.scrollIntoView({behavior:'smooth', block:'center', inline:'center'});
                    }
                }
            });
        }

        const run = function(){
            const q = normalize(input ? input.value : '');
            const terms = q ? q.split(' ').filter(Boolean) : [];
            if(!terms.length){ resetSearchView(); return; }

            let matched = 0;
            let matchedPortsTotal = 0;
            const resultItems = [];

            cards.forEach(function(card){
                const ports = Array.from(card.querySelectorAll('[data-sm-port-button]'));
                const matchedPorts = ports.filter(function(port){ return matchesAll(portText(port), terms); });
                ports.forEach(function(port){ port.classList.toggle('search-port-highlight', matchedPorts.indexOf(port) !== -1); });

                const ok = matchesAll(switchText(card), terms) || matchedPorts.length > 0;
                card.hidden = !ok;
                card.style.display = ok ? '' : 'none';
                card.classList.toggle('search-match', ok);
                if(ok){
                    matched += 1;
                    matchedPortsTotal += matchedPorts.length;
                    resultItems.push({
                        switchId: card.dataset.switchId || '',
                        name: firstText((card.querySelector('.switch-title-link') || card.querySelector('h2') || {}).textContent, card.dataset.switchName, 'Switch'),
                        ip: firstText((card.querySelector('.sm-switch-title .ltr') || {}).textContent, ''),
                        model: firstText((card.querySelector('.switch-avatar strong') || {}).textContent, ''),
                        port: matchedPorts[0] || null
                    });
                }
            });

            if(browser){
                browser.open = true;
                browser.classList.add('search-active');
            }
            if(empty) empty.hidden = matched > 0;
            if(state) state.textContent = 'نتیجه جستجو: ' + matched + ' دستگاه / ' + matchedPortsTotal + ' پورت';
            renderResults(resultItems, q, matchedPortsTotal);
        };

        if(input){
            input.addEventListener('input', run);
            input.addEventListener('search', run);
            input.addEventListener('keydown', function(event){
                if(event.key === 'Enter'){
                    event.preventDefault();
                    run();
                }
            });
        }
        triggerButtons.forEach(function(btn){ btn.addEventListener('click', run); });
        resetSearchView();
    }

'''
    text = text[:start] + new_func + text[end:]
    write(rel, text)

def patch_css():
    rel = "inventory/static/inventory/css/switchmap-dashboard-stable-main.css"
    text = read(rel)
    marker = "PHASE70_LIMITED_QUICK_SEARCH_FIX"
    if marker not in text:
        text = text.rstrip() + r'''

/* PHASE70_LIMITED_QUICK_SEARCH_FIX: highlight only; no size/layout change */
.sm-main-dashboard .sm-switch-card.search-match{
    border-color:#38bdf8!important;
    box-shadow:0 18px 42px rgba(56,189,248,.16)!important;
}
.sm-main-dashboard .sm-svg-port.search-port-highlight .port-frame,
.sm-main-dashboard .sm-svg-port.search-port-focus .port-frame{
    stroke:#38bdf8!important;
    stroke-width:3!important;
    filter:drop-shadow(0 0 5px rgba(56,189,248,.72))!important;
}
.sm-main-dashboard .dynamic-port.search-port-highlight,
.sm-main-dashboard .dynamic-port.search-port-focus,
.sm-main-dashboard .nexus-port.search-port-highlight,
.sm-main-dashboard .nexus-port.search-port-focus{
    outline:2px solid #38bdf8!important;
    outline-offset:2px!important;
    box-shadow:0 0 0 3px rgba(56,189,248,.20)!important;
}
.sm-main-dashboard .search-empty-state{
    grid-column:1 / -1!important;
}
'''
    write(rel, text)

def validate():
    checks = {
        "cisco data-port-label": "data-port-label" in read("inventory/templates/inventory/includes/cisco_3850_svg.html"),
        "generic data-port-label": "data-port-label" in read("inventory/templates/inventory/includes/generic_port_button.html"),
        "nexus data-port-label": "data-port-label" in read("inventory/templates/inventory/includes/nexus_svg.html"),
        "js marker": "PHASE70_LIMITED_QUICK_SEARCH_FIX" in read("inventory/static/inventory/switchmap.js"),
        "css marker": "PHASE70_LIMITED_QUICK_SEARCH_FIX" in read("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
        "no rerender marker": "no port re-render" in read("inventory/static/inventory/switchmap.js"),
    }
    for name, ok in checks.items():
        print(f"PHASE70_CHECK::{name}={'OK' if ok else 'FAIL'}")
        if not ok:
            fail(f"validation {name}")

backup_files()
patch_cisco()
patch_generic()
patch_nexus()
patch_js()
patch_css()
validate()
print("PHASE70_PATCH_OK")
