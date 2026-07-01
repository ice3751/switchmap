from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CSS_BLOCK = r'''
/* Phase 64: dashboard usability compact decision layout */
.dashboard-insight-shell{gap:12px;max-width:1500px;margin-inline:auto;}
.dashboard-live-meta{min-height:auto;padding:10px 14px;justify-content:space-between;border-radius:16px;}
.dashboard-live-meta small{font-size:12px;}
.insight-executive-card{grid-template-columns:minmax(0,1fr) minmax(280px,360px);gap:14px;min-height:auto;padding:18px 22px;border-radius:22px;box-shadow:0 12px 30px rgba(15,31,53,.06);}
.insight-executive-card h2{font-size:24px;margin:4px 0 6px;line-height:1.35;}
.insight-executive-card p{font-size:13px;line-height:1.75;}
.insight-label{padding:6px 10px;font-size:11px;}
.insight-action-box{padding:14px;border-radius:16px;}
.insight-action-box strong{font-size:15px;line-height:1.6;}
.insight-action-box small{font-size:12px;line-height:1.65;}
.insight-kpi-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;}
.insight-kpi-card{min-height:86px;padding:12px 14px;border-radius:18px;box-shadow:0 8px 20px rgba(15,31,53,.05);}
.insight-kpi-card span{font-size:11px;margin-bottom:8px;}
.insight-kpi-card strong{font-size:28px;}
.insight-kpi-card small{font-size:11px;line-height:1.55;margin-top:7px;}
.insight-health-grid{grid-template-columns:minmax(0,.85fr) minmax(0,.85fr) minmax(0,1.1fr);gap:12px;align-items:stretch;}
.insight-panel{padding:14px 16px;border-radius:20px;box-shadow:0 10px 24px rgba(15,31,53,.05);}
.insight-panel header{margin-bottom:10px;}
.insight-panel header strong{font-size:16px;}
.insight-panel header span{font-size:11px;line-height:1.55;}
.insight-ring{width:116px;height:116px;margin:0 auto 8px;}
.insight-ring:after{inset:12px;}
.insight-ring strong{font-size:24px;}
.insight-ring small{margin-top:30px;font-size:10px;}
.coverage-score strong{font-size:38px;}
.coverage-bar{height:10px;margin:12px 0 8px;}
.background-status-line{padding:12px;border-radius:14px;margin-bottom:8px;}
.insight-workbench-grid{grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);gap:12px;align-items:start;}
.action-panel .action-list{max-height:430px;overflow:auto;padding-left:4px;}
.action-item,.live-alarm{padding:12px;border-radius:15px;gap:6px;}
.action-item div{gap:8px;}
.action-item p,.action-item span,.live-alarm span{font-size:13px;line-height:1.55;}
.action-item small,.live-alarm small{font-size:11px;}
.notification-panel-live{min-height:0;align-self:start;}
.notification-panel-live .live-alarm-list{max-height:260px;overflow:auto;}
.notification-panel-live .modern-empty-state{min-height:86px;display:grid;place-items:center;border-radius:14px;}
.refresh-results-panel:empty{display:none;}
.device-browser-shell{margin-top:10px;}
.device-browser-shell>summary{min-height:42px;}
.insight-advanced{margin-top:4px;}
.insight-advanced>summary{padding:12px 14px;}
.advanced-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:12px;}
@media(max-width:1280px){.insight-kpi-grid{grid-template-columns:repeat(3,minmax(0,1fr));}.insight-health-grid,.insight-workbench-grid,.insight-executive-card{grid-template-columns:1fr;}}
@media(max-width:760px){.insight-kpi-grid{grid-template-columns:1fr 1fr;}.insight-kpi-card{min-height:82px}.insight-executive-card{padding:16px}.insight-workbench-grid{grid-template-columns:1fr;}.action-panel .action-list{max-height:none;}}
'''.strip()

TEMPLATE_MARKER = '<span hidden data-phase64-marker="dashboard-usability-compact">Phase 64 Dashboard Usability Compact</span>'


def replace_marked_block(text: str, start_marker: str, block: str) -> str:
    idx = text.find(start_marker)
    if idx == -1:
        return text.rstrip() + "\n\n" + block + "\n"
    next_idx = text.find("\n/* Phase ", idx + len(start_marker))
    if next_idx == -1:
        return text[:idx].rstrip() + "\n" + block + "\n"
    return text[:idx].rstrip() + "\n" + block + "\n" + text[next_idx:].lstrip()


def patch_css(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing css file: {path}")
    text = path.read_text(encoding="utf-8")
    updated = replace_marked_block(text, "/* Phase 64: dashboard usability compact decision layout */", CSS_BLOCK)
    path.write_text(updated, encoding="utf-8")


def patch_template(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing template file: {path}")
    text = path.read_text(encoding="utf-8")
    if TEMPLATE_MARKER in text:
        return
    anchor = '<span hidden data-phase63-marker="dashboard-live-insight">Phase 63 Live Insight Dashboard</span>'
    if anchor in text:
        text = text.replace(anchor, anchor + "\n    " + TEMPLATE_MARKER, 1)
    else:
        close = '</section>\n\n<section class="surface-card refresh-results-panel"'
        if close in text:
            text = text.replace(close, '    ' + TEMPLATE_MARKER + '\n' + close, 1)
        else:
            text = text.rstrip() + "\n" + TEMPLATE_MARKER + "\n"
    path.write_text(text, encoding="utf-8")


def patch_manifest(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    test = "smoke_tests/switchmap_64_dashboard_usability_smoke_test.py"
    data.setdefault("phase64", [])
    if test not in data["phase64"]:
        data["phase64"].append(test)
    data.setdefault("current", [])
    if test not in data["current"]:
        data["current"].append(test)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    patch_css(ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase42.css")
    static_css = ROOT / "staticfiles" / "inventory" / "css" / "switchmap-phase42.css"
    if static_css.exists():
        patch_css(static_css)
    patch_template(ROOT / "inventory" / "templates" / "inventory" / "switch_list.html")
    patch_manifest(ROOT / "smoke_tests" / "manifest.json")
    print("PHASE64_COMPACT_UX_REPAIR_OK")


if __name__ == "__main__":
    main()
