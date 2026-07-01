from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / "backups" / ("phase79_3_ssh_refresh_last_connected_ui_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
FILES = {
    "js": ROOT / "inventory" / "static" / "inventory" / "switchmap.js",
    "css": ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase79.css",
    "base": ROOT / "inventory" / "templates" / "inventory" / "base.html",
    "switch_list": ROOT / "inventory" / "templates" / "inventory" / "switch_list.html",
    "switch_detail": ROOT / "inventory" / "templates" / "inventory" / "switch_detail.html",
}
VERSION = "phase79-3-ssh-refresh-last-connected-v3"

SET_LAST_CONNECTION_V3 = r'''    function setLastConnection(root, attrName, last){
        // Phase79.3 - stable Last Connected Device renderer
        if(!root) return;
        const prefix = '[' + attrName + '="';
        const suffix = '"]';
        const box = root.querySelector('[data-phase79-last-connected]');
        function clean(v){
            const s = String(v === 0 ? '0' : (v || '')).trim();
            if(!s) return '';
            const low = s.toLowerCase();
            if(s === '-' || low === 'none' || low === 'null' || low === 'unknown') return '';
            if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return '';
            return s;
        }
        function esc(v){
            return String(v || '').replace(/[&<>"']/g, function(ch){
                return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
            });
        }
        const identity = clean(last && last.identity);
        const available = !!(last && last.available && identity);
        setText(root, prefix + 'last_connection_event_type' + suffix, available ? historyValue(last.event_type) : '-');
        if(!box){
            setText(root, prefix + 'last_connection_identity' + suffix, available ? identity : 'سابقه‌ای ثبت نشده');
            return;
        }
        box.classList.remove('is-current','is-history');
        if(!available){
            box.classList.add('is-empty');
            box.innerHTML = '<div class="phase79-lc-v3-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        box.classList.remove('is-empty');
        if(String(last.event_type || '').toLowerCase().indexOf('current') !== -1) box.classList.add('is-current');
        else box.classList.add('is-history');
        const details = [];
        function add(label, value){
            const v = clean(value);
            if(!v) return;
            if(label === 'Identity') return;
            details.push('<div class="phase79-lc-v3-item"><span>' + esc(label) + '</span><strong title="' + esc(v) + '">' + esc(v) + '</strong></div>');
        }
        add('Seen', last.observed_at_text);
        add('Neighbor', last.neighbor);
        add('MAC', last.mac);
        add('IP', last.ip);
        add('VLAN', last.vlan);
        add('Status', last.status_after);
        add('Source', last.source);
        const eventType = clean(last.event_type);
        box.innerHTML = '' +
            '<div class="phase79-lc-v3-head">' +
                '<span>' + esc(eventType || 'Last Connected') + '</span>' +
                '<strong title="' + esc(identity) + '">' + esc(identity) + '</strong>' +
            '</div>' +
            (details.length ? '<div class="phase79-lc-v3-grid">' + details.join('') + '</div>' : '');
    }
'''

REFRESH_AFTER_SSH_FUNCTION = r'''    function refreshSelectedPortAfterSsh(form, initialData){
        // Phase79.3 - after SSH, fetch fresh port payload without closing popup.
        const port = initialData && initialData.port ? initialData.port : null;
        const portId = (port && port.id) ? port.id : formValue(form, 'port_id');
        if(!portId) return;
        window.setTimeout(function(){
            fetch('/port/' + encodeURIComponent(portId) + '/payload/', {
                credentials:'same-origin',
                headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
            }).then(function(response){
                return response.json().catch(function(){return null;});
            }).then(function(data){
                if(data && data.ok && data.port){
                    applyCurrentUpdate(data);
                    setResult(form,true,'عملیات موفق بود؛ اطلاعات پورت به‌روزرسانی شد.');
                }else{
                    setResult(form,true,'عملیات موفق بود؛ دریافت وضعیت جدید پورت کامل نشد.');
                }
            }).catch(function(){
                setResult(form,true,'عملیات موفق بود؛ به‌روزرسانی خودکار پورت انجام نشد.');
            });
        }, 1200);
    }
'''

CSS_APPEND = r'''

/* Phase79.3 - stable compact Last Connected Device panel */
[data-phase79-last-connected] {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 8px 0 10px 0 !important;
    padding: 10px !important;
    border: 1px solid rgba(203, 213, 225, .95) !important;
    border-radius: 13px !important;
    background: #ffffff !important;
    box-shadow: none !important;
    min-height: 0 !important;
    max-height: 148px !important;
    overflow: auto !important;
    direction: ltr !important;
}
[data-phase79-last-connected].is-empty {
    background: #f8fafc !important;
    border-style: dashed !important;
    max-height: none !important;
    overflow: visible !important;
}
.phase79-lc-v3-empty {
    display: block !important;
    padding: 9px 10px !important;
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    line-height: 1.8 !important;
    text-align: right !important;
    direction: rtl !important;
}
.phase79-lc-v3-head {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 12px !important;
    padding: 8px 10px !important;
    margin-bottom: 8px !important;
    border: 1px solid rgba(191, 219, 254, .95) !important;
    border-radius: 10px !important;
    background: #eff6ff !important;
    direction: ltr !important;
}
.phase79-lc-v3-head span {
    display: inline-block !important;
    flex: 0 0 auto !important;
    color: #2563eb !important;
    font-size: 10px !important;
    font-weight: 900 !important;
    letter-spacing: .02em !important;
    white-space: nowrap !important;
    direction: ltr !important;
}
.phase79-lc-v3-head strong {
    display: block !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
    color: #0f172a !important;
    font-size: 13px !important;
    font-weight: 950 !important;
    line-height: 1.25 !important;
    text-align: right !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.phase79-lc-v3-grid {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 6px !important;
    direction: ltr !important;
}
.phase79-lc-v3-item {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 8px !important;
    min-width: 0 !important;
    padding: 6px 8px !important;
    border: 1px solid rgba(226, 232, 240, .95) !important;
    border-radius: 9px !important;
    background: #f8fafc !important;
    direction: ltr !important;
}
.phase79-lc-v3-item span {
    display: inline-block !important;
    flex: 0 0 auto !important;
    color: #64748b !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    white-space: nowrap !important;
    direction: ltr !important;
}
.phase79-lc-v3-item strong {
    display: block !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
    color: #0f172a !important;
    font-size: 11px !important;
    font-weight: 900 !important;
    text-align: right !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
@media (max-width: 900px) {
    .phase79-lc-v3-grid { grid-template-columns: 1fr !important; }
}
'''


def backup(path: Path) -> None:
    if path.exists():
        dst = BACKUP_ROOT / path.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    backup(path)
    path.write_text(text, encoding="utf-8")


def patch_js() -> None:
    path = FILES["js"]
    text = read(path)
    pattern = re.compile(r"    function setLastConnection\(root, attrName, last\)\{.*?\n    \}\n    function refreshLastConnectionFromPayload", re.S)
    text, count = pattern.subn(lambda m: SET_LAST_CONNECTION_V3 + "    function refreshLastConnectionFromPayload", text, count=1)
    if count != 1:
        raise RuntimeError("switchmap.js: setLastConnection block not found")
    if "function refreshSelectedPortAfterSsh(" not in text:
        marker = "    function submitSshForm(form){"
        if marker not in text:
            raise RuntimeError("switchmap.js: submitSshForm marker not found")
        text = text.replace(marker, REFRESH_AFTER_SSH_FUNCTION + marker, 1)
    old = """                applyCurrentUpdate(result.data);
                setResult(form,true,'عملیات موفق بود.');
                previewCommands(form);"""
    new = """                applyCurrentUpdate(result.data);
                setResult(form,true,'عملیات موفق بود؛ در حال به‌روزرسانی پورت ...');
                refreshSelectedPortAfterSsh(form, result.data);
                previewCommands(form);"""
    if old in text:
        text = text.replace(old, new, 1)
    elif "refreshSelectedPortAfterSsh(form, result.data);" not in text:
        raise RuntimeError("switchmap.js: SSH success block not found")
    write(path, text)


def patch_css() -> None:
    path = FILES["css"]
    text = read(path) if path.exists() else ""
    if "Phase79.3 - stable compact Last Connected Device panel" not in text:
        text = text.rstrip() + CSS_APPEND + "\n"
    write(path, text)


def patch_base() -> None:
    path = FILES["base"]
    text = read(path)
    if "switchmap-phase79.css" not in text:
        raise RuntimeError("base.html: switchmap-phase79.css include not found")
    lines = []
    changed = False
    for line in text.splitlines():
        if "switchmap-phase79.css" in line:
            if "?v=" in line:
                line = re.sub(r"\?v=[^\"']+", "?v=" + VERSION, line)
            else:
                line = line.replace("switchmap-phase79.css", "switchmap-phase79.css?v=" + VERSION)
            changed = True
        lines.append(line)
    if not changed:
        raise RuntimeError("base.html: phase79 css version not changed")
    write(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def patch_templates() -> None:
    for key in ("switch_list", "switch_detail"):
        path = FILES[key]
        text = read(path)
        text2 = text.replace('class="key-grid compact-grid port-main-grid phase79-last-connected" data-phase79-last-connected', 'class="phase79-last-connected" data-phase79-last-connected')
        if text2 != text:
            write(path, text2)


def collectstatic_best_effort() -> None:
    manage = ROOT / "manage.py"
    if not manage.exists():
        return
    try:
        subprocess.run([sys.executable, str(manage), "collectstatic", "--noinput"], cwd=str(ROOT), timeout=90, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_js()
    patch_css()
    patch_base()
    patch_templates()
    collectstatic_best_effort()
    print(f"PHASE79_3_PATCH_OK backup_dir={BACKUP_ROOT}")


if __name__ == "__main__":
    main()
