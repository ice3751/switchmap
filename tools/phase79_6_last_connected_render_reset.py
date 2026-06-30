from __future__ import annotations
from pathlib import Path
import datetime as _dt
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAMP = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_DIR = ROOT / 'backups' / f'phase79_6_last_connected_render_reset_{STAMP}'

FILES = [
    ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_list.html',
    ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_detail.html',
    ROOT / 'inventory' / 'templates' / 'inventory' / 'base.html',
    ROOT / 'inventory' / 'static' / 'inventory' / 'switchmap.js',
    ROOT / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-phase79.css',
]

EMPTY_MSG = 'سابقه اتصال واقعی برای این پورت ثبت نشده است.'


def read(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='ignore')


def write(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding='utf-8', newline='')


def backup_files() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for p in FILES:
        if p.exists():
            rel = p.relative_to(ROOT)
            dst = BACKUP_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)


def replace_last_connected_block(p: Path, attr_name: str) -> None:
    txt = read(p)
    pattern = re.compile(
        r'''<div\s+class="port-modal-section-title\s+compact-title\s+phase79-last-connected-title">.*?</div>\s*\n\s*<div\s+class="phase79-last-connected-panel\s+is-empty"\s+data-phase79-last-connected>.*?</div>''',
        re.S | re.I,
    )
    replacement = f'''<div class="phase79-lc-card" data-phase79-lc-card>
                    <div class="phase79-lc-head">
                        <strong>Last Connected Device</strong>
                        <small {attr_name}="last_connection_event_type">-</small>
                    </div>
                    <div class="phase79-lc-body is-empty" data-phase79-last-connected>
                        <div class="phase79-lc-empty">{EMPTY_MSG}</div>
                    </div>
                </div>'''
    new, count = pattern.subn(replacement, txt, count=1)
    if count != 1:
        raise RuntimeError(f'could not replace Last Connected block in {p}')
    write(p, new)


def patch_base_version() -> None:
    p = ROOT / 'inventory' / 'templates' / 'inventory' / 'base.html'
    txt = read(p)
    new = re.sub(
        r"inventory/switchmap\.js'\s*%\}\?v=[^\"']+",
        "inventory/switchmap.js' %}?v=phase79-6-last-connected-render-reset",
        txt,
        count=1,
    )
    if new == txt:
        raise RuntimeError('switchmap.js version marker not updated in base.html')
    write(p, new)


def patch_js() -> None:
    p = ROOT / 'inventory' / 'static' / 'inventory' / 'switchmap.js'
    txt = read(p)
    marker = '// PHASE79_6_LAST_CONNECTED_RENDER_RESET'
    new_func = r'''function setLastConnection(root, attrName, last){
        // PHASE79_6_LAST_CONNECTED_RENDER_RESET
        last = last || {};
        const box = root.querySelector('[data-phase79-last-connected]');
        const typeEl = root.querySelector('[' + attrName + '="last_connection_event_type"]');
        const eventType = last.event_type || '';
        if(typeEl){ typeEl.textContent = eventType || '-'; }
        if(!box) return;

        const real = hasMeaningfulLastConnection(last);
        box.className = 'phase79-lc-body ' + (real ? 'is-available' : 'is-empty');
        if(!real){
            box.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }

        const rows = [];
        const add = function(label, value, ltr){
            const v = (value || '').toString().trim();
            if(!v || v === '-') return;
            rows.push('<div class="phase79-lc-row"><span class="phase79-lc-label">' + esc(label) + '</span><strong class="phase79-lc-value ' + (ltr ? 'ltr' : '') + '" title="' + esc(v) + '">' + esc(v) + '</strong></div>');
        };
        add('Identity', last.identity || last.neighbor || last.mac || last.ip, true);
        add('Neighbor', last.neighbor, true);
        add('MAC', last.mac, true);
        add('IP', last.ip, true);
        add('Source', last.source, false);
        add('Seen', last.observed_at_text, true);

        if(!rows.length){
            box.className = 'phase79-lc-body is-empty';
            box.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        box.innerHTML = '<div class="phase79-lc-list">' + rows.join('') + '</div>';
    }

    '''
    pattern = re.compile(r"function\s+setLastConnection\(root,\s*attrName,\s*last\)\s*\{.*?\n\s*function\s+refreshLastConnectionFromPayload", re.S)
    new, count = pattern.subn(new_func + 'function refreshLastConnectionFromPayload', txt, count=1)
    if count != 1:
        raise RuntimeError('could not replace setLastConnection() in switchmap.js')
    write(p, new)


def patch_css() -> None:
    p = ROOT / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-phase79.css'
    txt = read(p) if p.exists() else ''
    marker = '/* PHASE79_6_LAST_CONNECTED_RENDER_RESET */'
    block = r'''
/* PHASE79_6_LAST_CONNECTED_RENDER_RESET */
.phase79-lc-card{
    margin-top:12px !important;
    padding-top:10px !important;
    border-top:1px solid #dbe6f3 !important;
    clear:both !important;
    display:block !important;
    width:100% !important;
}
.phase79-lc-head{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:10px !important;
    margin-bottom:8px !important;
    direction:ltr !important;
}
.phase79-lc-head strong{
    font-size:13px !important;
    color:#0f172a !important;
    font-weight:800 !important;
}
.phase79-lc-head small{
    display:inline-flex !important;
    align-items:center !important;
    justify-content:center !important;
    min-width:62px !important;
    max-width:none !important;
    height:24px !important;
    padding:0 10px !important;
    border-radius:999px !important;
    background:#eef6ff !important;
    color:#1d4ed8 !important;
    font-size:11px !important;
    font-weight:800 !important;
    line-height:1 !important;
}
.phase79-lc-body{
    display:block !important;
    width:100% !important;
    min-height:0 !important;
    max-height:none !important;
    overflow:visible !important;
    margin:0 !important;
    padding:10px 12px !important;
    border:1px solid #cfe0f4 !important;
    border-radius:12px !important;
    background:#ffffff !important;
    box-sizing:border-box !important;
    direction:rtl !important;
}
.phase79-lc-body.is-empty{
    background:#f8fafc !important;
    border-style:dashed !important;
}
.phase79-lc-empty{
    display:block !important;
    padding:2px 0 !important;
    margin:0 !important;
    color:#64748b !important;
    font-size:12px !important;
    font-weight:700 !important;
    text-align:right !important;
    white-space:normal !important;
}
.phase79-lc-list{
    display:grid !important;
    grid-template-columns:1fr !important;
    gap:0 !important;
    margin:0 !important;
    padding:0 !important;
    width:100% !important;
    max-height:none !important;
    overflow:visible !important;
}
.phase79-lc-row{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:14px !important;
    min-height:26px !important;
    padding:5px 0 !important;
    margin:0 !important;
    border-bottom:1px solid #edf2f7 !important;
    background:transparent !important;
    box-shadow:none !important;
}
.phase79-lc-row:last-child{border-bottom:0 !important;}
.phase79-lc-label{
    flex:0 0 auto !important;
    color:#64748b !important;
    font-size:11px !important;
    font-weight:800 !important;
    line-height:1.2 !important;
}
.phase79-lc-value{
    flex:1 1 auto !important;
    min-width:0 !important;
    text-align:left !important;
    direction:ltr !important;
    color:#0f172a !important;
    font-size:12px !important;
    font-weight:900 !important;
    line-height:1.35 !important;
    white-space:normal !important;
    overflow-wrap:anywhere !important;
}
.phase79-last-connected-title,
.phase79-last-connected-panel,
.phase79-last-connected-list,
.phase79-last-connected-row,
.phase79-last-connected-message{
    max-height:none !important;
    overflow:visible !important;
}
'''
    if marker in txt:
        txt = txt[:txt.index(marker)].rstrip() + '\n' + block.lstrip()
    else:
        txt = txt.rstrip() + '\n\n' + block.lstrip()
    write(p, txt)


def run_check() -> None:
    subprocess.check_call([sys.executable, 'manage.py', 'check'], cwd=str(ROOT))


def sync_static_if_exists() -> None:
    src_js = ROOT / 'inventory' / 'static' / 'inventory' / 'switchmap.js'
    src_css = ROOT / 'inventory' / 'static' / 'inventory' / 'css' / 'switchmap-phase79.css'
    for dst in [
        ROOT / 'staticfiles' / 'inventory' / 'switchmap.js',
        ROOT / 'inventory' / 'staticfiles' / 'inventory' / 'switchmap.js',
    ]:
        if dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_js, dst)
    for dst in [
        ROOT / 'staticfiles' / 'inventory' / 'css' / 'switchmap-phase79.css',
        ROOT / 'inventory' / 'staticfiles' / 'inventory' / 'css' / 'switchmap-phase79.css',
    ]:
        if dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_css, dst)


def main() -> int:
    backup_files()
    replace_last_connected_block(ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_list.html', 'data-field')
    replace_last_connected_block(ROOT / 'inventory' / 'templates' / 'inventory' / 'switch_detail.html', 'data-detail')
    patch_js()
    patch_css()
    patch_base_version()
    sync_static_if_exists()
    run_check()
    print(f'PHASE79_6_PATCH_OK backup_dir={BACKUP_DIR}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
