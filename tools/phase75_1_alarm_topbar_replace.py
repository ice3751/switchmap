from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PHASE = "phase75_1_alarm_topbar_replace"
PROJECT = Path.cwd().resolve()
BACKUP_ROOT = PROJECT / "backups" / f"{PHASE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
BASE = PROJECT / "inventory" / "templates" / "inventory" / "base.html"
CSS_NOTIF = PROJECT / "inventory" / "static" / "inventory" / "css" / "switchmap-notifications.css"
CSS_NOTIF_STATIC = PROJECT / "staticfiles" / "inventory" / "css" / "switchmap-notifications.css"

MARKER_TEMPLATE = "phase75-1-alarm-link"
MARKER_CSS = "Phase 75.1 alarm topbar final compact link"

ALARM_LINK = '''<a class="topbar-alarm-link phase75-1-alarm-link {% if swmap_alarm_critical_count %}is-critical{% elif swmap_alarm_active_count %}is-warning{% endif %}" href="{% url 'inventory:alarm_center' %}?status=active" title="آلارم‌های فعال" aria-label="آلارم‌های فعال">
                    <span class="topbar-alarm-icon" aria-hidden="true">!</span>
                    <span class="topbar-alarm-text">آلارم‌ها</span>
                    <strong class="topbar-alarm-count">{{ swmap_alarm_active_count|default:"0" }}</strong>
                </a>'''

CSS_SNIPPET = r'''

/* Phase 75.1 alarm topbar final compact link */
body .topbar-user.command-topbar-user{
    display:flex!important;
    flex-direction:row!important;
    align-items:center!important;
    justify-content:flex-end!important;
    gap:12px!important;
    overflow:visible!important;
    min-width:max-content!important;
    height:auto!important;
    position:relative!important;
    z-index:5100!important;
}
body .topbar-user.command-topbar-user .command-user-dropdown{
    order:1!important;
    flex:0 0 auto!important;
}
body .topbar-user.command-topbar-user details[data-phase75-alarm-topbar],
body .topbar-user.command-topbar-user details.phase75-alarm-topbar,
body .topbar-user.command-topbar-user details.alarm-mini-dropdown.nav-link-notification.command-alarm-menu{
    display:none!important;
    visibility:hidden!important;
    opacity:0!important;
    width:0!important;
    height:0!important;
    min-width:0!important;
    min-height:0!important;
    max-width:0!important;
    max-height:0!important;
    margin:0!important;
    padding:0!important;
    overflow:hidden!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link,
body .phase75-1-alarm-link{
    order:2!important;
    flex:0 0 auto!important;
    width:auto!important;
    min-width:74px!important;
    max-width:160px!important;
    height:42px!important;
    min-height:42px!important;
    max-height:42px!important;
    margin:0!important;
    padding:0 11px!important;
    border-radius:14px!important;
    border:1px solid rgba(255,255,255,.18)!important;
    background:rgba(59,130,246,.16)!important;
    color:#fff!important;
    box-shadow:none!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    gap:7px!important;
    position:static!important;
    inset:auto!important;
    transform:none!important;
    text-decoration:none!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    line-height:1!important;
    vertical-align:middle!important;
    cursor:pointer!important;
    direction:rtl!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link.is-warning,
body .phase75-1-alarm-link.is-warning{
    background:rgba(245,158,11,.18)!important;
    border-color:rgba(245,158,11,.34)!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link.is-critical,
body .phase75-1-alarm-link.is-critical{
    background:rgba(239,68,68,.20)!important;
    border-color:rgba(239,68,68,.38)!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link:hover,
body .phase75-1-alarm-link:hover{
    background:rgba(59,130,246,.26)!important;
    text-decoration:none!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link .topbar-alarm-icon,
body .phase75-1-alarm-link .topbar-alarm-icon{
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
body .topbar-user.command-topbar-user .phase75-1-alarm-link.is-critical .topbar-alarm-icon,
body .phase75-1-alarm-link.is-critical .topbar-alarm-icon{
    background:#ef4444!important;
    color:#fff!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link .topbar-alarm-text,
body .phase75-1-alarm-link .topbar-alarm-text{
    display:inline!important;
    color:inherit!important;
    font-size:12px!important;
    font-weight:850!important;
    line-height:1!important;
}
body .topbar-user.command-topbar-user .phase75-1-alarm-link .topbar-alarm-count,
body .phase75-1-alarm-link .topbar-alarm-count{
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    min-width:20px!important;
    height:20px!important;
    padding:0 6px!important;
    border-radius:999px!important;
    background:rgba(255,255,255,.16)!important;
    color:inherit!important;
    font-size:12px!important;
    font-weight:950!important;
    line-height:1!important;
}
@media (max-width:860px){
    body .topbar-user.command-topbar-user .phase75-1-alarm-link .topbar-alarm-text,
    body .phase75-1-alarm-link .topbar-alarm-text{
        display:none!important;
    }
    body .topbar-user.command-topbar-user .phase75-1-alarm-link,
    body .phase75-1-alarm-link{
        min-width:58px!important;
        padding:0 9px!important;
    }
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

    # If the final link already exists, do not duplicate it.
    if MARKER_TEMPLATE not in text:
        patterns = [
            r'\n?\s*<details\s+class="[^"]*alarm-mini-dropdown[^"]*command-alarm-menu[^"]*"[^>]*>.*?</details>',
            r'\n?\s*<details\s+class="[^"]*command-alarm-menu[^"]*alarm-mini-dropdown[^"]*"[^>]*>.*?</details>',
        ]
        replaced = 0
        for pattern in patterns:
            text, n = re.subn(pattern, "\n                " + ALARM_LINK, text, count=1, flags=re.IGNORECASE | re.DOTALL)
            replaced += n
            if n:
                break
        if replaced == 0:
            # Fallback: insert after user dropdown block if no details block is found.
            text, inserted = re.subn(
                r'(</details>\s*\n\s*</div>\s*\n\s*</header>)',
                "</details>\n                " + ALARM_LINK + "\n            </div>\n        </header>",
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
            replaced += inserted
        print(f"BASE_ALARM_BLOCK_REPLACED={replaced}")
    else:
        # Remove any old details left beside the new link.
        text, removed = re.subn(
            r'\n?\s*<details\s+class="[^"]*alarm-mini-dropdown[^"]*command-alarm-menu[^"]*"[^>]*>.*?</details>',
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        print(f"BASE_OLD_ALARM_DETAILS_REMOVED={removed}")

    if text != original:
        backup_file(BASE)
        write(BASE, text)
        changed.append(rel(BASE))
        print(f"PATCHED={rel(BASE)}")
    else:
        print(f"NO_TEMPLATE_CHANGE={rel(BASE)}")


def patch_css(changed: list[str]) -> None:
    if not CSS_NOTIF.exists():
        raise FileNotFoundError(CSS_NOTIF)
    text = read(CSS_NOTIF)
    if MARKER_CSS in text:
        print(f"SKIP_CSS_MARKER_EXISTS={rel(CSS_NOTIF)}")
        return
    backup_file(CSS_NOTIF)
    write(CSS_NOTIF, text.rstrip() + CSS_SNIPPET + "\n")
    changed.append(rel(CSS_NOTIF))
    print(f"APPENDED={rel(CSS_NOTIF)}")


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
    subprocess.run(["timeout", "/t", "3", "/nobreak"], cwd=str(PROJECT), text=True, shell=True)
    subprocess.run(["schtasks", "/Run", "/TN", "SwitchMap Waitress"], cwd=str(PROJECT), text=True)
    print("WAITRESS_RESTART=DONE_OR_ALREADY_RUNNING")


def apply() -> int:
    print("PHASE75_1_ALARM_TOPBAR_REPLACE")
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
    print("PHASE75_1_ALARM_TOPBAR_REPLACE_DONE")
    return 0


def verify() -> int:
    print("PHASE75_1_ALARM_TOPBAR_VERIFY")
    print(f"PROJECT={PROJECT}")
    ok = True
    base_text = read(BASE) if BASE.exists() else ""
    css_text = read(CSS_NOTIF) if CSS_NOTIF.exists() else ""
    static_css_text = read(CSS_NOTIF_STATIC) if CSS_NOTIF_STATIC.exists() else ""
    checks = [
        ("BASE_EXISTS", BASE.exists()),
        ("BASE_HAS_FINAL_LINK", MARKER_TEMPLATE in base_text),
        ("BASE_HAS_OLD_ALARM_DETAILS", "data-phase75-alarm-topbar" in base_text or "alarm-mini-dropdown nav-link-notification command-alarm-menu" in base_text),
        ("CSS_HAS_MARKER", MARKER_CSS in css_text),
        ("STATIC_CSS_HAS_MARKER", MARKER_CSS in static_css_text),
    ]
    for name, value in checks:
        if name == "BASE_HAS_OLD_ALARM_DETAILS":
            print(f"CHECK::{name}={'YES' if value else 'NO'}")
            ok = ok and (not value)
        else:
            print(f"CHECK::{name}={'YES' if value else 'NO'}")
            ok = ok and bool(value)
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    ok = ok and code == 0
    print("PHASE75_1_VERIFY_RESULT=" + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        return verify()
    return apply()


if __name__ == "__main__":
    raise SystemExit(main())
