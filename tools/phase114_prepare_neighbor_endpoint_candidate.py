
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import datetime as dt
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"C:\SwitchMap")
PHASE = "PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD_CANDIDATE"
TS = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = ROOT / f"SwitchMap_Phase114_Neighbor_Endpoint_UI_Guard_CANDIDATE_{TS}"
FILES = OUT / "files"
REPORT = OUT / "report"
PREVIEW = OUT / "preview"
ZIPDIR = OUT / "zip"

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")

def copy_rel(rel: str) -> Path:
    src = ROOT / rel
    dst = FILES / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
    return dst

def make_policy_module() -> str:
    return r"""# -*- coding: utf-8 -*-
from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict

_GATEWAY_EXACT = {"172.16.25.1"}

_NETWORK_DEVICE_HINTS = (
    "switch", "router", "gateway", "core", "nexus", "crs", "rb", "mikrotik",
    "cap", "ap", "access point", "uplink", "downlink", "trunk",
)

_UPLINK_HINTS = (
    "uplink", "downlink", "trunk", "core", "crs", "nexus", "fiber", "sfp",
    "ethernet1/40", "eth1/40", "et1/40", "sfp-sfpplus", "te", "tengig",
)

def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _low(value: Any) -> str:
    return _txt(value).lower()

def _int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(value)
    except Exception:
        return default

def _get(obj: Any, name: str, default: Any = "") -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default

def _switch(port: Any) -> Any:
    return _get(port, "switch", None)

def _switch_role(port: Any) -> str:
    return _low(_get(_switch(port), "device_role", ""))

def _switch_family(port: Any) -> str:
    return _low(_get(_switch(port), "device_family", ""))

def _switch_name(port: Any) -> str:
    return _txt(_get(_switch(port), "name", ""))

def _port_text(port: Any) -> str:
    fields = [
        "interface_name", "snmp_raw_name", "description", "connected_device",
        "neighbor_device", "neighbor_port", "snmp_alias", "port_mode",
    ]
    return " ".join(_low(_get(port, f, "")) for f in fields)

def _mac_list_count(port: Any) -> int:
    raw = _txt(_get(port, "mac_addresses", ""))
    if not raw:
        return 0
    parts = [p for p in re.split(r"[\\s,;|]+", raw) if p.strip()]
    return len(set(parts))

def mac_count(port: Any) -> int:
    return max(_int(_get(port, "mac_count", 0)), _mac_list_count(port))

def is_gateway_ip(value: Any) -> bool:
    ip = _txt(value)
    if not ip:
        return False
    if ip in _GATEWAY_EXACT:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return False
    return addr.version == 4 and ip.endswith(".1")

def is_uplink_or_trunk(port: Any) -> bool:
    mode = _low(_get(port, "port_mode", ""))
    if mode == "trunk":
        return True
    text = _port_text(port)
    return any(h in text for h in _UPLINK_HINTS)

def is_ap_port_context(port: Any) -> bool:
    role = _switch_role(port)
    family = _switch_family(port)
    name = _low(_switch_name(port))
    text = _port_text(port)
    return (
        "access_point" in role
        or "ap" in family
        or name.startswith("cap")
        or "cap-" in name
        or "access point" in text
    )

def is_network_device_neighbor(port: Any) -> bool:
    nd = _low(_get(port, "neighbor_device", ""))
    np = _low(_get(port, "neighbor_port", ""))
    return any(h in (nd + " " + np) for h in _NETWORK_DEVICE_HINTS)

def classify_port_connection_display(port: Any) -> Dict[str, Any]:
    ip = _txt(_get(port, "ip_address", ""))
    neighbor = _txt(_get(port, "neighbor_device", ""))
    count = mac_count(port)
    uplink = is_uplink_or_trunk(port)
    ap_ctx = is_ap_port_context(port)
    gateway = is_gateway_ip(ip)
    network_neighbor = is_network_device_neighbor(port)

    if ap_ctx and count > 1:
        return {"type": "behind_ap", "direct": False, "label": f"Behind AP / Multi-MAC ({count})", "reason": "AP context with multiple MAC addresses", "confidence": 95}
    if gateway and count > 1:
        return {"type": "gateway_arp_observed", "direct": False, "label": f"Gateway ARP observed / Behind network ({ip}, MACs={count})", "reason": "Gateway IP on a multi-MAC port is not a direct endpoint", "confidence": 95}
    if uplink and count > 1:
        return {"type": "behind_trunk", "direct": False, "label": f"Behind trunk/uplink ({count} MACs)", "reason": "Uplink/trunk with multiple MAC addresses", "confidence": 90}
    if neighbor and count > 8 and network_neighbor:
        return {"type": "physical_neighbor_conflict", "direct": False, "label": f"Network neighbor evidence / Aggregate behind link ({count} MACs)", "reason": "Neighbor is a network device but FDB shows many MACs behind the link", "confidence": 85}
    if count > 1:
        return {"type": "multi_mac_aggregate", "direct": False, "label": f"Aggregate / Multi-MAC ({count})", "reason": "Multiple MAC addresses on one port", "confidence": 80}
    if gateway:
        return {"type": "gateway_arp_observed", "direct": False, "label": f"Gateway ARP observed ({ip})", "reason": "Gateway IP should not be shown as direct endpoint", "confidence": 90}
    if neighbor:
        return {"type": "physical_neighbor", "direct": True, "label": neighbor, "reason": "Single physical neighbor evidence", "confidence": 70}
    return {"type": "direct_or_unknown", "direct": True, "label": _txt(_get(port, "connected_device", "")) or ip or _txt(_get(port, "mac_address", "")), "reason": "No guard condition matched", "confidence": 50}

def apply_port_connection_display_guard(port: Any, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = dict(payload or {})
    cls = classify_port_connection_display(port)
    data["phase114_display_guard"] = True
    data["current_connection_type"] = cls["type"]
    data["current_connection_direct"] = cls["direct"]
    data["current_connection_label"] = cls["label"]
    data["current_connection_reason"] = cls["reason"]
    data["current_connection_confidence"] = cls["confidence"]
    if not cls["direct"]:
        for key in ("current_connected_device", "current_device", "current_device_name", "connected_device_label", "display_connected_device"):
            if key in data:
                data[key] = cls["label"]
        data.setdefault("current_connected_device", cls["label"])
        data.setdefault("display_connected_device", cls["label"])
        data["direct_device"] = False
        data["direct_endpoint"] = False
    return data
"""

def patch_urls(text: str) -> tuple[str, list[str]]:
    changes = []
    if 'name="endpoint_search_page"' not in text and 'name="endpoint_search"' in text:
        old = 'path("endpoints/", view_required(endpoint_views.endpoint_search_view), name="endpoint_search"),'
        new = old + '\n    path("endpoints/", view_required(endpoint_views.endpoint_search_view), name="endpoint_search_page"),  # Phase114 URL alias'
        if old in text:
            text = text.replace(old, new, 1)
            changes.append("endpoint_search_page alias added")
        else:
            changes.append("endpoint_search_page alias NOT added: pattern missing")
    if 'name="endpoint_search_export_csv"' not in text and 'name="endpoint_export_csv"' in text:
        old = 'path("endpoints/export.csv", view_required(endpoint_views.endpoint_export_csv_view), name="endpoint_export_csv"),'
        new = old + '\n    path("endpoints/export.csv", view_required(endpoint_views.endpoint_export_csv_view), name="endpoint_search_export_csv"),  # Phase114 URL alias'
        if old in text:
            text = text.replace(old, new, 1)
            changes.append("endpoint_search_export_csv alias added")
        else:
            changes.append("endpoint_search_export_csv alias NOT added: pattern missing")
    return text, changes

def patch_views(text: str) -> tuple[str, list[str]]:
    changes = []
    if "PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD" in text:
        return text, ["views already contains Phase114 marker"]
    marker = """
# PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD_START
try:
    from inventory.endpoint_display_policy import apply_port_connection_display_guard
except Exception:
    apply_port_connection_display_guard = None
# PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD_END
"""
    matches = list(re.finditer(r"^(from\s+\S+\s+import\s+.+|import\s+\S+.*)$", text, re.M))
    import_pos = matches[-1].end() if matches else 0
    text = text[:import_pos] + "\n" + marker + text[import_pos:]
    changes.append("Phase114 policy import block added")
    wrapper = """
# PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD_WRAPPER_START
try:
    _phase114_original_phase79_current_connection_payload = _phase79_current_connection_payload

    def _phase79_current_connection_payload(port):
        payload = _phase114_original_phase79_current_connection_payload(port)
        if apply_port_connection_display_guard is None:
            return payload
        return apply_port_connection_display_guard(port, payload)
except NameError:
    pass
# PHASE114_NEIGHBOR_ENDPOINT_UI_GUARD_WRAPPER_END
"""
    text += "\n\n" + wrapper
    changes.append("Phase114 wrapper appended for _phase79_current_connection_payload")
    return text, changes

def make_preview_html() -> str:
    return """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>Phase114 Preview</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#f5f7fb;color:#172033;margin:24px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(260px,1fr));gap:16px}
.card{background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:16px;box-shadow:0 8px 24px rgba(15,23,42,.06)}
.bad{border-color:#fecaca;background:#fff7f7}
.warn{border-color:#fde68a;background:#fffdf3}
.ok{border-color:#bbf7d0;background:#f7fff9}
h2{font-size:16px;margin:0 0 10px}
.k{color:#64748b;font-size:12px}
.v{font:14px Consolas,monospace;direction:ltr;text-align:left;background:#f8fafc;border-radius:8px;padding:8px;margin-top:6px}
.tag{display:inline-block;border-radius:999px;padding:4px 10px;font-size:12px;margin:4px;background:#e2e8f0}
</style>
</head>
<body>
<h1>Phase114 Neighbor / Endpoint Display Guard Preview</h1>
<div class="grid">
  <div class="card bad"><h2>Cap-Managment / ether1</h2><div class="k">قبل: 172.16.25.1 به عنوان دستگاه متصل</div><div class="v">ip=172.16.25.1 | mac_count=22</div><span class="tag">بعد: Gateway ARP observed / Behind network</span></div>
  <div class="card ok"><h2>CRS354 / ether47</h2><div class="k">همسایه فیزیکی معتبرتر</div><div class="v">neighbor=CAP-XL-Managment / Bridge/ether1</div><span class="tag">بعد: Physical Neighbor</span></div>
  <div class="card warn"><h2>NEXUS / Ethernet1/40</h2><div class="k">قبل: CAP به عنوان Neighbor قطعی</div><div class="v">alias=DOWNLINK-TO-CRS | mac_count=40</div><span class="tag">بعد: Network neighbor evidence / Aggregate behind link</span></div>
</div>
</body>
</html>
"""

def main() -> int:
    for d in (FILES, REPORT, PREVIEW, ZIPDIR):
        d.mkdir(parents=True, exist_ok=True)

    result = {"phase": PHASE, "timestamp": TS, "root": str(ROOT), "out": str(OUT), "NO_LIVE_CHANGE_DONE": True, "DB_MUTATION": "NO", "SERVICE_RESTART": "NO", "MIGRATION_WRITE": "NO", "SSH_EXECUTION": "NO", "BACKUP_WRITE": "NO", "changes": [], "errors": []}

    write_text(FILES / "inventory/endpoint_display_policy.py", make_policy_module())
    result["changes"].append("candidate inventory/endpoint_display_policy.py created")

    urls_dst = copy_rel("inventory/urls.py")
    if urls_dst.exists():
        urls_text, changes = patch_urls(read_text(urls_dst))
        write_text(urls_dst, urls_text)
        result["changes"].extend(changes)
    else:
        result["errors"].append("inventory/urls.py not found")

    views_dst = copy_rel("inventory/views.py")
    if views_dst.exists():
        views_text, changes = patch_views(read_text(views_dst))
        write_text(views_dst, views_text)
        result["changes"].extend(changes)
    else:
        result["errors"].append("inventory/views.py not found")

    for rel in ["inventory/static/inventory/switchmap.js", "inventory/templates/inventory/switch_list.html"]:
        copy_rel(rel)

    py_checks = {}
    for rel in ["inventory/endpoint_display_policy.py", "inventory/urls.py", "inventory/views.py"]:
        path = FILES / rel
        if path.exists():
            try:
                ast.parse(read_text(path), filename=str(path))
                py_checks[rel] = "OK"
            except SyntaxError as e:
                py_checks[rel] = f"SYNTAX_ERROR line={e.lineno} {e.msg}"
    result["python_syntax"] = py_checks

    write_text(PREVIEW / "phase114_neighbor_endpoint_preview.html", make_preview_html())
    md = f"""# {PHASE}

Candidate folder: `{OUT}`

Prepared files:
- `files\\inventory\\endpoint_display_policy.py`
- `files\\inventory\\views.py`
- `files\\inventory\\urls.py`

Reference copies:
- `files\\inventory\\static\\inventory\\switchmap.js`
- `files\\inventory\\templates\\inventory\\switch_list.html`

Safety:
NO_LIVE_CHANGE_DONE=True
DB_MUTATION=NO
SERVICE_RESTART=NO
MIGRATION_WRITE=NO
RESTORE_ENABLE_CHANGE=NO
SSH_EXECUTION=NO
BACKUP_WRITE=NO
VISIBLE_TEST_DATA_CREATED=NO
REPORT_ONLY_AND_CANDIDATE_FILES=YES
"""
    write_text(REPORT / "phase114_candidate_report.md", md)
    write_text(REPORT / "phase114_candidate_result.json", json.dumps(result, ensure_ascii=False, indent=2))

    package = ZIPDIR / "SwitchMap_Phase114_Neighbor_Endpoint_UI_Guard_CANDIDATE.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob("*"):
            if p.is_file() and package not in p.parents and p != package:
                z.write(p, p.relative_to(OUT))

    print(PHASE)
    print(f"CANDIDATE_FOLDER={OUT}")
    print(f"PREVIEW_HTML={PREVIEW / 'phase114_neighbor_endpoint_preview.html'}")
    print(f"REPORT={REPORT / 'phase114_candidate_report.md'}")
    print(f"ZIP={package}")
    print("NO_LIVE_CHANGE_DONE=True")
    print("DB_MUTATION=NO")
    print("SERVICE_RESTART=NO")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
