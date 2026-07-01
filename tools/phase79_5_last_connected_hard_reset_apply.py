from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "phase79-5-last-connected-hard-reset"
BACKUP_ROOT = ROOT / "backups" / ("phase79_5_last_connected_hard_reset_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
FILES = {
    "base": ROOT / "inventory" / "templates" / "inventory" / "base.html",
    "switch_list": ROOT / "inventory" / "templates" / "inventory" / "switch_list.html",
    "switch_detail": ROOT / "inventory" / "templates" / "inventory" / "switch_detail.html",
    "js": ROOT / "inventory" / "static" / "inventory" / "switchmap.js",
    "css": ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase79.css",
}

LC_BOX = '''<div class="phase79-last-connected-panel is-empty" data-phase79-last-connected>
                    <div class="phase79-last-connected-message">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>
                </div>'''
LC_BOX_DETAIL = '''<div class="phase79-last-connected-panel is-empty" data-phase79-last-connected>
                <div class="phase79-last-connected-message">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>
            </div>'''

CSS = r'''/* Phase79.5 - hard reset Last Connected Device UI */
.phase79-last-connected-title {
    margin-top: 12px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 10px !important;
}
.phase79-last-connected-title small {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 20px !important;
    padding: 2px 8px !important;
    border-radius: 999px !important;
    background: #eef6ff !important;
    color: #1d4ed8 !important;
    font-size: 10px !important;
    font-weight: 900 !important;
    line-height: 1 !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
}
[data-phase79-last-connected],
.phase79-last-connected-panel[data-phase79-last-connected] {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 8px 0 10px 0 !important;
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
    box-shadow: none !important;
    direction: rtl !important;
}
[data-phase79-last-connected]::before,
[data-phase79-last-connected]::after,
.phase79-last-connected-panel::before,
.phase79-last-connected-panel::after {
    content: none !important;
    display: none !important;
}
[data-phase79-last-connected] .key-item,
[data-phase79-last-connected] .phase79-lc-row,
[data-phase79-last-connected] .phase79-lc-clean-row,
[data-phase79-last-connected] .phase79-lc-final-row,
[data-phase79-last-connected] .phase79-lc-empty,
[data-phase79-last-connected] .phase79-lc-final-empty {
    display: none !important;
}
.phase79-last-connected-message {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 0 !important;
    padding: 10px 12px !important;
    border: 1px dashed #cbd5e1 !important;
    border-radius: 12px !important;
    background: #f8fafc !important;
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 900 !important;
    line-height: 1.8 !important;
    text-align: right !important;
    direction: rtl !important;
}
.phase79-last-connected-list {
    display: grid !important;
    grid-template-columns: 1fr !important;
    gap: 6px !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 0 !important;
    padding: 8px !important;
    border: 1px solid #dbeafe !important;
    border-radius: 12px !important;
    background: #f8fbff !important;
}
.phase79-last-connected-row {
    display: grid !important;
    grid-template-columns: 120px minmax(0, 1fr) !important;
    align-items: center !important;
    gap: 10px !important;
    min-height: 28px !important;
    padding: 6px 8px !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
    direction: ltr !important;
}
.phase79-last-connected-label {
    display: block !important;
    color: #64748b !important;
    font-size: 10px !important;
    font-weight: 900 !important;
    line-height: 1.2 !important;
    text-align: left !important;
    white-space: nowrap !important;
    direction: ltr !important;
}
.phase79-last-connected-value {
    display: block !important;
    min-width: 0 !important;
    color: #0f172a !important;
    font-size: 12px !important;
    font-weight: 950 !important;
    line-height: 1.35 !important;
    text-align: right !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
}
'''

EFFECTIVE_FUNC = r'''    function effectiveLastConnectionFromDataset(d){
        // Phase79.5 - current visible port evidence first; history only as fallback.
        function clean(v){
            const s = String(v === 0 ? '0' : (v || '')).trim();
            if(!s) return '';
            const low = s.toLowerCase();
            if(s === '-' || low === 'none' || low === 'null' || low === 'unknown' || low === 'undefined') return '';
            if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return '';
            return s;
        }
        const neighborDevice = clean(d.neighborDevice);
        const neighborPort = clean(d.neighborPort);
        const neighbor = [neighborDevice, neighborPort].filter(Boolean).join(' / ');
        const device = clean(d.device);
        const mac = clean(d.macAddress);
        const ip = clean(d.ipAddress);
        const identity = neighbor || device || mac || ip;
        if(identity){
            return {
                available: true,
                identity: identity,
                event_type: String(d.status || '').toLowerCase() === 'up' ? 'Current' : 'Last known',
                observed_at_text: clean(d.discoveryLastPoll) || clean(d.snmpLastPoll) || clean(d.updatedAt) || '',
                neighbor: neighbor,
                neighbor_source: clean(d.neighborSource),
                source: clean(d.neighborSource) || 'current-db',
                mac: mac,
                ip: ip,
                vlan: clean(d.accessVlan) || clean(d.vlan),
                status_after: clean(d.status)
            };
        }
        const last = lastConnectionFromDataset(d);
        if(hasMeaningfulLastConnection(last)) return last;
        return {available:false, identity:'', event_type:'', observed_at_text:'', neighbor:'', source:'', mac:'', ip:'', vlan:'', status_after:''};
    }
'''

SET_FUNC = r'''    function setLastConnection(root, attrName, last){
        // Phase79.5 - hard reset renderer; no legacy key-grid/old pseudo elements.
        if(!root) return;
        const prefix = '[' + attrName + '="';
        const suffix = '"]';
        const box = root.querySelector('[data-phase79-last-connected]');
        function clean(v){
            const s = String(v === 0 ? '0' : (v || '')).trim();
            if(!s) return '';
            const low = s.toLowerCase();
            if(s === '-' || low === 'none' || low === 'null' || low === 'unknown' || low === 'undefined') return '';
            if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return '';
            return s;
        }
        function esc(v){
            return String(v || '').replace(/[&<>"']/g, function(ch){
                return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
            });
        }
        function row(label, value){
            const v = clean(value);
            if(!v) return '';
            return '<div class="phase79-last-connected-row"><span class="phase79-last-connected-label">' + esc(label) + '</span><strong class="phase79-last-connected-value" title="' + esc(v) + '">' + esc(v) + '</strong></div>';
        }
        const identity = clean(last && last.identity);
        const hasReal = !!(last && last.available && identity);
        setText(root, prefix + 'last_connection_event_type' + suffix, hasReal ? (clean(last.event_type) || 'Last known') : '-');
        if(!box) return;
        box.className = 'phase79-last-connected-panel ' + (hasReal ? 'is-available' : 'is-empty');
        box.removeAttribute('style');
        if(!hasReal){
            box.innerHTML = '<div class="phase79-last-connected-message">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        const rows = [
            row('Identity', identity),
            row('Type', clean(last.event_type) || 'Last known'),
            row('Neighbor', last.neighbor),
            row('Source', last.neighbor_source || last.source),
            row('MAC', last.mac),
            row('IP', last.ip),
            row('VLAN', last.vlan),
            row('Status', last.status_after),
            row('Seen', last.observed_at_text)
        ].filter(Boolean).join('');
        box.innerHTML = '<div class="phase79-last-connected-list">' + rows + '</div>';
    }
'''

REFRESH_FUNC = r'''    function refreshLastConnectionFromPayload(button, root, attrName){
        if(!button || !button.dataset || !button.dataset.portId) return;
        const url = '/port/' + encodeURIComponent(button.dataset.portId) + '/payload/';
        fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}})
            .then(function(response){ return response.json().catch(function(){return null;}); })
            .then(function(data){
                if(!data || !data.ok || !data.port) return;
                updateButtonFromPayload(button, data);
                setLastConnection(root, attrName, effectiveLastConnectionFromDataset(button.dataset));
            })
            .catch(function(){ /* read-only helper; do not break popup */ });
    }
'''


def backup(path: Path) -> None:
    if path.exists():
        dst = BACKUP_ROOT / path.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    backup(path)
    path.write_text(text, encoding="utf-8")


def replace_js_function(text: str, name: str, new_func: str) -> str:
    marker = f"    function {name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"switchmap.js: function {name} not found")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"switchmap.js: function {name} opening brace not found")
    depth = 0
    i = brace
    in_str = None
    esc = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"', '`'):
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    if end < len(text) and text[end:end+1] == "\n":
                        end += 1
                    return text[:start] + new_func + text[end:]
        i += 1
    raise RuntimeError(f"switchmap.js: function {name} closing brace not found")


def patch_js() -> None:
    path = FILES["js"]
    text = read(path)
    if "function lastConnectionFromDataset" not in text:
        raise RuntimeError("switchmap.js: lastConnectionFromDataset not found")

    block = EFFECTIVE_FUNC + SET_FUNC + REFRESH_FUNC + "    function updateButtonFromPayload"
    pattern = re.compile(r"    function effectiveLastConnectionFromDataset\(d\)\{.*?\n    function updateButtonFromPayload", re.S)
    text2, count = pattern.subn(block, text, count=1)
    if count != 1:
        pattern = re.compile(r"    function setLastConnection\(root, attrName, last\)\{.*?\n    function updateButtonFromPayload", re.S)
        text2, count = pattern.subn(EFFECTIVE_FUNC + SET_FUNC + REFRESH_FUNC + "    function updateButtonFromPayload", text, count=1)
    if count != 1:
        raise RuntimeError("switchmap.js: Last Connected function block not found")
    text = text2

    text = text.replace("setLastConnection(modal, 'data-field', lastConnectionFromDataset(d));", "setLastConnection(modal, 'data-field', effectiveLastConnectionFromDataset(d));")
    text = text.replace('setLastConnection(modal, "data-field", lastConnectionFromDataset(d));', 'setLastConnection(modal, "data-field", effectiveLastConnectionFromDataset(d));')
    text = text.replace("setLastConnection(panel, 'data-detail', lastConnectionFromDataset(d));", "setLastConnection(panel, 'data-detail', effectiveLastConnectionFromDataset(d));")
    text = text.replace('setLastConnection(panel, "data-detail", lastConnectionFromDataset(d));', 'setLastConnection(panel, "data-detail", effectiveLastConnectionFromDataset(d));')
    if "Phase79.5 - hard reset renderer" not in text or "function updateButtonFromPayload" not in text:
        raise RuntimeError("switchmap.js: Phase79.5 marker not applied")
    write(path, text)


def find_div_bounds(text: str, attr: str = "data-phase79-last-connected") -> tuple[int, int] | None:
    attr_pos = text.find(attr)
    if attr_pos < 0:
        return None
    start = text.rfind("<div", 0, attr_pos)
    if start < 0:
        return None
    tag_re = re.compile(r"</?div\b[^>]*>", re.I)
    depth = 0
    for m in tag_re.finditer(text, start):
        token = m.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, m.end()
        else:
            depth += 1
    return None


def patch_template(path: Path) -> None:
    text = read(path)
    replacement = LC_BOX if path.name == "switch_list.html" else LC_BOX_DETAIL
    bounds = find_div_bounds(text)
    if not bounds:
        raise RuntimeError(f"{path.name}: data-phase79-last-connected div not found")
    start, end = bounds
    text = text[:start] + replacement + text[end:]
    write(path, text)


def patch_css() -> None:
    write(FILES["css"], CSS + "\n")


def version_static_ref(line: str, filename: str) -> str:
    if filename not in line:
        return line
    if "?v=" in line:
        return re.sub(r"\?v=[^\"']+", "?v=" + VERSION, line)
    return line.replace(filename, filename + "?v=" + VERSION)


def patch_base() -> None:
    path = FILES["base"]
    text = read(path)
    lines = []
    hit_js = hit_css = False
    for line in text.splitlines():
        if "switchmap-phase79.css" in line:
            line = version_static_ref(line, "switchmap-phase79.css")
            hit_css = True
        if "switchmap.js" in line:
            line = version_static_ref(line, "switchmap.js")
            hit_js = True
        lines.append(line)
    if not hit_css:
        raise RuntimeError("base.html: switchmap-phase79.css include not found")
    if not hit_js:
        raise RuntimeError("base.html: switchmap.js include not found")
    write(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def run_best_effort(args: list[str], timeout: int = 120) -> None:
    try:
        subprocess.run(args, cwd=str(ROOT), timeout=timeout, check=False)
    except Exception:
        pass


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_js()
    patch_template(FILES["switch_list"])
    patch_template(FILES["switch_detail"])
    patch_css()
    patch_base()
    run_best_effort([sys.executable, str(ROOT / "manage.py"), "collectstatic", "--noinput"], timeout=120)
    print(f"PHASE79_5_PATCH_OK backup_dir={BACKUP_ROOT}")

if __name__ == "__main__":
    main()
