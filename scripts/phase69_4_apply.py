from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import subprocess
import sys

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase69_4_quick_search_repair"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / PHASE

TOUCH = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
    Path("smoke_tests/manifest.json"),
]
COPY_FILES = [
    Path("smoke_tests/switchmap_69_4_quick_search_repair_smoke_test.py"),
    Path("docs/PHASE69_4_QUICK_SEARCH_REPAIR.md"),
]

JS_BLOCK = r'''

// Phase 69.4: isolated quick-search repair for imported T/N/D port labels.
(function(){
    'use strict';
    const MARKER = 'phase69-4-quick-search-repair';
    const compat68 = 'phase68-quick-search-port-labels';
    let initialized = false;

    function normalize(value){
        return String(value || '')
            .toLowerCase()
            .replace(/[ك]/g,'ک')
            .replace(/[ي]/g,'ی')
            .replace(/[\u200c\u200f\u202a-\u202e]/g,' ')
            .replace(/[_\-\/\\:؛،,.()[\]{}]+/g,' ')
            .replace(/\s+/g,' ')
            .trim();
    }
    function escapeHtml(value){
        return String(value || '').replace(/[&<>"']/g, function(ch){
            return ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[ch];
        });
    }
    function isCode(term){ return /^[tnd]\d{1,4}$/i.test(String(term || '').trim()); }
    function codesFrom(value){
        const out = [];
        String(value || '').replace(/(^|[^a-z0-9])([tnd]\d{1,4})(?=$|[^a-z0-9])/ig, function(_, prefix, code){
            const c = code.toLowerCase();
            if(out.indexOf(c) === -1) out.push(c);
            return _;
        });
        return out;
    }
    function textOf(el){ return el ? String(el.textContent || '').trim() : ''; }
    function data(el, name){ return el && el.dataset ? (el.dataset[name] || '') : ''; }
    function first(){
        for(let i=0;i<arguments.length;i+=1){
            const v = String(arguments[i] || '').trim();
            if(v && v !== '-') return v;
        }
        return '-';
    }
    function cssEscape(value){
        if(window.CSS && CSS.escape) return CSS.escape(String(value || ''));
        return String(value || '').replace(/[^a-zA-Z0-9_-]/g, function(ch){ return '\\' + ch; });
    }
    function portHaystack(port){
        return [
            data(port,'description'), data(port,'interface'), data(port,'interfaceName'), data(port,'portName'),
            data(port,'device'), data(port,'connectedDevice'), data(port,'neighborDevice'), data(port,'neighborPort'),
            data(port,'ipAddress'), data(port,'macAddress'), data(port,'status'), data(port,'portStatus'),
            data(port,'portMode'), data(port,'accessVlan'), data(port,'nativeVlan'), data(port,'voiceVlan'),
            data(port,'trunkVlans'), port.getAttribute('title') || '', textOf(port)
        ].join(' ');
    }
    function portCodes(port){
        return codesFrom([
            data(port,'description'), port.getAttribute('title') || '', data(port,'interface'),
            data(port,'interfaceName'), data(port,'portName'), textOf(port)
        ].join(' '));
    }
    function portMatches(port, terms){
        if(!terms.length) return false;
        const hay = normalize(portHaystack(port));
        const codes = portCodes(port);
        return terms.every(function(term){
            if(isCode(term)) return codes.indexOf(term.toLowerCase()) !== -1;
            return hay.indexOf(term) !== -1;
        });
    }
    function cardText(card){
        return [
            card.getAttribute('data-search') || '',
            data(card,'switchName'), data(card,'switchIp'),
            textOf(card.querySelector('.switch-title-link')),
            textOf(card.querySelector('h2')),
            textOf(card.querySelector('.sm-switch-title .ltr')),
            textOf(card.querySelector('.switch-avatar strong'))
        ].join(' ');
    }
    function cardMatches(card, terms){
        const hay = normalize(cardText(card));
        return terms.every(function(term){ return hay.indexOf(term) !== -1; });
    }
    function clearPortState(card){
        card.querySelectorAll('[data-sm-port-button], .search-port-highlight, .search-port-focus, .phase69-4-port-hit').forEach(function(port){
            port.classList.remove('search-port-highlight','search-port-focus','phase69-4-port-hit');
            port.removeAttribute('data-search-hit');
        });
    }
    function highlight(port){
        if(!port) return;
        port.classList.add('search-port-highlight','search-port-focus','phase69-4-port-hit');
        port.setAttribute('data-search-hit','1');
    }
    function renderResults(results, items, q){
        if(!results) return;
        if(!q){
            results.hidden = true;
            results.innerHTML = '';
            return;
        }
        results.hidden = false;
        if(!items.length){
            results.innerHTML = '<div class="search-result-empty">نتیجه‌ای پیدا نشد.</div>';
            return;
        }
        const html = items.slice(0,10).map(function(item){
            const code = item.port ? first(data(item.port,'description'), data(item.port,'interface'), item.port.getAttribute('title')) : 'Switch';
            const iface = item.port ? first(data(item.port,'interface'), data(item.port,'interfaceName'), data(item.port,'portName')) : '';
            return '<button type="button" class="search-result-item phase68-search-result-item phase69-4-search-result-item" data-result-switch-id="' + escapeHtml(item.switchId) + '" data-result-port-id="' + escapeHtml(item.port ? data(item.port,'portId') : '') + '">' +
                '<strong>' + escapeHtml(item.name) + '</strong>' +
                '<span>' + escapeHtml(code + (iface && iface !== code ? ' · ' + iface : '')) + '</span>' +
            '</button>';
        }).join('');
        results.innerHTML = '<div class="search-result-head">نتیجه جستجو: ' + items.length + ' سوییچ</div>' + html;
    }
    function runSearch(ctx){
        const input = ctx.input;
        const q = normalize(input ? input.value : '');
        const terms = q.split(' ').filter(Boolean);
        const hasCode = terms.some(isCode);
        const browser = ctx.browser;
        const cards = ctx.cards;
        const results = ctx.results;
        const state = ctx.state;
        let visible = 0;
        let hitPorts = 0;
        const resultItems = [];

        cards.forEach(function(card){
            clearPortState(card);
            const ports = Array.from(card.querySelectorAll('[data-sm-port-button]'));
            const matchedPorts = terms.length ? ports.filter(function(port){ return portMatches(port, terms); }) : [];
            const okCard = terms.length && !hasCode ? cardMatches(card, terms) : false;
            const ok = !terms.length || okCard || matchedPorts.length > 0;

            card.hidden = !ok;
            card.style.display = ok ? '' : 'none';
            card.classList.toggle('search-match', ok && terms.length > 0);
            card.classList.toggle('search-port-match', matchedPorts.length > 0);
            card.classList.toggle('phase69-4-switch-hit', matchedPorts.length > 0);

            if(ok){
                visible += 1;
                hitPorts += matchedPorts.length;
                matchedPorts.forEach(highlight);
                resultItems.push({
                    switchId: data(card,'switchId') || card.getAttribute('data-switch-id') || '',
                    name: first(textOf(card.querySelector('.switch-title-link')), textOf(card.querySelector('h2')), data(card,'switchName'), 'Switch'),
                    port: matchedPorts[0] || null
                });
            }
        });

        if(browser){
            if(terms.length){
                browser.open = true;
                browser.classList.add('search-active','phase69-search-visual-stable','phase69-4-search-active');
            }else{
                browser.classList.remove('search-active','phase69-search-visual-stable','phase69-4-search-active');
            }
        }
        if(state){
            state.textContent = terms.length ? ('نتیجه جستجو: ' + visible + ' سوییچ / ' + hitPorts + ' پورت') : '';
        }
        renderResults(results, resultItems, q);

        if(terms.length && resultItems.length === 1){
            const card = document.querySelector('[data-switch-card][data-switch-id="' + cssEscape(resultItems[0].switchId) + '"]');
            if(card){
                const extra = card.querySelector('.sm-switch-extra');
                if(extra) extra.open = false;
                window.setTimeout(function(){
                    try{ card.scrollIntoView({behavior:'smooth', block:'center'}); }catch(error){}
                }, 50);
            }
        }
    }
    function init(){
        const input = document.querySelector('#sm-main-search, [data-switch-search]');
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        if(!input || !cards.length) return;
        const browser = document.querySelector('.device-browser-shell');
        const panel = input.closest('.modern-search-panel, .sm-main-quick-search, form') || input.parentElement;
        let results = panel ? panel.querySelector('[data-search-results]') : document.querySelector('[data-search-results]');
        if(panel && !results){
            results = document.createElement('div');
            results.className = 'sm-main-search-results phase68-search-results phase69-4-search-results';
            results.setAttribute('data-search-results','');
            results.hidden = true;
            panel.appendChild(results);
        }
        let state = panel ? panel.querySelector('[data-search-result-state]') : null;
        if(panel && !state){
            state = document.createElement('div');
            state.className = 'search-result-state phase69-4-search-state';
            state.setAttribute('data-search-result-state','');
            panel.appendChild(state);
        }
        const ctx = {input:input, cards:cards, browser:browser, results:results, state:state};
        const delayedRun = function(){ window.setTimeout(function(){ runSearch(ctx); }, 0); };
        input.setAttribute('data-phase69-4-search-ready','1');
        input.addEventListener('input', delayedRun);
        input.addEventListener('search', delayedRun);
        input.addEventListener('keyup', delayedRun);
        document.querySelectorAll('[data-search-trigger]').forEach(function(btn){ btn.addEventListener('click', delayedRun); });
        if(results){
            results.addEventListener('click', function(event){
                const item = event.target.closest('[data-result-switch-id]');
                if(!item) return;
                const card = document.querySelector('[data-switch-card][data-switch-id="' + cssEscape(item.dataset.resultSwitchId) + '"]');
                if(!card) return;
                if(browser) browser.open = true;
                const portId = item.dataset.resultPortId;
                if(portId){
                    const port = card.querySelector('[data-sm-port-button][data-port-id="' + cssEscape(portId) + '"]');
                    highlight(port);
                }
                try{ card.scrollIntoView({behavior:'smooth', block:'center'}); }catch(error){}
            });
        }
        runSearch(ctx);
        initialized = true;
    }
    function boot(){
        if(initialized) return;
        init();
        window.setTimeout(init, 350);
        window.setTimeout(init, 1200);
    }
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
    window.SwitchMapPhase694QuickSearchRepair = { init:init, marker:MARKER, compat:compat68 };
})();
'''

CSS_BLOCK = r'''

/* Phase 69.4: restore Quick Search behavior and keep switch cards stable */
body.sm-main-dashboard-body .sm-main-quick-search,
body.sm-main-dashboard-body .modern-search-panel{
    position:relative!important;
    overflow:visible!important;
    z-index:50!important;
}
body.sm-main-dashboard-body .sm-main-search-results,
body.sm-main-dashboard-body .phase68-search-results,
body.sm-main-dashboard-body .phase69-4-search-results{
    position:absolute!important;
    top:calc(100% + 8px)!important;
    left:0!important;
    right:0!important;
    z-index:120!important;
    max-height:310px!important;
    overflow:auto!important;
    padding:8px!important;
    border:1px solid #cbdcf0!important;
    border-radius:16px!important;
    background:#fff!important;
    box-shadow:0 18px 42px rgba(15,23,42,.18)!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .phase69-4-search-state,
body.sm-main-dashboard-body .search-result-state{
    margin-top:6px!important;
    color:#475569!important;
    font-size:12px!important;
    font-weight:800!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .search-result-head{
    padding:7px 10px 9px!important;
    color:#64748b!important;
    font-size:12px!important;
    font-weight:800!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .search-result-item,
body.sm-main-dashboard-body .phase69-4-search-result-item{
    width:100%!important;
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:12px!important;
    margin:0 0 7px!important;
    padding:11px 12px!important;
    border:1px solid #d7e4f4!important;
    border-radius:13px!important;
    background:#f8fbff!important;
    color:#0f172a!important;
    cursor:pointer!important;
    text-align:right!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .search-result-item:hover,
body.sm-main-dashboard-body .phase69-4-search-result-item:hover{
    border-color:#2563eb!important;
    background:#eff6ff!important;
}
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active .compact-device-grid,
body.sm-main-dashboard-body .device-browser-shell.search-active .compact-device-grid{
    grid-template-columns:minmax(0, 1fr)!important;
    align-items:start!important;
}
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active [data-switch-card],
body.sm-main-dashboard-body .device-browser-shell.search-active [data-switch-card]{
    width:100%!important;
    max-width:100%!important;
    min-width:0!important;
}
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active .sm-switch-extra,
body.sm-main-dashboard-body .device-browser-shell.search-active .sm-switch-extra{
    display:none!important;
}
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active .sm-map-scroll,
body.sm-main-dashboard-body .device-browser-shell.search-active .sm-map-scroll,
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active .sm-3850-svg-scroll,
body.sm-main-dashboard-body .device-browser-shell.search-active .sm-3850-svg-scroll{
    max-width:100%!important;
    overflow-x:auto!important;
    overflow-y:hidden!important;
}
body.sm-main-dashboard-body [data-sm-port-button].phase69-4-port-hit .port-frame,
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-frame,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-frame{
    stroke:#ef4444!important;
    stroke-width:4!important;
    filter:drop-shadow(0 0 6px rgba(239,68,68,.75))!important;
}
body.sm-main-dashboard-body [data-sm-port-button].phase69-4-port-hit .port-led,
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-led,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-led{
    fill:#ef4444!important;
}
body.sm-main-dashboard-body [data-sm-port-button].phase69-4-port-hit .port-number,
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-number,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-number{
    fill:#fff!important;
    font-weight:900!important;
}
/* phase69-4-quick-search-repair */
'''

def log(msg):
    print(msg, flush=True)

def backup(rel: Path):
    src = PROJECT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def read(rel: Path) -> str:
    return (PROJECT / rel).read_text(encoding="utf-8", errors="replace")

def write(rel: Path, text: str):
    (PROJECT / rel).write_text(text, encoding="utf-8", newline="")

def copy_files():
    for rel in COPY_FILES:
        src = PATCH_ROOT / rel
        if not src.exists():
            raise SystemExit(f"PHASE69_4_FAIL missing patch file: {rel}")
        backup(rel)
        dst = PROJECT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"PHASE69_4_COPIED={rel}")

def patch_base():
    rel = Path("inventory/templates/inventory/base.html")
    text = read(rel)
    text = re.sub(r"(inventory/switchmap\.js'\s*%\}\?v=)[^\"']+", r"\1phase69-4-quick-search-repair", text)
    if "phase68-quick-search-port-labels" not in text:
        text += "\n<!-- phase68-quick-search-port-labels compatibility marker -->\n"
    if "phase69-4-quick-search-repair" not in text:
        text += "\n<!-- phase69-4-quick-search-repair -->\n"
    write(rel, text)
    log(f"PHASE69_4_PATCHED={rel}")

def patch_switch_list():
    rel = Path("inventory/templates/inventory/switch_list.html")
    text = read(rel)
    text = re.sub(r"(switchmap-dashboard-stable-main\.css'\s*%\}\?v=)[^\"']+", r"\1phase69-4-quick-search-repair", text)
    if "{{ port.description|default_if_none:'' }}" not in text:
        text = text.replace(
            "{{ port|port_title }} {{ port|port_neighbor }}",
            "{{ port|port_title }} {{ port.description|default_if_none:'' }} {{ port|port_description }} {{ port|port_neighbor }}",
            1,
        )
    for marker in ["phase68-quick-search-port-labels", "phase69-search-visual-stable", "phase69-4-quick-search-repair"]:
        if marker not in text:
            text += f"\n{{# {marker} compatibility marker #}}\n".replace("{#", "{#")
    write(rel, text)
    log(f"PHASE69_4_PATCHED={rel}")

def patch_css():
    rel = Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
    text = read(rel)
    text = re.sub(r"\n/\* Phase 69\.4: restore Quick Search behavior.*?phase69-4-quick-search-repair \*/\n?", "\n", text, flags=re.S)
    text = text.rstrip() + CSS_BLOCK + "\n"
    write(rel, text)
    log(f"PHASE69_4_PATCHED={rel}")

def patch_js():
    rel = Path("inventory/static/inventory/switchmap.js")
    text = read(rel)
    text = re.sub(r"\n// Phase 69\.4: isolated quick-search repair.*?window\.SwitchMapPhase694QuickSearchRepair = \{ init:init, marker:MARKER, compat:compat68 \};\n\}\)\(\);\n?", "\n", text, flags=re.S)
    text = text.rstrip() + JS_BLOCK + "\n"
    if "phase68-quick-search-port-labels" not in text:
        text += "\n// phase68-quick-search-port-labels\n"
    write(rel, text)
    log(f"PHASE69_4_PATCHED={rel}")

def patch_manifest():
    rel = Path("smoke_tests/manifest.json")
    path = PROJECT / rel
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    current = data.setdefault("current", [])
    smoke = "smoke_tests/switchmap_69_4_quick_search_repair_smoke_test.py"
    if smoke not in current:
        current.append(smoke)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log("PHASE69_4_MANIFEST_PATCHED")
    else:
        log("PHASE69_4_MANIFEST_ALREADY_OK")

def run(label, args):
    log(f"PHASE69_4_RUN={label}")
    r = subprocess.run(args, cwd=str(PROJECT), shell=False)
    if r.returncode != 0:
        log(f"PHASE69_4_FAIL={label}")
        log(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        sys.exit(r.returncode)

def main():
    log(f"PHASE69_4_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in TOUCH:
        backup(rel)
    copy_files()
    patch_base()
    patch_switch_list()
    patch_css()
    patch_js()
    patch_manifest()
    run("phase69.4 smoke", [str(PYTHON), "smoke_tests\\switchmap_69_4_quick_search_repair_smoke_test.py"])
    run("manage.py check", [str(PYTHON), "manage.py", "check"])
    run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
    run("run_smoke current", [str(PYTHON), "smoke_tests\\run_smoke.py", "current"])
    restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
    if restart.exists():
        run("restart Waitress", [str(restart)])
    log("PHASE69_4_APPLY_OK")

if __name__ == "__main__":
    main()
