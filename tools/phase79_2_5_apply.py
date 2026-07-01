
from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / 'backups' / ('phase79_2_5_last_connected_current_port_fix_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
FILES = {
    'views': ROOT / 'inventory/views.py',
    'history': ROOT / 'inventory/phase79_history.py',
    'js': ROOT / 'inventory/static/inventory/switchmap.js',
    'css': ROOT / 'inventory/static/inventory/css/switchmap-phase79.css',
    'base': ROOT / 'inventory/templates/inventory/base.html',
}
VERSION = 'phase79-2-5-last-connected-current-port-fix'

STRICT_HISTORY_FUNCTIONS = r'''
def _identity_clean(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value in ("", "-", "None", "none", "null", "Null", "NULL"):
        return ""
    if value.lower() in ("unknown", "نامشخص"):
        return ""
    return value


def _first_mac(value):
    value = _identity_clean(value)
    if not value:
        return ""
    for part in re.split(r"[\\s,;]+", value):
        part = _identity_clean(part)
        if part:
            return part
    return ""


def port_has_identity_data(port: Port) -> bool:
    # Phase79.2.5: only real endpoint evidence counts as connected-device history.
    # Poll timestamps, VLAN, status, neighbor_source, mac_count and default device_type=unknown
    # are not enough; they caused fake Last Connected records on empty SFP ports.
    if _identity_clean(getattr(port, "connected_device", "")):
        return True
    if _identity_clean(getattr(port, "neighbor_device", "")) or _identity_clean(getattr(port, "neighbor_port", "")):
        return True
    if _identity_clean(getattr(port, "neighbor_ip", "")) or _identity_clean(getattr(port, "ip_address", "")):
        return True
    if _identity_clean(getattr(port, "mac_address", "")) or _first_mac(getattr(port, "mac_addresses", "")):
        return True
    return False


def port_identity_hash(port: Port) -> str:
    parts = [
        f"connected_device={_identity_clean(getattr(port, 'connected_device', ''))}",
        f"neighbor_device={_identity_clean(getattr(port, 'neighbor_device', ''))}",
        f"neighbor_port={_identity_clean(getattr(port, 'neighbor_port', ''))}",
        f"neighbor_ip={_identity_clean(getattr(port, 'neighbor_ip', ''))}",
        f"ip_address={_identity_clean(getattr(port, 'ip_address', ''))}",
        f"mac_address={_identity_clean(getattr(port, 'mac_address', ''))}",
        f"mac_addresses={_first_mac(getattr(port, 'mac_addresses', ''))}",
        f"vlan={_identity_clean(getattr(port, 'access_vlan', None) or getattr(port, 'vlan', None))}",
        f"mode={_identity_clean(getattr(port, 'port_mode', ''))}",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()

'''

VIEWS_REPLACEMENT = r'''
def _phase79_empty_last_connection_payload():
    return {
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


def _phase79_clean_identity(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value in ("", "-", "None", "none", "null", "Null", "NULL"):
        return ""
    if value.lower() in ("unknown", "نامشخص"):
        return ""
    return value


def _phase79_first_mac(value):
    value = _phase79_clean_identity(value)
    if not value:
        return ""
    for part in re.split(r"[\s,;]+", value):
        part = _phase79_clean_identity(part)
        if part:
            return part
    return ""


def _phase79_neighbor_label(device, port):
    return " / ".join(filter(None, [
        _phase79_clean_identity(device),
        _phase79_clean_identity(port),
    ]))


def _phase79_current_connection_payload(port):
    if not port:
        return _phase79_empty_last_connection_payload()
    connected_device = _phase79_clean_identity(getattr(port, "connected_device", ""))
    neighbor = _phase79_neighbor_label(getattr(port, "neighbor_device", ""), getattr(port, "neighbor_port", ""))
    mac_value = _phase79_clean_identity(getattr(port, "mac_address", "")) or _phase79_first_mac(getattr(port, "mac_addresses", ""))
    ip_value = _phase79_clean_identity(getattr(port, "ip_address", None)) or _phase79_clean_identity(getattr(port, "neighbor_ip", None))
    identity = connected_device or neighbor or mac_value or ip_value
    if not identity:
        return _phase79_empty_last_connection_payload()
    observed_at = getattr(port, "discovery_last_poll", None) or getattr(port, "snmp_last_poll", None) or getattr(port, "updated_at", None)
    status_after = getattr(port, "status", "") or ""
    event_type = "Current" if str(status_after).lower() == "up" else "Last known"
    vlan_value = getattr(port, "access_vlan", None) or getattr(port, "vlan", None)
    return {
        "available": True,
        "identity": identity,
        "event_type": event_type,
        "observed_at_text": _dt_text(observed_at),
        "last_verified_at_text": _dt_text(observed_at),
        "neighbor": neighbor or "-",
        "neighbor_source": _phase79_clean_identity(getattr(port, "neighbor_source", "")) or "-",
        "mac": mac_value or "-",
        "ip": ip_value or "-",
        "vlan": _phase79_clean_identity(vlan_value) or "-",
        "status_after": status_after or "-",
        "source": _phase79_clean_identity(getattr(port, "neighbor_source", "")) or "current-db",
    }


def _phase79_history_payload(history):
    if not history:
        return _phase79_empty_last_connection_payload()
    connected_device = _phase79_clean_identity(getattr(history, "connected_device", ""))
    neighbor = _phase79_neighbor_label(getattr(history, "neighbor_device", ""), getattr(history, "neighbor_port", ""))
    mac_value = _phase79_clean_identity(getattr(history, "mac_address", "")) or _phase79_first_mac(getattr(history, "mac_addresses", ""))
    ip_value = _phase79_clean_identity(getattr(history, "ip_address", None)) or _phase79_clean_identity(getattr(history, "neighbor_ip", None))
    identity = connected_device or neighbor or mac_value or ip_value
    if not identity:
        return _phase79_empty_last_connection_payload()
    vlan_value = getattr(history, "access_vlan", None) or getattr(history, "vlan", None)
    return {
        "available": True,
        "identity": identity,
        "event_type": history.get_event_type_display() if hasattr(history, "get_event_type_display") else _phase79_clean_identity(getattr(history, "event_type", "")) or "-",
        "observed_at_text": _dt_text(getattr(history, "observed_at", None)),
        "last_verified_at_text": _dt_text(getattr(history, "last_verified_at", None)),
        "neighbor": neighbor or "-",
        "neighbor_source": _phase79_clean_identity(getattr(history, "neighbor_source", "")) or "-",
        "mac": mac_value or "-",
        "ip": ip_value or "-",
        "vlan": _phase79_clean_identity(vlan_value) or "-",
        "status_after": _phase79_clean_identity(getattr(history, "status_after", "")) or "-",
        "source": _phase79_clean_identity(getattr(history, "source", "")) or "-",
    }


def _phase79_effective_last_connection_payload(port):
    current = _phase79_current_connection_payload(port)
    if current.get("available"):
        return current
    return _phase79_history_payload(latest_port_connection(port))
'''

CSS_APPEND = r'''

/* Phase79.2.5 - strict, readable Last Connected Device panel */
[data-phase79-last-connected] {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 6px 0 10px 0 !important;
    padding: 10px 12px !important;
    border: 1px solid rgba(203, 213, 225, .95) !important;
    border-radius: 12px !important;
    background: #ffffff !important;
    box-shadow: none !important;
    max-height: none !important;
    min-height: 0 !important;
    overflow: visible !important;
    direction: rtl !important;
}
[data-phase79-last-connected].is-empty {
    background: #f8fafc !important;
    border-style: dashed !important;
}
.phase79-lc-empty {
    display: block !important;
    padding: 6px 2px !important;
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    line-height: 1.8 !important;
    text-align: right !important;
    direction: rtl !important;
}
.phase79-lc-clean-row {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 12px !important;
    min-height: 26px !important;
    padding: 5px 0 !important;
    border-bottom: 1px solid rgba(226, 232, 240, .95) !important;
    direction: ltr !important;
}
.phase79-lc-clean-row:last-child { border-bottom: 0 !important; }
.phase79-lc-clean-label {
    display: inline-block !important;
    flex: 0 0 auto !important;
    color: #64748b !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
    text-align: left !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
}
.phase79-lc-clean-value {
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

JS_SET_LAST_CONNECTION = r'''    function setLastConnection(root, attrName, last){
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
        const available = !!(last && last.available && clean(last.identity));
        setText(root, prefix + 'last_connection_event_type' + suffix, available ? historyValue(last.event_type) : '-');
        if(!box){
            setText(root, prefix + 'last_connection_identity' + suffix, available ? historyValue(last.identity) : 'سابقه‌ای ثبت نشده');
            return;
        }
        if(!available){
            box.classList.add('is-empty');
            box.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        box.classList.remove('is-empty');
        const rows = [];
        function add(label, value){
            const v = clean(value);
            if(!v) return;
            rows.push('<div class="phase79-lc-clean-row"><span class="phase79-lc-clean-label">' + esc(label) + '</span><strong class="phase79-lc-clean-value" title="' + esc(v) + '">' + esc(v) + '</strong></div>');
        }
        add('Identity', last.identity);
        add('Seen', last.observed_at_text);
        add('Neighbor', last.neighbor);
        add('MAC', last.mac);
        add('IP', last.ip);
        add('VLAN', last.vlan);
        add('Status', last.status_after);
        add('Source', last.source);
        box.innerHTML = rows.length ? rows.join('') : '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
        if(!rows.length) box.classList.add('is-empty');
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

def patch_history() -> None:
    path = FILES['history']
    text = read(path)
    if 'import re' not in text.split('\n')[:10]:
        text = text.replace('import hashlib\n', 'import hashlib\nimport re\n', 1)
    pattern = re.compile(r'def port_has_identity_data\(port: Port\) -> bool:.*?\n\ndef _history_kwargs\(', re.S)
    new_text, count = pattern.subn(lambda m: STRICT_HISTORY_FUNCTIONS + '\ndef _history_kwargs(', text, count=1)
    if count != 1:
        raise RuntimeError('phase79_history: port_has_identity_data/port_identity_hash block not found')
    write(path, new_text)

def patch_views() -> None:
    path = FILES['views']
    text = read(path)
    pattern = re.compile(r'def _phase79_history_payload\(history\):.*?\n\ndef _port_payload\(port\):', re.S)
    new_text, count = pattern.subn(lambda m: VIEWS_REPLACEMENT + '\n\ndef _port_payload(port):', text, count=1)
    if count != 1:
        raise RuntimeError('views: _phase79_history_payload block not found')
    old = '"last_connection": _phase79_history_payload(latest_port_connection(port)),'
    if old in new_text:
        new_text = new_text.replace(old, '"last_connection": _phase79_effective_last_connection_payload(port),', 1)
    elif '"last_connection": _phase79_effective_last_connection_payload(port),' not in new_text:
        raise RuntimeError('views: last_connection payload line not found')
    write(path, new_text)

def patch_js() -> None:
    path = FILES['js']
    text = read(path)
    pattern = re.compile(r'    function setLastConnection\(root, attrName, last\)\{.*?\n    \}\n    function refreshLastConnectionFromPayload', re.S)
    new_text, count = pattern.subn(lambda m: JS_SET_LAST_CONNECTION + '    function refreshLastConnectionFromPayload', text, count=1)
    if count != 1:
        raise RuntimeError('js: setLastConnection block not found')
    write(path, new_text)

def patch_css() -> None:
    path = FILES['css']
    text = read(path) if path.exists() else ''
    if 'Phase79.2.5 - strict, readable Last Connected Device panel' not in text:
        text = text.rstrip() + CSS_APPEND + '\n'
    write(path, text)

def patch_base() -> None:
    path = FILES['base']
    text = read(path)
    if 'switchmap-phase79.css' not in text:
        raise RuntimeError('base: switchmap-phase79.css include not found')
    changed = False
    lines = []
    for line in text.splitlines():
        if 'switchmap-phase79.css' in line:
            if '?v=' in line:
                line = re.sub(r'\?v=[^"\']+', '?v=' + VERSION, line)
            else:
                line = line.replace('switchmap-phase79.css', 'switchmap-phase79.css?v=' + VERSION)
            changed = True
        lines.append(line)
    if not changed:
        raise RuntimeError('base: phase79 css version not changed')
    write(path, '\n'.join(lines) + ('\n' if text.endswith('\n') else ''))

def collectstatic_best_effort() -> None:
    manage = ROOT / 'manage.py'
    if not manage.exists():
        return
    try:
        subprocess.run([sys.executable, str(manage), 'collectstatic', '--noinput'], cwd=str(ROOT), timeout=90, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_history()
    patch_views()
    patch_js()
    patch_css()
    patch_base()
    collectstatic_best_effort()
    print(f'PHASE79_2_5_PATCH_OK backup_dir={BACKUP_ROOT}')

if __name__ == '__main__':
    main()
