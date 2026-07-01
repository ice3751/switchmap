from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_DIR = ROOT / 'backups' / f'phase79_6_1_last_connected_actual_reset_{STAMP}'

SWITCH_LIST = ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_list.html'
SWITCH_DETAIL = ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_detail.html'
JS_STATIC = ROOT / 'inventory' / 'static' / 'inventory' / 'switchmap.js'
JS_STATICFILES = ROOT / 'inventory' / 'staticfiles' / 'inventory' / 'switchmap.js'
CSS = ROOT / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-phase79.css'
CSS_STATICFILES = ROOT / 'inventory' / 'staticfiles' / 'inventory' / 'css' / 'switchmap-phase79.css'
BASE = ROOT / 'inventory' / 'templates' / 'inventory' / 'base.html'

PANEL_TEMPLATE = '''
                <div class="phase79-last-connected-wrap" data-phase79-last-connected-wrap>
                    <div class="phase79-last-connected-head">
                        <span>Last Connected Device</span>
                        <small data-{attr}="last_connection_event_type">-</small>
                    </div>
                    <div class="phase79-last-connected-panel is-empty" data-phase79-last-connected>
                        <div class="phase79-last-connected-message">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>
                    </div>
                </div>
'''

CSS_BLOCK = r'''

/* PHASE79_6_1_LAST_CONNECTED_ACTUAL_RESET */
.phase79-last-connected-wrap{
  margin:12px 0 10px !important;
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
  overflow:visible !important;
  direction:rtl !important;
}
.phase79-last-connected-head{
  display:flex !important;
  align-items:center !important;
  justify-content:space-between !important;
  gap:10px !important;
  margin:0 0 8px !important;
  padding:0 !important;
  border:0 !important;
  min-height:auto !important;
}
.phase79-last-connected-head span{
  display:inline-flex !important;
  font-size:13px !important;
  font-weight:900 !important;
  color:#0f172a !important;
  line-height:1.4 !important;
}
.phase79-last-connected-head small{
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  padding:3px 9px !important;
  border-radius:999px !important;
  background:#eaf2ff !important;
  color:#1d4ed8 !important;
  font-size:11px !important;
  font-weight:800 !important;
  line-height:1.2 !important;
}
.phase79-last-connected-panel,
.phase79-last-connected-panel.is-available,
.phase79-last-connected-panel.is-empty{
  display:block !important;
  width:100% !important;
  min-height:0 !important;
  max-height:none !important;
  height:auto !important;
  margin:0 !important;
  padding:10px 12px !important;
  border:1px solid #d8e5f5 !important;
  border-radius:14px !important;
  background:#ffffff !important;
  overflow:visible !important;
  box-shadow:none !important;
  direction:rtl !important;
}
.phase79-last-connected-panel.is-empty{
  background:#f8fafc !important;
  border-style:dashed !important;
}
.phase79-last-connected-message{
  display:block !important;
  margin:0 !important;
  padding:0 !important;
  color:#64748b !important;
  font-size:12px !important;
  font-weight:700 !important;
  line-height:1.8 !important;
  text-align:right !important;
  white-space:normal !important;
}
.phase79-last-connected-single{
  display:flex !important;
  align-items:center !important;
  justify-content:space-between !important;
  gap:12px !important;
  margin:0 !important;
  padding:0 !important;
  min-height:28px !important;
  background:transparent !important;
  border:0 !important;
  overflow:visible !important;
}
.phase79-last-connected-identity{
  display:block !important;
  flex:1 1 auto !important;
  min-width:0 !important;
  color:#0f172a !important;
  font-size:13px !important;
  font-weight:900 !important;
  line-height:1.6 !important;
  text-align:left !important;
  direction:ltr !important;
  white-space:normal !important;
  word-break:break-word !important;
}
.phase79-last-connected-meta{
  display:inline-flex !important;
  flex:0 0 auto !important;
  color:#64748b !important;
  font-size:11px !important;
  font-weight:800 !important;
  line-height:1.4 !important;
  text-align:right !important;
  direction:rtl !important;
}
.phase79-last-connected-extra{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:6px !important;
  margin:8px 0 0 !important;
  padding:0 !important;
}
.phase79-last-connected-extra span{
  display:inline-flex !important;
  align-items:center !important;
  max-width:100% !important;
  padding:3px 8px !important;
  border-radius:999px !important;
  background:#f1f5f9 !important;
  color:#334155 !important;
  font-size:11px !important;
  font-weight:800 !important;
  direction:ltr !important;
  white-space:normal !important;
  word-break:break-word !important;
}
.phase79-last-connected-panel .key-grid,
.phase79-last-connected-panel .compact-grid,
.phase79-last-connected-panel .key-item,
.phase79-last-connected-panel .phase79-last-connected-row,
.phase79-last-connected-panel .phase79-last-connected-list{
  display:contents !important;
  margin:0 !important;
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
  box-shadow:none !important;
}
'''

SET_LAST_CONNECTION = r'''
    function setLastConnection(root, attrName, last){
        const box = root.querySelector('[data-phase79-last-connected]');
        const eventNode = root.querySelector('[' + attrName + '="last_connection_event_type"]');
        if(!box) return;
        const rawIdentity = (last && last.identity ? String(last.identity).trim() : '');
        const neighbor = (last && last.neighbor ? String(last.neighbor).trim() : '');
        const mac = (last && last.mac ? String(last.mac).trim() : '');
        const ip = (last && last.ip ? String(last.ip).trim() : '');
        const source = (last && last.source ? String(last.source).trim() : '');
        const eventType = (last && last.event_type ? String(last.event_type).trim() : '');
        const observed = (last && last.observed_at_text ? String(last.observed_at_text).trim() : '');
        const identity = rawIdentity || neighbor || mac || ip;
        const hasReal = Boolean(identity || neighbor || mac || ip);
        if(eventNode){
            eventNode.textContent = hasReal ? (eventType || source || '-') : '-';
        }
        if(!hasReal){
            box.className = 'phase79-last-connected-panel is-empty';
            box.innerHTML = '<div class="phase79-last-connected-message">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        box.className = 'phase79-last-connected-panel is-available';
        const extras = [];
        if(neighbor && neighbor !== identity) extras.push('Neighbor: ' + neighbor);
        if(mac) extras.push('MAC: ' + mac);
        if(ip) extras.push('IP: ' + ip);
        if(source) extras.push('Source: ' + source);
        if(observed) extras.push('Seen: ' + observed);
        const extraHtml = extras.length ? '<div class="phase79-last-connected-extra">' + extras.map(function(x){ return '<span>' + esc(x) + '</span>'; }).join('') + '</div>' : '';
        box.innerHTML = '<div class="phase79-last-connected-single"><strong class="phase79-last-connected-identity" title="' + esc(identity) + '">' + esc(identity) + '</strong><span class="phase79-last-connected-meta">' + esc(eventType || source || 'Current') + '</span></div>' + extraHtml;
    }
'''


def read(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='ignore')


def write(p: Path, txt: str) -> None:
    p.write_text(txt, encoding='utf-8', newline='')


def backup(paths):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for p in paths:
        if p.exists():
            rel = p.relative_to(ROOT)
            dest = BACKUP_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)


def replace_template_block(p: Path, attr: str) -> bool:
    txt = read(p)
    start = txt.find('<div class="port-modal-section-title compact-title phase79-last-connected-title">')
    if start < 0:
        start = txt.find('<div class="phase79-last-connected-wrap" data-phase79-last-connected-wrap>')
    if start < 0:
        raise RuntimeError(f'last-connected start not found: {p}')
    end = txt.find('<div class="port-refresh-box', start)
    if end < 0:
        raise RuntimeError(f'port-refresh-box not found after last-connected block: {p}')
    new = txt[:start] + PANEL_TEMPLATE.format(attr=attr) + txt[end:]
    if new != txt:
        write(p, new)
        return True
    return False


def replace_js_function(p: Path) -> bool:
    if not p.exists():
        return False
    txt = read(p)
    pattern = re.compile(r"\n\s*function\s+setLastConnection\s*\([^)]*\)\s*\{.*?\n\s*\}\s*\n\s*function\s+refreshLastConnectionFromPayload", re.S)
    m = pattern.search(txt)
    if not m:
        raise RuntimeError(f'setLastConnection function block not found: {p}')
    repl = '\n' + SET_LAST_CONNECTION.rstrip() + '\n    function refreshLastConnectionFromPayload'
    new = txt[:m.start()] + repl + txt[m.end():]
    if new != txt:
        write(p, new)
        return True
    return False


def append_css(p: Path) -> bool:
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        write(p, CSS_BLOCK)
        return True
    txt = read(p)
    marker = 'PHASE79_6_1_LAST_CONNECTED_ACTUAL_RESET'
    if marker in txt:
        # replace existing marker block onwards to keep it single and final
        txt = txt.split('/* ' + marker + ' */')[0].rstrip() + CSS_BLOCK
    else:
        txt = txt.rstrip() + CSS_BLOCK
    write(p, txt)
    return True


def update_base_version() -> bool:
    if not BASE.exists():
        return False
    txt = read(BASE)
    new = re.sub(r"switchmap\.js' %\}\?v=[^\"']+", "switchmap.js' %}?v=phase79-6-1-last-connected-actual-reset", txt)
    new = re.sub(r"switchmap-phase79\.css' %\}\?v=[^\"']+", "switchmap-phase79.css' %}?v=phase79-6-1-last-connected-actual-reset", new)
    if new != txt:
        write(BASE, new)
        return True
    return False


def verify() -> tuple[int, int, int]:
    ok = warn = fail = 0
    def OK(msg):
        nonlocal ok; ok += 1; print('OK', msg)
    def FAIL(msg):
        nonlocal fail; fail += 1; print('FAIL', msg)

    for p in [SWITCH_LIST, SWITCH_DETAIL]:
        txt = read(p)
        if 'phase79-last-connected-wrap' in txt and 'phase79-last-connected-title' not in txt:
            OK(f'template:{p.name}:new_block')
        else:
            FAIL(f'template:{p.name}:old_block_still_present')
        if 'key-grid compact-grid' in txt[txt.find('phase79-last-connected'): txt.find('port-refresh-box', txt.find('phase79-last-connected'))]:
            FAIL(f'template:{p.name}:key_grid_inside_last_connected')
        else:
            OK(f'template:{p.name}:no_key_grid_inside_last_connected')

    for p in [JS_STATIC, JS_STATICFILES]:
        if p.exists():
            txt = read(p)
            if 'phase79-last-connected-single' in txt and 'سابقه اتصال واقعی' in txt:
                OK(f'js:{p}:new_renderer')
            else:
                FAIL(f'js:{p}:renderer_marker_missing')

    for p in [CSS, CSS_STATICFILES]:
        if p.exists():
            txt = read(p)
            if 'PHASE79_6_1_LAST_CONNECTED_ACTUAL_RESET' in txt:
                OK(f'css:{p}:marker')
            else:
                FAIL(f'css:{p}:marker_missing')

    return ok, warn, fail


def main() -> int:
    paths = [SWITCH_LIST, SWITCH_DETAIL, JS_STATIC, JS_STATICFILES, CSS, CSS_STATICFILES, BASE]
    backup(paths)
    changes = []
    changes.append(('switch_list_template', replace_template_block(SWITCH_LIST, 'field')))
    changes.append(('switch_detail_template', replace_template_block(SWITCH_DETAIL, 'detail')))
    changes.append(('switchmap_js_static', replace_js_function(JS_STATIC)))
    if JS_STATICFILES.exists():
        changes.append(('switchmap_js_staticfiles', replace_js_function(JS_STATICFILES)))
    changes.append(('css_static', append_css(CSS)))
    if CSS_STATICFILES.exists():
        changes.append(('css_staticfiles', append_css(CSS_STATICFILES)))
    changes.append(('base_version', update_base_version()))

    print(f'PHASE79_6_1_PATCH_OK backup_dir={BACKUP_DIR}')
    for name, changed in changes:
        print(f'PATCH {name}={"changed" if changed else "unchanged"}')
    ok, warn, fail = verify()
    print('PHASE79_6_1_LAST_CONNECTED_ACTUAL_RESET_REPORT')
    print(f'OK_COUNT={ok}')
    print(f'WARNING_COUNT={warn}')
    print(f'FAIL_COUNT={fail}')
    if fail:
        print('PHASE79_6_1_VERIFY_FAIL')
        return 1
    print('PHASE79_6_1_VERIFY_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
