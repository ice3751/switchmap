from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / 'backups' / ('phase79_2_3_last_connected_safe_ui_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S'))

FILES = {
    'history': ROOT / 'inventory/phase79_history.py',
    'views': ROOT / 'inventory/views.py',
    'switch_list': ROOT / 'inventory/templates/inventory/switch_list.html',
    'switch_detail': ROOT / 'inventory/templates/inventory/switch_detail.html',
    'css': ROOT / 'inventory/static/inventory/css/switchmap-phase79.css',
    'base': ROOT / 'inventory/templates/inventory/base.html',
}

VERSION = 'phase79-2-3-last-connected-safe-ui'

CSS = r'''/* Phase79.2.3 - safe compact Last Connected Device UI */
.phase79-last-connected-title {
    margin-top: 10px !important;
    padding-top: 8px !important;
    border-top: 1px solid rgba(148, 163, 184, .24) !important;
}
.phase79-last-connected-title small {
    direction: ltr !important;
    unicode-bidi: isolate !important;
    font-size: 10px !important;
    opacity: .70 !important;
}
.phase79-lc-list,
.phase79-last-connected {
    display: block !important;
    border: 1px solid rgba(203, 213, 225, .95) !important;
    border-radius: 12px !important;
    padding: 8px 10px !important;
    margin: 6px 0 10px 0 !important;
    background: #ffffff !important;
    box-shadow: none !important;
    max-height: none !important;
    overflow: visible !important;
    direction: ltr !important;
}
.phase79-lc-row {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 10px !important;
    min-height: 26px !important;
    padding: 4px 0 !important;
    border-bottom: 1px solid rgba(226, 232, 240, .95) !important;
}
.phase79-lc-row:last-child {
    border-bottom: 0 !important;
}
.phase79-lc-row span {
    display: inline-block !important;
    flex: 0 0 auto !important;
    color: #64748b !important;
    font-size: 10px !important;
    line-height: 1.2 !important;
    text-align: left !important;
    direction: ltr !important;
    unicode-bidi: isolate !important;
    margin: 0 !important;
}
.phase79-lc-row strong {
    display: block !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
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
.phase79-lc-row.phase79-lc-wide strong {
    text-align: right !important;
}
.phase79-last-connected.is-empty {
    opacity: 1 !important;
    background: #f8fafc !important;
}
.phase79-last-connected.is-empty .phase79-lc-row:not(:first-child) {
    display: none !important;
}
.phase79-last-connected.is-empty .phase79-lc-row:first-child {
    border-bottom: 0 !important;
}
.phase79-last-connected.is-empty .phase79-lc-row:first-child strong {
    direction: rtl !important;
    text-align: right !important;
    white-space: normal !important;
}
@media (max-width: 720px) {
    .phase79-lc-row {
        align-items: flex-start !important;
        flex-direction: column !important;
        gap: 2px !important;
    }
    .phase79-lc-row strong {
        width: 100% !important;
        text-align: left !important;
    }
}
'''

FIELD_OLD = '''                <div class="key-grid compact-grid port-main-grid phase79-last-connected" data-phase79-last-connected>
                    <div class="key-item key-item-wide"><span>Identity</span><strong class="ltr" data-field="last_connection_identity">-</strong></div>
                    <div class="key-item"><span>Last Seen</span><strong class="ltr" data-field="last_connection_observed_at">-</strong></div>
                    <div class="key-item key-item-wide"><span>Neighbor</span><strong class="ltr" data-field="last_connection_neighbor">-</strong></div>
                    <div class="key-item"><span>MAC</span><strong class="ltr" data-field="last_connection_mac">-</strong></div>
                    <div class="key-item"><span>IP</span><strong class="ltr" data-field="last_connection_ip">-</strong></div>
                    <div class="key-item"><span>VLAN</span><strong class="ltr" data-field="last_connection_vlan">-</strong></div>
                    <div class="key-item"><span>Status</span><strong data-field="last_connection_status">-</strong></div>
                    <div class="key-item"><span>Source</span><strong data-field="last_connection_source">-</strong></div>
                </div>'''
FIELD_NEW = '''                <div class="phase79-last-connected phase79-lc-list" data-phase79-last-connected>
                    <div class="phase79-lc-row phase79-lc-wide"><span>Identity</span><strong class="ltr" data-field="last_connection_identity">-</strong></div>
                    <div class="phase79-lc-row"><span>Last Seen</span><strong class="ltr" data-field="last_connection_observed_at">-</strong></div>
                    <div class="phase79-lc-row phase79-lc-wide"><span>Neighbor</span><strong class="ltr" data-field="last_connection_neighbor">-</strong></div>
                    <div class="phase79-lc-row"><span>MAC</span><strong class="ltr" data-field="last_connection_mac">-</strong></div>
                    <div class="phase79-lc-row"><span>IP</span><strong class="ltr" data-field="last_connection_ip">-</strong></div>
                    <div class="phase79-lc-row"><span>VLAN</span><strong class="ltr" data-field="last_connection_vlan">-</strong></div>
                    <div class="phase79-lc-row"><span>Status</span><strong data-field="last_connection_status">-</strong></div>
                    <div class="phase79-lc-row"><span>Source</span><strong data-field="last_connection_source">-</strong></div>
                </div>'''
DETAIL_OLD = '''            <div class="key-grid compact-grid port-main-grid phase79-last-connected" data-phase79-last-connected>
                <div class="key-item key-item-wide"><span>Identity</span><strong class="ltr" data-detail="last_connection_identity">-</strong></div>
                <div class="key-item"><span>Last Seen</span><strong class="ltr" data-detail="last_connection_observed_at">-</strong></div>
                <div class="key-item key-item-wide"><span>Neighbor</span><strong class="ltr" data-detail="last_connection_neighbor">-</strong></div>
                <div class="key-item"><span>MAC</span><strong class="ltr" data-detail="last_connection_mac">-</strong></div>
                <div class="key-item"><span>IP</span><strong class="ltr" data-detail="last_connection_ip">-</strong></div>
                <div class="key-item"><span>VLAN</span><strong class="ltr" data-detail="last_connection_vlan">-</strong></div>
                <div class="key-item"><span>Status</span><strong data-detail="last_connection_status">-</strong></div>
                <div class="key-item"><span>Source</span><strong data-detail="last_connection_source">-</strong></div>
            </div>'''
DETAIL_NEW = '''            <div class="phase79-last-connected phase79-lc-list" data-phase79-last-connected>
                <div class="phase79-lc-row phase79-lc-wide"><span>Identity</span><strong class="ltr" data-detail="last_connection_identity">-</strong></div>
                <div class="phase79-lc-row"><span>Last Seen</span><strong class="ltr" data-detail="last_connection_observed_at">-</strong></div>
                <div class="phase79-lc-row phase79-lc-wide"><span>Neighbor</span><strong class="ltr" data-detail="last_connection_neighbor">-</strong></div>
                <div class="phase79-lc-row"><span>MAC</span><strong class="ltr" data-detail="last_connection_mac">-</strong></div>
                <div class="phase79-lc-row"><span>IP</span><strong class="ltr" data-detail="last_connection_ip">-</strong></div>
                <div class="phase79-lc-row"><span>VLAN</span><strong class="ltr" data-detail="last_connection_vlan">-</strong></div>
                <div class="phase79-lc-row"><span>Status</span><strong data-detail="last_connection_status">-</strong></div>
                <div class="phase79-lc-row"><span>Source</span><strong data-detail="last_connection_source">-</strong></div>
            </div>'''


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
    if 'from django.db.models import Q' not in text:
        text = text.replace('from django.utils import timezone\n', 'from django.db.models import Q\nfrom django.utils import timezone\n')
    helper = '''\n\ndef meaningful_identity_q() -> Q:\n    return (\n        Q(connected_device__gt="")\n        | Q(neighbor_device__gt="")\n        | Q(neighbor_port__gt="")\n        | Q(neighbor_ip__isnull=False)\n        | Q(ip_address__isnull=False)\n        | Q(mac_address__gt="")\n        | Q(mac_addresses__gt="")\n        | Q(mac_count__gt=0)\n        | Q(device_type__gt="")\n        | Q(owner__gt="")\n    )\n\n\ndef history_has_identity_data(history) -> bool:\n    if not history:\n        return False\n    return any([\n        _clean(getattr(history, "connected_device", "")),\n        _clean(getattr(history, "neighbor_device", "")),\n        _clean(getattr(history, "neighbor_port", "")),\n        getattr(history, "neighbor_ip", None),\n        getattr(history, "ip_address", None),\n        _clean(getattr(history, "mac_address", "")),\n        _clean(getattr(history, "mac_addresses", "")),\n        int(getattr(history, "mac_count", 0) or 0) > 0,\n        _clean(getattr(history, "device_type", "")),\n        _clean(getattr(history, "owner", "")),\n    ])\n'''
    if 'def meaningful_identity_q() -> Q:' not in text:
        text = text.replace('def port_identity_hash(port: Port) -> str:\n', helper + '\ndef port_identity_hash(port: Port) -> str:\n')
    pattern = re.compile(r'def latest_port_connection\(port: Port\).*?\n\s*return PortConnectionHistory\.objects\.filter\(port=port\).*?\.first\(\)\n', re.S)
    replacement = '''def latest_port_connection(port: Port) -> Optional[PortConnectionHistory]:\n    return (\n        PortConnectionHistory.objects\n        .filter(port=port)\n        .filter(meaningful_identity_q())\n        .order_by("-observed_at", "-id")\n        .first()\n    )\n'''
    text2, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError('latest_port_connection function not patched')
    write(path, text2)


def patch_views() -> None:
    path = FILES['views']
    text = read(path)
    text = text.replace('from .phase79_history import latest_port_connection', 'from .phase79_history import latest_port_connection, history_has_identity_data')
    marker = '    identity = history.identity_label() if hasattr(history, "identity_label") else "-"\n'
    guard = '''    if not history_has_identity_data(history):\n        return {\n            "available": False,\n            "identity": "سابقه‌ای ثبت نشده",\n            "event_type": "-",\n            "observed_at_text": "-",\n            "last_verified_at_text": "-",\n            "neighbor": "-",\n            "neighbor_source": "-",\n            "mac": "-",\n            "ip": "-",\n            "vlan": "-",\n            "status_after": "-",\n            "source": "-",\n        }\n\n'''
    if guard.strip() not in text:
        if marker not in text:
            raise RuntimeError('views history payload marker not found')
        text = text.replace(marker, guard + marker, 1)
    write(path, text)


def patch_templates() -> None:
    p = FILES['switch_list']
    text = read(p)
    if FIELD_NEW.strip() not in text:
        if FIELD_OLD not in text:
            raise RuntimeError('switch_list last connected block not found')
        text = text.replace(FIELD_OLD, FIELD_NEW, 1)
        write(p, text)
    p = FILES['switch_detail']
    text = read(p)
    if DETAIL_NEW.strip() not in text:
        if DETAIL_OLD not in text:
            raise RuntimeError('switch_detail last connected block not found')
        text = text.replace(DETAIL_OLD, DETAIL_NEW, 1)
        write(p, text)


def patch_css_and_base() -> None:
    write(FILES['css'], CSS)
    path = FILES['base']
    text = read(path)
    if 'switchmap-phase79.css' not in text:
        raise RuntimeError('switchmap-phase79.css include not found in base.html')
    lines = []
    changed = False
    for line in text.splitlines():
        if 'switchmap-phase79.css' in line:
            prefix = line.split('?v=')[0] if '?v=' in line else line.split('switchmap-phase79.css')[0] + 'switchmap-phase79.css" %}'
            line = prefix + '?v=' + VERSION + '">'
            changed = True
        lines.append(line)
    if not changed:
        raise RuntimeError('switchmap-phase79.css include version was not changed')
    write(path, '\n'.join(lines) + ('\n' if text.endswith('\n') else ''))


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_history()
    patch_views()
    patch_templates()
    patch_css_and_base()
    print(f'PHASE79_2_3_PATCH_OK backup_dir={BACKUP_ROOT}')


if __name__ == '__main__':
    main()
