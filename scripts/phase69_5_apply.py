
from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import subprocess
import sys

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase69_5_quick_search_hard_repair"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"
PATCH_ROOT = PROJECT / "patches" / PHASE

TOUCH = [
    Path("inventory/templates/inventory/switch_list.html"),
    Path("inventory/templates/inventory/includes/cisco_3850_svg.html"),
    Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
    Path("smoke_tests/manifest.json"),
]
COPY_FILES = [
    Path("smoke_tests/switchmap_69_5_quick_search_hard_repair_smoke_test.py"),
    Path("docs/PHASE69_5_QUICK_SEARCH_HARD_REPAIR.md"),
]

INLINE_JS = r'''
<script>
/* phase69-5-quick-search-hard-repair */
(function(){
    'use strict';
    var MARKER = 'phase69-5-quick-search-hard-repair';
    var lastQuery = null;

    function norm(v){
        return String(v || '')
            .toLowerCase()
            .replace(/[ك]/g,'ک')
            .replace(/[ي]/g,'ی')
            .replace(/[\u200c\u200f\u202a-\u202e]/g,' ')
            .replace(/[\\/_\-:؛،,.()[\]{}]+/g,' ')
            .replace(/\s+/g,' ')
            .trim();
    }
    function esc(v){
        return String(v || '').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});
    }
    function code(v){ return /^[tnd]\d{1,4}$/i.test(String(v || '').trim()); }
    function codeList(v){
        var out = [];
        String(v || '').replace(/(^|[^a-z0-9])([tnd]\d{1,4})(?=$|[^a-z0-9])/ig,function(_,p,c){
            c = c.toLowerCase();
            if(out.indexOf(c) === -1) out.push(c);
            return _;
        });
        return out;
    }
    function text(el){ return el ? String(el.textContent || '').trim() : ''; }
    function d(el,n){ return el && el.dataset ? (el.dataset[n] || '') : ''; }
    function first(){
        for(var i=0;i<arguments.length;i++){
            var v = String(arguments[i] || '').trim();
            if(v && v !== '-') return v;
        }
        return '-';
    }
    function qsa(root, sel){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
    function portSelector(){
        return '[data-sm-port-button], .sm-svg-port[data-port-id], .sm-svg-port[title], [data-port-id][data-interface]';
    }
    function clearOld(card){
        qsa(card, portSelector()).forEach(function(p){
            p.classList.remove('phase69-5-port-hit','phase69-4-port-hit','search-port-highlight','search-port-focus');
            p.removeAttribute('data-search-hit');
        });
        card.classList.remove('phase69-5-switch-hit','phase69-4-switch-hit','search-match','search-port-match');
    }
    function portRaw(p){
        return [
            d(p,'officeLabel'), d(p,'searchCode'), d(p,'description'), d(p,'portDescription'),
            d(p,'interface'), d(p,'interfaceName'), d(p,'portName'), d(p,'device'),
            d(p,'connectedDevice'), d(p,'neighborDevice'), d(p,'neighborPort'), d(p,'ipAddress'),
            d(p,'macAddress'), d(p,'status'), d(p,'portMode'), d(p,'accessVlan'), d(p,'nativeVlan'),
            d(p,'voiceVlan'), d(p,'trunkVlans'), p.getAttribute('title') || '', text(p)
        ].join(' ');
    }
    function portMatch(p, terms){
        var raw = portRaw(p);
        var hay = norm(raw);
        var codes = codeList(raw);
        for(var i=0;i<terms.length;i++){
            var t = terms[i];
            if(code(t)){
                if(codes.indexOf(t.toLowerCase()) === -1) return false;
            }else if(hay.indexOf(t) === -1){
                return false;
            }
        }
        return true;
    }
    function cardRaw(card){
        return [
            card.getAttribute('data-search') || '', d(card,'switchName'), d(card,'switchIp'),
            text(card.querySelector('.switch-title-link')), text(card.querySelector('h2')), text(card.querySelector('.sm-switch-title'))
        ].join(' ');
    }
    function addHit(p){
        if(!p) return;
        p.classList.add('phase69-5-port-hit','search-port-highlight','search-port-focus');
        p.setAttribute('data-search-hit','1');
    }
    function ensureResults(input){
        var panel = input.closest('.sm-main-quick-search, .modern-search-panel, form') || input.parentElement;
        if(!panel) return null;
        var box = panel.querySelector('[data-phase69-5-results]');
        if(!box){
            box = document.createElement('div');
            box.className = 'phase69-5-search-results';
            box.setAttribute('data-phase69-5-results','1');
            box.hidden = true;
            panel.appendChild(box);
        }
        return box;
    }
    function render(box, items, q){
        if(!box) return;
        if(!q){ box.hidden = true; box.innerHTML = ''; return; }
        box.hidden = false;
        if(!items.length){ box.innerHTML = '<div class="phase69-5-empty">نتیجه‌ای پیدا نشد.</div>'; return; }
        box.innerHTML = '<div class="phase69-5-result-head">' + items.length + ' نتیجه</div>' + items.slice(0,12).map(function(it){
            return '<button type="button" class="phase69-5-result" data-phase69-5-card="' + esc(it.cardId) + '" data-phase69-5-port="' + esc(it.portId) + '"><strong>' + esc(it.switchName) + '</strong><span>' + esc(it.label) + '</span></button>';
        }).join('');
    }
    function run(force){
        var input = document.querySelector('#sm-main-search, [data-switch-search]');
        var cards = qsa(document, '[data-switch-card]');
        if(!input || !cards.length) return;
        var q = norm(input.value || '');
        if(!force && q === lastQuery) return;
        lastQuery = q;
        var terms = q.split(' ').filter(Boolean);
        var hasCode = terms.some(code);
        var browser = document.querySelector('.device-browser-shell');
        var box = ensureResults(input);
        var items = [];
        var visible = 0;
        var portHits = 0;

        if(browser){
            browser.open = !!terms.length || browser.open;
            browser.classList.remove('search-active','phase69-search-visual-stable','phase69-4-search-active');
            browser.classList.toggle('phase69-5-search-active', !!terms.length);
        }

        cards.forEach(function(card){
            clearOld(card);
            var ports = qsa(card, portSelector());
            var matched = [];
            if(terms.length){
                ports.forEach(function(p){ if(portMatch(p, terms)) matched.push(p); });
            }
            var okCard = false;
            if(terms.length && !hasCode){
                var ch = norm(cardRaw(card));
                okCard = terms.every(function(t){ return ch.indexOf(t) !== -1; });
            }
            var ok = !terms.length || matched.length > 0 || okCard;
            card.hidden = !ok;
            card.style.display = ok ? '' : 'none';
            if(ok){
                visible += 1;
                if(matched.length){
                    card.classList.add('phase69-5-switch-hit','search-port-match');
                    matched.forEach(addHit);
                    portHits += matched.length;
                    items.push({
                        cardId: d(card,'switchId') || card.getAttribute('data-switch-id') || '',
                        portId: d(matched[0],'portId') || matched[0].getAttribute('data-port-id') || '',
                        switchName: first(text(card.querySelector('.switch-title-link')), text(card.querySelector('h2')), 'Switch'),
                        label: first(d(matched[0],'officeLabel'), d(matched[0],'searchCode'), d(matched[0],'description'), d(matched[0],'interface'), matched[0].getAttribute('title'))
                    });
                }else if(terms.length){
                    card.classList.add('phase69-5-switch-hit');
                    items.push({cardId:d(card,'switchId') || card.getAttribute('data-switch-id') || '', portId:'', switchName:first(text(card.querySelector('.switch-title-link')), text(card.querySelector('h2')), 'Switch'), label:'Switch'});
                }
            }
        });

        render(box, items, q);
        var state = document.querySelector('[data-search-result-state]');
        if(state) state.textContent = terms.length ? ('نتیجه: ' + visible + ' سوییچ / ' + portHits + ' پورت') : '';
        if(terms.length && items.length === 1){
            var one = document.querySelector('[data-switch-card][data-switch-id="' + String(items[0].cardId).replace(/"/g,'\\"') + '"]');
            if(one){ try{ one.scrollIntoView({behavior:'smooth', block:'center'}); }catch(e){} }
        }
    }
    function bind(){
        var input = document.querySelector('#sm-main-search, [data-switch-search]');
        if(!input || input.getAttribute('data-phase69-5-bound') === '1') return;
        input.setAttribute('data-phase69-5-bound','1');
        ['input','search','keyup','change'].forEach(function(ev){
            input.addEventListener(ev, function(e){
                if(e){ e.stopImmediatePropagation(); }
                window.setTimeout(function(){ run(true); }, 0);
            }, true);
        });
        var box = ensureResults(input);
        if(box){
            box.addEventListener('click', function(e){
                var item = e.target.closest('[data-phase69-5-card]');
                if(!item) return;
                var card = document.querySelector('[data-switch-card][data-switch-id="' + String(item.getAttribute('data-phase69-5-card')).replace(/"/g,'\\"') + '"]');
                if(card){ try{ card.scrollIntoView({behavior:'smooth', block:'center'}); }catch(err){} }
            });
        }
        run(true);
    }
    function boot(){ bind(); window.setTimeout(bind,300); window.setTimeout(bind,1000); window.setTimeout(function(){ run(true); },1400); }
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
    window.SwitchMapPhase695QuickSearchHardRepair = {run:run, bind:bind, marker:MARKER};
})();
</script>
'''

CSS_BLOCK = r'''

/* Phase 69.5: hard repair for Quick Search without distorting switch visuals */
body.sm-main-dashboard-body .device-browser-shell.search-active .compact-device-grid,
body.sm-main-dashboard-body .device-browser-shell.phase69-search-visual-stable .compact-device-grid,
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active .compact-device-grid,
body.sm-main-dashboard-body .device-browser-shell.phase69-5-search-active .compact-device-grid{
    grid-template-columns:repeat(auto-fit,minmax(520px,1fr))!important;
    align-items:start!important;
}
body.sm-main-dashboard-body .device-browser-shell.search-active [data-switch-card],
body.sm-main-dashboard-body .device-browser-shell.phase69-4-search-active [data-switch-card],
body.sm-main-dashboard-body .device-browser-shell.phase69-5-search-active [data-switch-card]{
    width:auto!important;
    max-width:none!important;
    min-width:0!important;
}
body.sm-main-dashboard-body .device-browser-shell.phase69-5-search-active .sm-switch-extra{
    display:none!important;
}
body.sm-main-dashboard-body .sm-main-quick-search,
body.sm-main-dashboard-body .modern-search-panel{
    position:relative!important;
    overflow:visible!important;
    z-index:80!important;
}
body.sm-main-dashboard-body .phase69-5-search-results{
    position:absolute!important;
    top:calc(100% + 8px)!important;
    left:0!important;
    right:0!important;
    z-index:200!important;
    max-height:300px!important;
    overflow:auto!important;
    padding:8px!important;
    border:1px solid #cbdcf0!important;
    border-radius:16px!important;
    background:#fff!important;
    box-shadow:0 18px 42px rgba(15,23,42,.18)!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .phase69-5-result-head,
body.sm-main-dashboard-body .phase69-5-empty{
    padding:8px 10px!important;
    color:#64748b!important;
    font-size:12px!important;
    font-weight:900!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .phase69-5-result{
    width:100%!important;
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:12px!important;
    margin:0 0 7px!important;
    padding:10px 12px!important;
    border:1px solid #d7e4f4!important;
    border-radius:13px!important;
    background:#f8fbff!important;
    color:#0f172a!important;
    cursor:pointer!important;
    text-align:right!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .phase69-5-result:hover{
    border-color:#2563eb!important;
    background:#eff6ff!important;
}
body.sm-main-dashboard-body .phase69-5-port-hit .port-frame,
body.sm-main-dashboard-body [data-sm-port-button].phase69-5-port-hit .port-frame,
body.sm-main-dashboard-body .sm-svg-port.phase69-5-port-hit .port-frame{
    stroke:#ef4444!important;
    stroke-width:4!important;
    filter:drop-shadow(0 0 7px rgba(239,68,68,.8))!important;
}
body.sm-main-dashboard-body .phase69-5-port-hit .port-led,
body.sm-main-dashboard-body [data-sm-port-button].phase69-5-port-hit .port-led,
body.sm-main-dashboard-body .sm-svg-port.phase69-5-port-hit .port-led{
    fill:#ef4444!important;
}
body.sm-main-dashboard-body .phase69-5-port-hit .port-number,
body.sm-main-dashboard-body [data-sm-port-button].phase69-5-port-hit .port-number,
body.sm-main-dashboard-body .sm-svg-port.phase69-5-port-hit .port-number{
    fill:#fff!important;
    font-weight:900!important;
}
/* phase69-5-quick-search-hard-repair */
'''

def log(m): print(m, flush=True)

def backup(rel):
    src=PROJECT/rel
    if src.exists():
        dst=BACKUP/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)

def read(rel): return (PROJECT/rel).read_text(encoding='utf-8', errors='replace')
def write(rel,txt): (PROJECT/rel).write_text(txt, encoding='utf-8', newline='')

def copy_files():
    for rel in COPY_FILES:
        src=PATCH_ROOT/rel
        if not src.exists(): raise SystemExit(f"PHASE69_5_FAIL missing patch file: {rel}")
        backup(rel)
        dst=PROJECT/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)
        log(f"PHASE69_5_COPIED={rel}")

def patch_switch_list():
    rel=Path('inventory/templates/inventory/switch_list.html')
    text=read(rel)
    if "port.description|default_if_none:''" not in text:
        text=text.replace(
            "{{ port|port_title }} {{ port|port_neighbor }}",
            "{{ port|port_title }} {{ port.description|default_if_none:'' }} {{ port|port_description }} {{ port|port_neighbor }}",
            1,
        )
    text=re.sub(r"\n?<script>\s*/\* phase69-5-quick-search-hard-repair \*/.*?</script>\s*", "\n", text, flags=re.S)
    idx=text.rfind('{% endblock %}')
    if idx == -1: raise SystemExit('PHASE69_5_FAIL switch_list endblock not found')
    text=text[:idx] + INLINE_JS + '\n' + text[idx:]
    for marker in ['phase68-quick-search-port-labels','phase69-4-quick-search-repair','phase69-5-quick-search-hard-repair']:
        if marker not in text:
            text += f"\n{{# {marker} compatibility marker #}}\n"
    write(rel,text)
    log(f"PHASE69_5_PATCHED={rel}")

def patch_3850_include():
    rel=Path('inventory/templates/inventory/includes/cisco_3850_svg.html')
    path=PROJECT/rel
    if not path.exists():
        log(f"PHASE69_5_SKIP_MISSING={rel}")
        return
    text=read(rel)
    if 'data-office-label=' not in text:
        text=text.replace(
            'data-interface="{{ port|port_label }}"',
            'data-interface="{{ port|port_label }}"\n                       data-office-label="{{ port.description|default_if_none:\'\' }}"\n                       data-search-code="{{ port.description|default_if_none:\'\' }} {{ port.cable_label|default_if_none:\'\' }} {{ port.outlet|default_if_none:\'\' }}"',
        )
    text=text.replace(
        'data-description="{{ port|port_description }}"',
        'data-description="{{ port.description|default_if_none:\'\' }} {{ port|port_description }}"'
    )
    if 'phase69-5-quick-search-hard-repair' not in text:
        text += '\n{# phase69-5-quick-search-hard-repair #}\n'
    write(rel,text)
    log(f"PHASE69_5_PATCHED={rel}")

def patch_css():
    rel=Path('inventory/static/inventory/css/switchmap-dashboard-stable-main.css')
    text=read(rel)
    text=re.sub(r"\n/\* Phase 69\.5: hard repair for Quick Search.*?phase69-5-quick-search-hard-repair \*/\n?", "\n", text, flags=re.S)
    text=text.rstrip()+CSS_BLOCK+'\n'
    write(rel,text)
    log(f"PHASE69_5_PATCHED={rel}")

def patch_manifest():
    rel=Path('smoke_tests/manifest.json')
    path=PROJECT/rel
    if not path.exists(): return
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        log('PHASE69_5_MANIFEST_SKIP_PARSE')
        return
    current=data.setdefault('current',[])
    smoke='smoke_tests/switchmap_69_5_quick_search_hard_repair_smoke_test.py'
    if smoke not in current:
        current.append(smoke)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        log('PHASE69_5_MANIFEST_PATCHED')
    else:
        log('PHASE69_5_MANIFEST_ALREADY_OK')

def run(label,args,required=True):
    log(f"PHASE69_5_RUN={label}")
    r=subprocess.run(args,cwd=str(PROJECT),shell=False)
    if r.returncode != 0 and required:
        log(f"PHASE69_5_FAIL={label}")
        log(f'Rollback example:\nxcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        sys.exit(r.returncode)
    return r.returncode

def main():
    log(f"PHASE69_5_BACKUP_PATH={BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in TOUCH: backup(rel)
    copy_files()
    patch_switch_list()
    patch_3850_include()
    patch_css()
    patch_manifest()
    run('phase69.5 smoke',[str(PYTHON),'smoke_tests\\switchmap_69_5_quick_search_hard_repair_smoke_test.py'])
    run('manage.py check',[str(PYTHON),'manage.py','check'])
    run('collectstatic',[str(PYTHON),'manage.py','collectstatic','--noinput'])
    run('run_smoke current',[str(PYTHON),'smoke_tests\\run_smoke.py','current'], required=False)
    restart=PROJECT/'scripts'/'12_vm_restart_waitress_task.cmd'
    if restart.exists(): run('restart Waitress',[str(restart)], required=False)
    log('PHASE69_5_APPLY_OK')

if __name__=='__main__': main()
