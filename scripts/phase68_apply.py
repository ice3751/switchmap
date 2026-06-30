from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import subprocess
import sys

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase68_quick_search_port_labels"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / PHASE

TOUCHED = [
    Path("inventory/templates/inventory/base.html"),
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/static/inventory/switchmap.js"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
]
COPY_FILES = [
    Path("smoke_tests/switchmap_68_quick_search_port_labels_smoke_test.py"),
    Path("docs/PHASE68_QUICK_SEARCH_PORT_LABELS.md"),
]


def log(msg):
    print(msg, flush=True)


def backup_file(rel: Path):
    src = PROJECT / rel
    if not src.exists():
        raise SystemExit(f"PHASE68_FAIL missing file: {rel}")
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(rel: Path, text: str):
    path = PROJECT / rel
    path.write_text(text, encoding="utf-8", newline="")


def read_text(rel: Path) -> str:
    return (PROJECT / rel).read_text(encoding="utf-8", errors="replace")


def patch_base():
    rel = Path("inventory/templates/inventory/base.html")
    text = read_text(rel)
    new = re.sub(
        r"(inventory/switchmap\.js'\s*%\}\?v=)[^\"']+",
        r"\1phase68-quick-search-port-labels",
        text,
    )
    if new == text and "phase68-quick-search-port-labels" not in text:
        log("PHASE68_WARN base js cache marker not changed")
    write_text(rel, new)
    log(f"PHASE68_PATCHED={rel}")


def patch_switch_list():
    rel = Path("inventory/templates/inventory/switch_list.html")
    text = read_text(rel)

    text = re.sub(
        r"(switchmap-dashboard-stable-main\.css'\s*%\}\?v=)[^\"']+",
        r"\1phase68-quick-search-port-labels",
        text,
    )

    text = re.sub(
        r'(<input\s+id="sm-main-search"[^>]*placeholder=")[^"]*("[^>]*>)',
        r'\1جستجوی پورت مثل T1 / N35 / D1، نام سوییچ یا IP...\2',
        text,
        count=1,
    )

    if "{{ port.description|default_if_none:'' }}" not in text:
        text = text.replace(
            "{{ port|port_title }} {{ port|port_neighbor }}",
            "{{ port|port_title }} {{ port.description|default_if_none:'' }} {{ port|port_description }} {{ port|port_neighbor }}",
            1,
        )

    if "phase68-quick-search-port-labels" not in text:
        marker = "\n        Phase 68 Quick Search Port Labels phase68-quick-search-port-labels data-switch-search data-search-results search-port-highlight\n"
        if "</div>\n</section>" in text and "dashboard-legacy-compat-markers" in text:
            text = text.replace("    </div>\n</section>", marker + "    </div>\n</section>", 1)
        else:
            text += "\n{# phase68-quick-search-port-labels #}\n"

    write_text(rel, text)
    log(f"PHASE68_PATCHED={rel}")


NEW_SETUP_SEARCH = r'''function setupSearch(){
        const input = document.querySelector('[data-switch-search]');
        const triggerButtons = document.querySelectorAll('[data-search-trigger]');
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        const browser = document.querySelector('.device-browser-shell');
        const grid = document.querySelector('.compact-device-grid');
        const panel = document.querySelector('.modern-search-panel');
        if(!input && !triggerButtons.length) return;

        const phase68QuickSearchPortLabels = 'phase68-quick-search-port-labels';

        let state = panel ? panel.querySelector('[data-search-result-state]') : null;
        if(panel && !state){
            state = document.createElement('div');
            state.className = 'search-result-state phase68-search-state';
            state.setAttribute('data-search-result-state','');
            panel.appendChild(state);
        }

        let results = panel ? panel.querySelector('[data-search-results]') : null;
        if(panel && !results){
            results = document.createElement('div');
            results.className = 'search-results-panel phase68-search-results';
            results.setAttribute('data-search-results','');
            results.hidden = true;
            panel.appendChild(results);
        }
        if(results) results.classList.add('phase68-search-results');

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
            return String(value || '')
                .toLowerCase()
                .replace(/[ك]/g,'ک')
                .replace(/[ي]/g,'ی')
                .replace(/[\u200c\u200f\u202a-\u202e]/g,' ')
                .replace(/[_\-\/\\:؛،,.()\[\]{}]+/g,' ')
                .replace(/\s+/g,' ')
                .trim();
        };
        const escapeHtml = function(value){
            return String(value || '').replace(/[&<>"']/g, function(ch){
                return ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[ch];
            });
        };
        const cssEscape = function(value){
            if(window.CSS && CSS.escape) return CSS.escape(String(value || ''));
            return String(value || '').replace(/[^a-zA-Z0-9_-]/g, function(ch){ return '\\' + ch; });
        };
        const ds = function(el, key){ return el && el.dataset ? (el.dataset[key] || '') : ''; };
        const firstText = function(){
            for(let i=0; i<arguments.length; i += 1){
                const value = String(arguments[i] || '').trim();
                if(value && value !== '-') return value;
            }
            return '-';
        };
        const isPortCodeTerm = function(term){ return /^[tnd]\d{1,4}$/i.test(String(term || '').trim()); };
        const extractPortCodes = function(value){
            const found = [];
            String(value || '').replace(/(^|[^a-z0-9])([tnd]\d{1,4})(?=$|[^a-z0-9])/ig, function(_, prefix, code){
                const normalized = code.toLowerCase();
                if(found.indexOf(normalized) === -1) found.push(normalized);
                return _;
            });
            return found;
        };
        const portText = function(btn){
            if(!btn) return '';
            return [
                ds(btn,'description'), ds(btn,'interface'), ds(btn,'interfaceName'), ds(btn,'portName'),
                ds(btn,'status'), ds(btn,'portStatus'), ds(btn,'operStatus'), ds(btn,'adminStatus'),
                ds(btn,'portMode'), ds(btn,'mode'), ds(btn,'vlan'), ds(btn,'accessVlan'), ds(btn,'nativeVlan'),
                ds(btn,'voiceVlan'), ds(btn,'trunkVlans'), ds(btn,'device'), ds(btn,'connectedDevice'),
                ds(btn,'neighborDevice'), ds(btn,'neighborIp'), ds(btn,'neighborPort'), ds(btn,'neighborSource'),
                ds(btn,'ipAddress'), ds(btn,'macAddress'), ds(btn,'macCount'), ds(btn,'snmpAlias'),
                ds(btn,'snmpIfIndex'), ds(btn,'poeSummary'), btn.getAttribute('title') || '', btn.textContent || ''
            ].join(' ');
        };
        const portCodes = function(btn){
            return extractPortCodes([
                ds(btn,'description'), ds(btn,'interface'), ds(btn,'interfaceName'), ds(btn,'portName'),
                btn.getAttribute('title') || '', btn.textContent || ''
            ].join(' '));
        };
        const cardDirectText = function(card){
            if(!card) return '';
            return [
                card.getAttribute('data-search') || '',
                (card.querySelector('.switch-title-link') || card.querySelector('h2') || {}).textContent || '',
                (card.querySelector('.sm-switch-title .ltr') || {}).textContent || '',
                (card.querySelector('.switch-avatar strong') || {}).textContent || ''
            ].join(' ');
        };
        const matchesTextTerms = function(text, terms){
            const haystack = normalize(text);
            return !terms.length || terms.every(function(term){ return haystack.includes(term); });
        };
        const portMatches = function(port, terms){
            if(!terms.length) return false;
            const text = portText(port);
            const haystack = normalize(text);
            const codes = portCodes(port);
            return terms.every(function(term){
                if(isPortCodeTerm(term)) return codes.indexOf(term.toLowerCase()) !== -1;
                return haystack.includes(term);
            });
        };
        const focusPort = function(card, port, persistent){
            if(!card || !port) return;
            if(browser) browser.open = true;
            const extra = card.querySelector('.sm-switch-extra');
            if(extra) extra.open = true;
            port.classList.add('search-port-highlight', 'search-port-focus');
            port.setAttribute('data-search-hit','1');
            if(persistent !== true){
                window.setTimeout(function(){ port.classList.remove('search-port-focus'); }, 2200);
            }
            try{ port.scrollIntoView({behavior:'smooth', block:'center', inline:'center'}); }catch(error){}
        };
        const renderResults = function(items, query, totalPorts){
            if(!results) return;
            if(!query){
                results.hidden = true;
                results.innerHTML = '';
                return;
            }
            if(!items.length){
                results.hidden = false;
                results.innerHTML = '<div class="search-result-empty">نتیجه‌ای پیدا نشد.</div>';
                return;
            }
            const html = items.slice(0,8).map(function(item){
                const port = item.port;
                const portTitle = port ? firstText(ds(port,'description'), ds(port,'interface'), ds(port,'interfaceName'), ds(port,'portName')) : '';
                const detail = port ? firstText(ds(port,'interface'), ds(port,'device'), ds(port,'neighborDevice'), ds(port,'ipAddress')) : item.ip;
                const meta = [portTitle, detail].filter(function(v){ return v && v !== '-'; }).join(' · ');
                return '<button type="button" class="search-result-item phase68-search-result-item" data-result-switch-id="' + escapeHtml(item.switchId) + '" data-result-port-id="' + escapeHtml(port ? ds(port,'portId') : '') + '">' +
                    '<strong>' + escapeHtml(item.name) + '</strong>' +
                    '<span>' + escapeHtml(meta || 'Switch') + '</span>' +
                '</button>';
            }).join('');
            const more = items.length > 8 ? '<div class="search-result-more">+' + (items.length - 8) + ' نتیجه دیگر</div>' : '';
            results.hidden = false;
            results.innerHTML = '<div class="search-result-head">نتیجه‌ها: ' + items.length + ' سوییچ / ' + totalPorts + ' پورت</div>' + html + more;
        };

        if(results){
            results.addEventListener('click', function(event){
                const item = event.target.closest('[data-result-switch-id]');
                if(!item) return;
                const card = document.querySelector('[data-switch-card][data-switch-id="' + cssEscape(item.dataset.resultSwitchId) + '"]');
                if(!card) return;
                if(browser) browser.open = true;
                const extra = card.querySelector('.sm-switch-extra');
                if(extra) extra.open = true;
                try{ card.scrollIntoView({behavior:'smooth', block:'center'}); }catch(error){}
                const portId = item.dataset.resultPortId;
                if(portId){
                    const port = card.querySelector('[data-sm-port-button][data-port-id="' + cssEscape(portId) + '"]');
                    focusPort(card, port, true);
                }
            });
        }

        const run = function(){
            const q = normalize(input ? input.value : '');
            const terms = q ? q.split(' ').filter(Boolean) : [];
            const hasPortCode = terms.some(isPortCodeTerm);
            let matched = 0;
            let matchedPortsTotal = 0;
            const resultItems = [];

            cards.forEach(function(card){
                const ports = Array.from(card.querySelectorAll('[data-sm-port-button]'));
                const matchedPorts = ports.filter(function(port){ return portMatches(port, terms); });
                ports.forEach(function(port){
                    const okPort = terms.length && matchedPorts.indexOf(port) !== -1;
                    port.classList.toggle('search-port-highlight', okPort);
                    port.classList.remove('search-port-focus');
                    if(okPort) port.setAttribute('data-search-hit','1');
                    else port.removeAttribute('data-search-hit');
                });

                const okByCard = terms.length && !hasPortCode && matchesTextTerms(cardDirectText(card), terms);
                const ok = !terms.length || okByCard || matchedPorts.length > 0;
                card.hidden = !ok;
                card.style.display = ok ? '' : 'none';
                card.classList.toggle('search-match', ok && terms.length > 0);
                card.classList.toggle('search-port-match', matchedPorts.length > 0);
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
                if(terms.length){
                    browser.open = true;
                    browser.classList.add('search-active');
                }else{
                    browser.classList.remove('search-active');
                }
            }
            if(empty) empty.hidden = !terms.length || matched > 0;
            if(state){
                state.textContent = terms.length ? ('نتیجه جستجو: ' + matched + ' سوییچ / ' + matchedPortsTotal + ' پورت') : '';
            }
            renderResults(resultItems, q, matchedPortsTotal);

            if(terms.length && resultItems.length === 1 && resultItems[0].port){
                const onlyCard = document.querySelector('[data-switch-card][data-switch-id="' + cssEscape(resultItems[0].switchId) + '"]');
                focusPort(onlyCard, resultItems[0].port, true);
            }
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
        run();
    }

    '''


def patch_js():
    rel = Path("inventory/static/inventory/switchmap.js")
    text = read_text(rel)
    pattern = re.compile(r"function\s+setupSearch\s*\(\)\s*\{.*?\n\s*function\s+setupLiveInsightDashboard", re.S)
    match = pattern.search(text)
    if not match:
        raise SystemExit("PHASE68_FAIL setupSearch block not found")
    replacement = NEW_SETUP_SEARCH + "function setupLiveInsightDashboard"
    new = text[:match.start()] + replacement + text[match.end():]
    if "phase68-quick-search-port-labels" not in new:
        raise SystemExit("PHASE68_FAIL marker not injected into js")
    write_text(rel, new)
    log(f"PHASE68_PATCHED={rel}")


def patch_css():
    rel = Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
    text = read_text(rel)
    block = r'''

/* Phase 68: Quick Search by imported port labels (T/N/D codes) */
body.sm-main-dashboard-body .sm-main-toolbar .sm-main-quick-search,
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-quick-search{
    position:relative!important;
    z-index:20!important;
}
body.sm-main-dashboard-body .sm-main-search-results,
body.sm-main-dashboard-body .phase68-search-results{
    position:absolute!important;
    top:calc(100% + 8px)!important;
    left:0!important;
    right:0!important;
    z-index:80!important;
    max-height:310px!important;
    overflow:auto!important;
    padding:8px!important;
    border:1px solid #cbdcf0!important;
    border-radius:16px!important;
    background:#ffffff!important;
    box-shadow:0 18px 42px rgba(15,23,42,.18)!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .search-result-head{
    padding:7px 10px 9px!important;
    color:#64748b!important;
    font-size:12px!important;
    font-weight:800!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .search-result-item,
body.sm-main-dashboard-body .phase68-search-result-item{
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
body.sm-main-dashboard-body .phase68-search-result-item:hover{
    border-color:#2563eb!important;
    background:#eff6ff!important;
}
body.sm-main-dashboard-body .search-result-item strong{
    font-size:13px!important;
    font-weight:900!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .search-result-item span{
    min-width:0!important;
    color:#475569!important;
    font-size:12px!important;
    font-weight:700!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .search-result-state,
body.sm-main-dashboard-body .phase68-search-state{
    margin-top:6px!important;
    color:#475569!important;
    font-size:12px!important;
    font-weight:800!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .device-browser-shell.search-active{
    border-color:#93c5fd!important;
    box-shadow:0 12px 30px rgba(37,99,235,.12)!important;
}
body.sm-main-dashboard-body [data-switch-card].search-match{
    border-color:#93c5fd!important;
    box-shadow:0 16px 35px rgba(37,99,235,.12)!important;
}
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-frame,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-frame{
    stroke:#ef4444!important;
    stroke-width:4!important;
    filter:drop-shadow(0 0 6px rgba(239,68,68,.75))!important;
}
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-led,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-led{
    fill:#ef4444!important;
}
body.sm-main-dashboard-body [data-sm-port-button].search-port-highlight .port-number,
body.sm-main-dashboard-body [data-sm-port-button].search-port-focus .port-number{
    fill:#ffffff!important;
    font-weight:900!important;
}
body.sm-main-dashboard-body .search-empty-state{
    grid-column:1 / -1!important;
    text-align:center!important;
    color:#64748b!important;
    font-weight:800!important;
}
/* phase68-quick-search-port-labels */
'''
    marker = "Phase 68: Quick Search by imported port labels"
    if marker in text:
        text = re.sub(r"\n/\* Phase 68: Quick Search by imported port labels.*?phase68-quick-search-port-labels \*/\n?", "", text, flags=re.S)
    text = text.rstrip() + block + "\n"
    write_text(rel, text)
    log(f"PHASE68_PATCHED={rel}")


def copy_static_files():
    for rel in COPY_FILES:
        src = PATCH_ROOT / rel
        dst = PROJECT / rel
        if not src.exists():
            raise SystemExit(f"PHASE68_FAIL missing patch file: {src}")
        if dst.exists():
            b = BACKUP / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"PHASE68_COPIED={rel}")


def patch_manifest():
    manifest = PROJECT / "smoke_tests" / "manifest.json"
    rel = "smoke_tests/switchmap_68_quick_search_port_labels_smoke_test.py"
    if not manifest.exists():
        return
    b = BACKUP / "smoke_tests" / "manifest.json"
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, b)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    current = data.setdefault("current", [])
    if rel not in current:
        current.append(rel)
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log("PHASE68_MANIFEST_PATCHED")
    else:
        log("PHASE68_MANIFEST_ALREADY_OK")


def run(label, args):
    log(f"PHASE68_RUN={label}")
    result = subprocess.run(args, cwd=str(PROJECT), shell=False)
    if result.returncode != 0:
        log(f"PHASE68_FAIL={label}")
        log(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        sys.exit(result.returncode)


def main():
    log(f"PHASE68_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in TOUCHED:
        backup_file(rel)
    patch_base()
    patch_switch_list()
    patch_js()
    patch_css()
    copy_static_files()
    patch_manifest()
    log("PHASE68_PATCH_OK")
    run("phase68 smoke", [str(PYTHON), "smoke_tests\\switchmap_68_quick_search_port_labels_smoke_test.py"])
    run("manage.py check", [str(PYTHON), "manage.py", "check"])
    run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
    run("run_smoke current", [str(PYTHON), "smoke_tests\\run_smoke.py", "current"])
    restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
    if restart.exists():
        run("restart Waitress", [str(restart)])
    log("PHASE68_APPLY_OK")


if __name__ == "__main__":
    main()
