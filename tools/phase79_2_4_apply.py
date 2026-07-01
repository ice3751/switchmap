from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / 'backups' / ('phase79_2_4_last_connected_truth_guard_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S'))

FILES = {
    'views': ROOT / 'inventory/views.py',
    'js': ROOT / 'inventory/static/inventory/switchmap.js',
    'css': ROOT / 'inventory/static/inventory/css/switchmap-phase79.css',
    'base': ROOT / 'inventory/templates/inventory/base.html',
}

VERSION = 'phase79-2-4-last-connected-truth-guard'

CSS_APPEND = r'''

/* Phase79.2.4 - truth guard for empty Last Connected Device records */
[data-phase79-last-connected] {
    display: block !important;
    margin: 6px 0 10px 0 !important;
    padding: 8px 10px !important;
    border: 1px solid rgba(203, 213, 225, .95) !important;
    border-radius: 12px !important;
    background: #ffffff !important;
    box-shadow: none !important;
    max-height: 160px !important;
    overflow: auto !important;
    direction: ltr !important;
}
[data-phase79-last-connected].is-empty {
    max-height: none !important;
    overflow: visible !important;
    background: #f8fafc !important;
    border-style: dashed !important;
    direction: rtl !important;
}
[data-phase79-last-connected].is-empty .phase79-lc-row,
[data-phase79-last-connected].is-empty .key-item {
    display: none !important;
}
[data-phase79-last-connected].is-empty::before {
    content: 'سابقه اتصال واقعی برای این پورت ثبت نشده است.';
    display: block !important;
    padding: 8px 4px !important;
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    line-height: 1.7 !important;
    text-align: right !important;
    direction: rtl !important;
}
[data-phase79-last-connected]:not(.is-empty) .phase79-lc-row {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 10px !important;
    min-height: 24px !important;
    padding: 3px 0 !important;
    border-bottom: 1px solid rgba(226, 232, 240, .95) !important;
}
[data-phase79-last-connected]:not(.is-empty) .phase79-lc-row:last-child {
    border-bottom: 0 !important;
}
[data-phase79-last-connected]:not(.is-empty) .phase79-lc-row span {
    display: inline-block !important;
    flex: 0 0 auto !important;
    margin: 0 !important;
    color: #64748b !important;
    font-size: 10px !important;
    line-height: 1.2 !important;
    text-align: left !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
}
[data-phase79-last-connected]:not(.is-empty) .phase79-lc-row strong {
    display: block !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
    margin: 0 !important;
    color: #0f172a !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    line-height: 1.25 !important;
    text-align: right !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
'''

VIEWS_REPLACEMENT = r'''def _phase79_history_payload(history):
    empty_payload = {
        "available": False,
        "identity": "سابقه‌ای ثبت نشده",
        "event_type": "-",
        "observed_at_text": "-",
        "last_verified_at_text": "-",
        "neighbor": "-",
        "neighbor_source": "-",
        "mac": "-",
        "ip": "-",
        "vlan": "-",
        "status_after": "-",
        "source": "-",
    }
    if not history:
        return empty_payload

    def clean(value):
        if value is None:
            return ""
        value = str(value).strip()
        if value in ("", "-", "None", "none", "unknown", "Unknown", "UNKNOWN"):
            return ""
        return value

    neighbor = " / ".join(filter(None, [
        clean(getattr(history, "neighbor_device", "")),
        clean(getattr(history, "neighbor_port", "")),
    ]))
    mac_value = clean(getattr(history, "mac_address", ""))
    mac_addresses = clean(getattr(history, "mac_addresses", ""))
    if not mac_value and mac_addresses:
        mac_value = mac_addresses.splitlines()[0].strip()

    ip_value = getattr(history, "ip_address", None) or getattr(history, "neighbor_ip", None)
    ip_text = clean(ip_value)
    connected_device = clean(getattr(history, "connected_device", ""))
    device_type = clean(getattr(history, "device_type", ""))
    owner = clean(getattr(history, "owner", ""))

    identity_candidates = [
        connected_device,
        neighbor,
        mac_value,
        ip_text,
        device_type,
        owner,
    ]
    identity = next((item for item in identity_candidates if clean(item)), "")

    # observed_at / VLAN / status are not identity evidence.  They can be created by polling
    # even when the port has no module or no known connected endpoint.
    if not identity:
        return empty_payload

    vlan_value = getattr(history, "access_vlan", None) or getattr(history, "vlan", None)
    return {
        "available": True,
        "identity": identity,
        "event_type": history.get_event_type_display() if hasattr(history, "get_event_type_display") else clean(getattr(history, "event_type", "")) or "-",
        "observed_at_text": _dt_text(getattr(history, "observed_at", None)),
        "last_verified_at_text": _dt_text(getattr(history, "last_verified_at", None)),
        "neighbor": neighbor or "-",
        "neighbor_source": clean(getattr(history, "neighbor_source", "")) or "-",
        "mac": mac_value or "-",
        "ip": ip_text or "-",
        "vlan": clean(vlan_value) or "-",
        "status_after": clean(getattr(history, "status_after", "")) or "-",
        "source": clean(getattr(history, "source", "")) or "-",
    }
'''

JS_HELPERS = r'''    function meaningfulHistoryValue(value){
        const s = String(value === 0 ? '0' : (value || '')).trim();
        if(!s) return false;
        const low = s.toLowerCase();
        if(s === '-' || low === 'none' || low === 'null' || low === 'unknown') return false;
        if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return false;
        return true;
    }
    function hasMeaningfulLastConnection(last){
        if(!last || last.available === false) return false;
        return [last.identity, last.neighbor, last.mac, last.ip, last.device, last.connected_device].some(meaningfulHistoryValue);
    }
'''

JS_SET_LAST_CONNECTION = r'''    function setLastConnection(root, attrName, last){
        if(!root) return;
        const prefix = '[' + attrName + '="';
        const suffix = '"]';
        const available = hasMeaningfulLastConnection(last);
        const box = root.querySelector('[data-phase79-last-connected]');
        if(box) box.classList.toggle('is-empty', !available);
        setText(root, prefix + 'last_connection_identity' + suffix, available ? historyValue(last.identity) : 'سابقه‌ای ثبت نشده');
        setText(root, prefix + 'last_connection_event_type' + suffix, available ? historyValue(last.event_type) : '-');
        setText(root, prefix + 'last_connection_observed_at' + suffix, available ? historyValue(last.observed_at_text) : '-');
        setText(root, prefix + 'last_connection_neighbor' + suffix, available ? historyValue(last.neighbor) : '-');
        setText(root, prefix + 'last_connection_mac' + suffix, available ? historyValue(last.mac) : '-');
        setText(root, prefix + 'last_connection_ip' + suffix, available ? historyValue(last.ip) : '-');
        setText(root, prefix + 'last_connection_vlan' + suffix, available ? historyValue(last.vlan) : '-');
        setText(root, prefix + 'last_connection_status' + suffix, available ? historyValue(last.status_after) : '-');
        setText(root, prefix + 'last_connection_source' + suffix, available ? historyValue(last.source) : '-');
    }
'''


def backup(path: Path) -> None:
    if path.exists():
        rel = path.relative_to(ROOT)
        dst = BACKUP_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding='utf-8', errors='ignore')


def write(path: Path, text: str) -> None:
    backup(path)
    path.write_text(text, encoding='utf-8')


def patch_views() -> None:
    path = FILES['views']
    text = read(path)
    pattern = re.compile(r'def _phase79_history_payload\(history\):.*?\n\ndef _port_payload\(port\):', re.S)
    new_text, count = pattern.subn(VIEWS_REPLACEMENT + '\n\ndef _port_payload(port):', text, count=1)
    if count != 1:
        raise RuntimeError('views:_phase79_history_payload block not found')
    write(path, new_text)


def patch_js() -> None:
    path = FILES['js']
    text = read(path)
    if 'function meaningfulHistoryValue(value)' not in text:
        marker = '    function historyValue(value){ return valueOrDash(value); }\n'
        if marker not in text:
            raise RuntimeError('js:historyValue marker not found')
        text = text.replace(marker, marker + JS_HELPERS, 1)
    pattern = re.compile(r'    function setLastConnection\(root, attrName, last\)\{.*?\n    \}\n    function refreshLastConnectionFromPayload', re.S)
    text2, count = pattern.subn(JS_SET_LAST_CONNECTION + '    function refreshLastConnectionFromPayload', text, count=1)
    if count != 1:
        raise RuntimeError('js:setLastConnection block not found')
    write(path, text2)


def patch_css() -> None:
    path = FILES['css']
    text = read(path) if path.exists() else ''
    if 'Phase79.2.4 - truth guard' not in text:
        text = text.rstrip() + CSS_APPEND + '\n'
    write(path, text)


def patch_base() -> None:
    path = FILES['base']
    text = read(path)
    if 'switchmap-phase79.css' not in text:
        raise RuntimeError('base:switchmap-phase79.css include not found')
    new_lines = []
    changed = False
    for line in text.splitlines():
        if 'switchmap-phase79.css' in line:
            if '?v=' in line:
                line = re.sub(r'\?v=[^"\']+', '?v=' + VERSION, line)
            else:
                line = line.replace('switchmap-phase79.css', 'switchmap-phase79.css?v=' + VERSION)
            changed = True
        new_lines.append(line)
    if not changed:
        raise RuntimeError('base:phase79 css version not changed')
    write(path, '\n'.join(new_lines) + ('\n' if text.endswith('\n') else ''))


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_views()
    patch_js()
    patch_css()
    patch_base()
    print(f'PHASE79_2_4_PATCH_OK backup_dir={BACKUP_ROOT}')


if __name__ == '__main__':
    main()
