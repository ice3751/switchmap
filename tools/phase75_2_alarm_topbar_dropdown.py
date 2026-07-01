from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PHASE = "phase75_2_alarm_topbar_dropdown"
PROJECT = Path.cwd().resolve()
BACKUP_ROOT = PROJECT / "backups" / f"{PHASE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
BASE = PROJECT / "inventory" / "templates" / "inventory" / "base.html"
CSS = PROJECT / "inventory" / "static" / "inventory" / "css" / "switchmap-notifications.css"
STATIC_CSS = PROJECT / "staticfiles" / "inventory" / "css" / "switchmap-notifications.css"

MARKER_TEMPLATE = "phase75-2-alarm-dropdown"
OLD_MARKER = "phase75-1-alarm-link"
MARKER_CSS = "Phase 75.2 alarm topbar dropdown"

DROPDOWN = r'''<details class="topbar-alarm-dropdown phase75-2-alarm-dropdown {% if swmap_alarm_critical_count %}is-critical{% elif swmap_alarm_active_count %}is-warning{% endif %}" data-phase75-2-alarm-dropdown>
                    <summary class="topbar-alarm-summary" title="آلارم‌های فعال" aria-label="آلارم‌های فعال">
                        <span class="topbar-alarm-icon" aria-hidden="true">!</span>
                        <span class="topbar-alarm-text">آلارم‌ها</span>
                        <strong class="topbar-alarm-count">{{ swmap_alarm_active_count|default:"0" }}</strong>
                    </summary>
                    <div class="topbar-alarm-panel phase75-2-alarm-panel" role="menu">
                        <div class="topbar-alarm-panel-head">
                            <strong>آلارم‌های فعال</strong>
                            <small>{{ swmap_alarm_active_count|default:"0" }} مورد</small>
                        </div>
                        <div class="topbar-alarm-list">
                            {% for alarm in swmap_alarm_sidebar_items|slice:":5" %}
                                <a class="topbar-alarm-item severity-{{ alarm.severity }}" href="{% url 'inventory:alarm_center' %}?status=active#alarm-{{ alarm.id }}" role="menuitem">
                                    <span class="topbar-alarm-item-main">
                                        <b>{{ alarm.title }}</b>
                                        <small>{% if alarm.switch %}{{ alarm.switch.name }}{% else %}-{% endif %}{% if alarm.port %} · {{ alarm.port.interface_name }}{% endif %}</small>
                                    </span>
                                    <em>{{ alarm.get_severity_display }}</em>
                                </a>
                            {% empty %}
                                <div class="topbar-alarm-empty">آلارم فعالی وجود ندارد.</div>
                            {% endfor %}
                        </div>
                        <a class="topbar-alarm-all" href="{% url 'inventory:alarm_center' %}?status=active" role="menuitem">دیدن همه آلارم‌ها</a>
                    </div>
                </details>'''

CSS_SNIPPET = r'''

/* Phase 75.2 alarm topbar dropdown */
body .topbar-user.command-topbar-user{
    display:flex!important;
    flex-direction:row!important;
    align-items:center!important;
    justify-content:flex-end!important;
    gap:12px!important;
    overflow:visible!important;
    min-width:max-content!important;
    position:relative!important;
    z-index:7000!important;
}
body .topbar-user.command-topbar-user .command-user-dropdown{
    order:2!important;
    flex:0 0 auto!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link{
    display:none!important;
    visibility:hidden!important;
    opacity:0!important;
}
body .topbar-user.command-topbar-user details[data-phase75-alarm-topbar],
body .topbar-user.command-topbar-user details.alarm-mini-dropdown.nav-link-notification.command-alarm-menu{
    display:none!important;
    visibility:hidden!important;
    opacity:0!important;
    width:0!important;
    height:0!important;
    overflow:hidden!important;
}
body .topbar-user.command-topbar-user .phase75-2-alarm-dropdown,
body .phase75-2-alarm-dropdown{
    order:1!important;
    flex:0 0 auto!important;
    position:relative!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    overflow:visible!important;
    direction:rtl!important;
    z-index:7600!important;
}
body .phase75-2-alarm-dropdown > summary,
body .phase75-2-alarm-dropdown .topbar-alarm-summary{
    list-style:none!important;
    width:auto!important;
    min-width:118px!important;
    height:42px!important;
    padding:0 12px!important;
    border-radius:14px!important;
    border:1px solid rgba(255,255,255,.18)!important;
    background:rgba(59,130,246,.16)!important;
    color:#fff!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    gap:8px!important;
    cursor:pointer!important;
    white-space:nowrap!important;
    user-select:none!important;
    box-shadow:none!important;
    line-height:1!important;
}
body .phase75-2-alarm-dropdown > summary::-webkit-details-marker{display:none!important;}
body .phase75-2-alarm-dropdown.is-warning > summary{
    background:rgba(245,158,11,.18)!important;
    border-color:rgba(245,158,11,.38)!important;
}
body .phase75-2-alarm-dropdown.is-critical > summary{
    background:rgba(239,68,68,.20)!important;
    border-color:rgba(239,68,68,.42)!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-icon{
    width:22px!important;
    height:22px!important;
    min-width:22px!important;
    border-radius:999px!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    background:#f59e0b!important;
    color:#111827!important;
    font-size:13px!important;
    font-weight:950!important;
    line-height:1!important;
}
body .phase75-2-alarm-dropdown.is-critical .topbar-alarm-icon{
    background:#ef4444!important;
    color:#fff!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-text{
    color:inherit!important;
    font-size:12px!important;
    font-weight:850!important;
    line-height:1!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-count{
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    min-width:22px!important;
    height:22px!important;
    padding:0 7px!important;
    border-radius:999px!important;
    background:rgba(255,255,255,.16)!important;
    color:inherit!important;
    font-size:12px!important;
    font-weight:950!important;
    line-height:1!important;
}
body .phase75-2-alarm-dropdown .phase75-2-alarm-panel,
body .phase75-2-alarm-dropdown .topbar-alarm-panel{
    position:absolute!important;
    top:calc(100% + 12px)!important;
    right:0!important;
    left:auto!important;
    width:380px!important;
    max-width:calc(100vw - 24px)!important;
    min-width:340px!important;
    max-height:520px!important;
    overflow:auto!important;
    padding:10px!important;
    border-radius:18px!important;
    border:1px solid rgba(148,163,184,.28)!important;
    background:#ffffff!important;
    color:#0f172a!important;
    box-shadow:0 24px 60px rgba(15,23,42,.22)!important;
    z-index:9000!important;
    direction:rtl!important;
    text-align:right!important;
}
body .phase75-2-alarm-dropdown:not([open]) .phase75-2-alarm-panel{display:none!important;}
body .phase75-2-alarm-dropdown .topbar-alarm-panel-head{
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:10px!important;
    padding:7px 8px 10px!important;
    border-bottom:1px solid rgba(226,232,240,.95)!important;
    margin-bottom:8px!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-panel-head strong{
    font-size:14px!important;
    font-weight:950!important;
    color:#0f172a!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-panel-head small{
    color:#64748b!important;
    font-size:11px!important;
    font-weight:800!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-list{
    display:flex!important;
    flex-direction:column!important;
    gap:7px!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item{
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:12px!important;
    padding:10px 10px!important;
    border-radius:14px!important;
    border:1px solid rgba(226,232,240,.9)!important;
    background:#f8fafc!important;
    color:#0f172a!important;
    text-decoration:none!important;
    min-height:58px!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item:hover{
    background:#eef6ff!important;
    border-color:rgba(59,130,246,.35)!important;
    text-decoration:none!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item-main{
    display:flex!important;
    flex-direction:column!important;
    gap:5px!important;
    min-width:0!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item-main b{
    font-size:12px!important;
    font-weight:950!important;
    color:#0f172a!important;
    line-height:1.35!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    max-width:245px!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item-main small{
    font-size:11px!important;
    font-weight:750!important;
    color:#64748b!important;
    direction:ltr!important;
    text-align:left!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item em{
    font-style:normal!important;
    font-size:10px!important;
    font-weight:950!important;
    border-radius:999px!important;
    padding:5px 8px!important;
    background:#f59e0b!important;
    color:#111827!important;
    flex:0 0 auto!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-item.severity-critical em{
    background:#ef4444!important;
    color:#fff!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-empty{
    padding:18px 12px!important;
    border-radius:14px!important;
    background:#f8fafc!important;
    color:#64748b!important;
    text-align:center!important;
    font-size:12px!important;
    font-weight:800!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-all{
    margin-top:9px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    height:38px!important;
    border-radius:12px!important;
    background:#2563eb!important;
    color:#fff!important;
    text-decoration:none!important;
    font-size:12px!important;
    font-weight:950!important;
}
body .phase75-2-alarm-dropdown .topbar-alarm-all:hover{
    background:#1d4ed8!important;
    color:#fff!important;
}
@media (max-width:860px){
    body .phase75-2-alarm-dropdown > summary{min-width:58px!important;padding:0 9px!important;}
    body .phase75-2-alarm-dropdown .topbar-alarm-text{display:none!important;}
    body .phase75-2-alarm-dropdown .phase75-2-alarm-panel{right:auto!important;left:0!important;width:340px!important;min-width:300px!important;}
}
'''


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT))
    except Exception:
        return str(path)


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    target = BACKUP_ROOT / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def patch_base(changed: list[str]) -> None:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    text = read(BASE)
    original = text

    if MARKER_TEMPLATE in text:
        print("BASE_DROPDOWN_EXISTS=YES")
        # Ensure old compact link is not present beside the dropdown.
        text, old_removed = re.subn(r'\n?\s*<a\s+class="[^"]*phase75-1-alarm-link[^"]*"[^>]*>.*?</a>', "", text, flags=re.I | re.S)
        print(f"BASE_OLD_LINK_REMOVED={old_removed}")
    else:
        text, n = re.subn(r'<a\s+class="[^"]*phase75-1-alarm-link[^"]*"[^>]*>.*?</a>', DROPDOWN, text, count=1, flags=re.I | re.S)
        print(f"BASE_PHASE75_1_LINK_REPLACED={n}")
        if n == 0:
            # Replace any previous alarm details block if it still exists.
            text, n = re.subn(r'<details\s+class="[^"]*(?:alarm-mini-dropdown|phase75-alarm-topbar|command-alarm-menu)[^"]*"[^>]*>.*?</details>', DROPDOWN, text, count=1, flags=re.I | re.S)
            print(f"BASE_OLD_DETAILS_REPLACED={n}")
        if n == 0:
            # Insert before command user dropdown inside topbar-user as a last safe fallback.
            text, n = re.subn(r'(\s*<details\s+class="[^"]*command-user-dropdown[^"]*"[^>]*>)', "\n                " + DROPDOWN + r"\1", text, count=1, flags=re.I | re.S)
            print(f"BASE_INSERT_BEFORE_USER_DROPDOWN={n}")
        if n == 0:
            raise RuntimeError("Could not find alarm topbar location in base.html")

    if text != original:
        backup_file(BASE)
        write(BASE, text)
        changed.append(rel(BASE))
        print(f"PATCHED={rel(BASE)}")
    else:
        print(f"NO_TEMPLATE_CHANGE={rel(BASE)}")


def patch_css(changed: list[str]) -> None:
    if not CSS.exists():
        raise FileNotFoundError(CSS)
    text = read(CSS)
    if MARKER_CSS in text:
        print(f"SKIP_CSS_MARKER_EXISTS={rel(CSS)}")
        return
    backup_file(CSS)
    write(CSS, text.rstrip() + CSS_SNIPPET + "\n")
    changed.append(rel(CSS))
    print(f"APPENDED={rel(CSS)}")


def run(cmd: list[str], check: bool = False) -> int:
    print("RUN=" + " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(PROJECT), text=True)
    print(f"RETURN_CODE={p.returncode}")
    if check and p.returncode != 0:
        raise SystemExit(p.returncode)
    return p.returncode


def restart_waitress() -> None:
    print("WAITRESS_RESTART=TRY")
    subprocess.run(["schtasks", "/End", "/TN", "SwitchMap Waitress"], cwd=str(PROJECT), text=True)
    subprocess.run("timeout /t 3 /nobreak", cwd=str(PROJECT), text=True, shell=True)
    subprocess.run(["schtasks", "/Run", "/TN", "SwitchMap Waitress"], cwd=str(PROJECT), text=True)
    print("WAITRESS_RESTART=DONE_OR_ALREADY_RUNNING")


def apply() -> int:
    print("PHASE75_2_ALARM_TOPBAR_DROPDOWN")
    print(f"PROJECT={PROJECT}")
    print(f"BACKUP={BACKUP_ROOT}")
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    patch_base(changed)
    patch_css(changed)
    (BACKUP_ROOT / "changed_files.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
    print("CHANGED_FILES=" + str(len(changed)))
    for item in changed:
        print("CHANGED=" + item)
    run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"], check=True)
    run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "collectstatic", "--noinput", "-v", "0"], check=True)
    restart_waitress()
    print("PHASE75_2_ALARM_TOPBAR_DROPDOWN_DONE")
    return 0


def verify() -> int:
    print("PHASE75_2_ALARM_TOPBAR_DROPDOWN_VERIFY")
    print(f"PROJECT={PROJECT}")
    ok = True
    base_text = read(BASE) if BASE.exists() else ""
    css_text = read(CSS) if CSS.exists() else ""
    static_css_text = read(STATIC_CSS) if STATIC_CSS.exists() else ""
    checks = [
        ("BASE_EXISTS", BASE.exists(), True),
        ("BASE_HAS_PHASE75_2_DROPDOWN", MARKER_TEMPLATE in base_text, True),
        ("BASE_HAS_PHASE75_1_LINK", OLD_MARKER in base_text, False),
        ("BASE_HAS_SIDEBAR_ITEMS", "swmap_alarm_sidebar_items" in base_text, True),
        ("BASE_HAS_ALL_ALARMS_LINK", "دیدن همه آلارم" in base_text and "alarm_center" in base_text, True),
        ("CSS_HAS_PHASE75_2_MARKER", MARKER_CSS in css_text, True),
        ("STATIC_CSS_HAS_PHASE75_2_MARKER", MARKER_CSS in static_css_text, True),
    ]
    for name, value, expected in checks:
        print(f"CHECK::{name}={'YES' if value else 'NO'}")
        ok = ok and (bool(value) == expected)
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    ok = ok and code == 0
    print("PHASE75_2_VERIFY_RESULT=" + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        return verify()
    return apply()


if __name__ == "__main__":
    raise SystemExit(main())
