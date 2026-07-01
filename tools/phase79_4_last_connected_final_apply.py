from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / "backups" / ("phase79_4_last_connected_final_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
FILES = {
    "js": ROOT / "inventory" / "static" / "inventory" / "switchmap.js",
    "css": ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase79.css",
    "base": ROOT / "inventory" / "templates" / "inventory" / "base.html",
    "switch_list": ROOT / "inventory" / "templates" / "inventory" / "switch_list.html",
    "switch_detail": ROOT / "inventory" / "templates" / "inventory" / "switch_detail.html",
}
VERSION = "phase79-4-last-connected-final"

SET_LAST_CONNECTION_FINAL = r'''    function setLastConnection(root, attrName, last){
        // Phase79.4 - final deterministic Last Connected renderer.
        // It ignores fake records with only poll/status/VLAN and removes old grid classes from the box.
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
        function labelValue(label, value){
            const v = clean(value);
            if(!v) return '';
            return '<div class="phase79-lc-final-row"><span>' + esc(label) + '</span><strong title="' + esc(v) + '">' + esc(v) + '</strong></div>';
        }
        const identity = clean(last && last.identity);
        const hasReal = !!(last && last.available && identity);
        setText(root, prefix + 'last_connection_event_type' + suffix, hasReal ? clean(last.event_type) || '-' : '-');
        setText(root, prefix + 'last_connection_identity' + suffix, hasReal ? identity : 'سابقه‌ای ثبت نشده');
        if(!box) return;

        // Remove old key-grid/compact-grid classes that were forcing broken layout.
        box.className = 'phase79-lc-final ' + (hasReal ? 'is-available' : 'is-empty');
        box.removeAttribute('style');
        if(!hasReal){
            box.innerHTML = '<div class="phase79-lc-final-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        const eventType = clean(last.event_type) || 'Last Connected';
        const rows = [];
        rows.push(labelValue('Identity', identity));
        rows.push(labelValue('Type', eventType));
        rows.push(labelValue('Seen', last.observed_at_text));
        rows.push(labelValue('Neighbor', last.neighbor));
        rows.push(labelValue('Source', last.neighbor_source || last.source));
        rows.push(labelValue('MAC', last.mac));
        rows.push(labelValue('IP', last.ip));
        rows.push(labelValue('VLAN', last.vlan));
        rows.push(labelValue('Status', last.status_after));
        box.innerHTML = rows.filter(Boolean).join('');
    }
'''

EFFECTIVE_DATASET_FUNCTION = r'''    function effectiveLastConnectionFromDataset(d){
        // Phase79.4 - use current visible port data first; history is fallback only.
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
        const currentIdentity = neighbor || device || mac || ip;
        if(currentIdentity){
            return {
                available: true,
                identity: currentIdentity,
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

CSS_FINAL = r'''

/* Phase79.4 - final Last Connected Device layout; isolated from key-grid/compact-grid rules */
[data-phase79-last-connected].phase79-lc-final,
.phase79-lc-final[data-phase79-last-connected] {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 8px 0 8px 0 !important;
    padding: 8px 10px !important;
    border: 1px solid rgba(203,213,225,.95) !important;
    border-radius: 12px !important;
    background: #ffffff !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
    direction: ltr !important;
    box-shadow: none !important;
}
[data-phase79-last-connected].phase79-lc-final.is-empty,
.phase79-lc-final.is-empty[data-phase79-last-connected] {
    background: #f8fafc !important;
    border-style: dashed !important;
}
.phase79-lc-final-empty {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    padding: 8px 10px !important;
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    line-height: 1.8 !important;
    text-align: right !important;
    direction: rtl !important;
}
.phase79-lc-final-row {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 12px !important;
    width: 100% !important;
    min-height: 24px !important;
    padding: 5px 0 !important;
    border-bottom: 1px solid rgba(226,232,240,.95) !important;
    direction: ltr !important;
}
.phase79-lc-final-row:last-child { border-bottom: 0 !important; }
.phase79-lc-final-row span {
    display: inline-block !important;
    flex: 0 0 86px !important;
    color: #64748b !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    line-height: 1.2 !important;
    text-align: left !important;
    white-space: nowrap !important;
    direction: ltr !important;
}
.phase79-lc-final-row strong {
    display: block !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
    color: #0f172a !important;
    font-size: 12px !important;
    font-weight: 900 !important;
    line-height: 1.25 !important;
    text-align: right !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
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
    text, count = pattern.subn(lambda m: SET_LAST_CONNECTION_FINAL + "    function refreshLastConnectionFromPayload", text, count=1)
    if count != 1:
        raise RuntimeError("switchmap.js: setLastConnection block not found")

    if "function effectiveLastConnectionFromDataset(" not in text:
        marker = "    function setLastConnection(root, attrName, last){"
        if marker not in text:
            raise RuntimeError("switchmap.js: setLastConnection insertion marker not found")
        text = text.replace(marker, EFFECTIVE_DATASET_FUNCTION + marker, 1)

    text = text.replace("setLastConnection(modal, 'data-field', lastConnectionFromDataset(d));", "setLastConnection(modal, 'data-field', effectiveLastConnectionFromDataset(d));")
    text = text.replace('setLastConnection(modal, "data-field", lastConnectionFromDataset(d));', 'setLastConnection(modal, "data-field", effectiveLastConnectionFromDataset(d));')
    text = text.replace("setLastConnection(panel, 'data-detail', lastConnectionFromDataset(d));", "setLastConnection(panel, 'data-detail', effectiveLastConnectionFromDataset(d));")
    text = text.replace('setLastConnection(panel, "data-detail", lastConnectionFromDataset(d));', 'setLastConnection(panel, "data-detail", effectiveLastConnectionFromDataset(d));')

    if "effectiveLastConnectionFromDataset(d)" not in text:
        raise RuntimeError("switchmap.js: effective last connection calls not applied")
    write(path, text)


def patch_templates() -> None:
    for key in ("switch_list", "switch_detail"):
        path = FILES[key]
        text = read(path)
        # Normalize opening tag only; JS replaces content on click/payload refresh.
        text2 = re.sub(r'<div\s+class="[^"]*phase79[^"\n]*"\s+data-phase79-last-connected\s*>', '<div class="phase79-lc-final is-empty" data-phase79-last-connected>', text)
        text2 = re.sub(r'<div\s+class="[^"]*key-grid[^"\n]*"\s+data-phase79-last-connected\s*>', '<div class="phase79-lc-final is-empty" data-phase79-last-connected>', text2)
        if text2 != text:
            write(path, text2)


def patch_css() -> None:
    path = FILES["css"]
    text = read(path) if path.exists() else ""
    if "Phase79.4 - final Last Connected Device layout" not in text:
        text = text.rstrip() + CSS_FINAL + "\n"
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
        raise RuntimeError("base.html: phase79 css include not versioned")
    write(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


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
    patch_templates()
    patch_css()
    patch_base()
    collectstatic_best_effort()
    print(f"PHASE79_4_PATCH_OK backup_dir={BACKUP_ROOT}")


if __name__ == "__main__":
    main()
