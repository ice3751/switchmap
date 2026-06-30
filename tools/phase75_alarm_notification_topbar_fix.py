from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PHASE = "phase75_alarm_notification_topbar_fix"
PROJECT = Path.cwd().resolve()
BACKUP_ROOT = PROJECT / "backups" / f"{PHASE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
BASE = PROJECT / "inventory" / "templates" / "inventory" / "base.html"
CSS_PHASE = PROJECT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase43-47.css"
CSS_STATIC_PHASE = PROJECT / "staticfiles" / "inventory" / "css" / "switchmap-phase43-47.css"

MARKER_TEMPLATE = "phase75-alarm-topbar"
MARKER_CSS = "Phase 75 alarm notification compact topbar fix"

CSS_SNIPPET = r'''

/* Phase 75 alarm notification compact topbar fix */
body .app-topbar.command-topbar,
body .modern-app-frame,
body .command-topbar-user,
body .topbar-user.command-topbar-user{
    overflow:visible!important;
}
body .topbar-user.command-topbar-user{
    display:flex!important;
    flex-direction:row!important;
    align-items:center!important;
    justify-content:flex-end!important;
    gap:12px!important;
    min-width:max-content!important;
    height:auto!important;
    position:relative!important;
    z-index:5000!important;
}
body .topbar-user.command-topbar-user .command-user-dropdown{
    order:1!important;
    flex:0 0 auto!important;
    position:relative!important;
    z-index:5002!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu.alarm-mini-dropdown,
body .topbar-user.command-topbar-user details.command-alarm-menu,
body .topbar-user.command-topbar-user details.alarm-mini-dropdown.nav-link-notification{
    order:2!important;
    flex:0 0 46px!important;
    width:46px!important;
    min-width:46px!important;
    max-width:46px!important;
    height:46px!important;
    min-height:46px!important;
    max-height:46px!important;
    margin:0!important;
    padding:0!important;
    border:0!important;
    background:transparent!important;
    box-shadow:none!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    align-content:center!important;
    position:relative!important;
    overflow:visible!important;
    z-index:5003!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip,
body .topbar-user.command-topbar-user .command-alarm-menu>summary.alarm-mini-summary,
body .topbar-user.command-topbar-user .command-alarm-menu .alarm-mini-summary{
    width:46px!important;
    height:46px!important;
    min-width:46px!important;
    min-height:46px!important;
    max-width:46px!important;
    max-height:46px!important;
    margin:0!important;
    padding:0!important;
    border:0!important;
    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    place-items:center!important;
    grid-template-columns:1fr!important;
    gap:0!important;
    border-radius:999px!important;
    background:#f59e0b!important;
    color:#111827!important;
    font-size:13px!important;
    line-height:46px!important;
    font-weight:950!important;
    text-align:center!important;
    letter-spacing:0!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    cursor:pointer!important;
    box-shadow:0 12px 26px rgba(245,158,11,.30)!important;
    transform:none!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip.is-critical,
body .topbar-user.command-topbar-user .command-alarm-menu>summary.alarm-mini-summary.is-critical,
body .topbar-user.command-topbar-user .command-alarm-menu .alarm-mini-summary.is-critical{
    background:#ef4444!important;
    color:#fff!important;
    box-shadow:0 12px 30px rgba(239,68,68,.32)!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip::before,
body .topbar-user.command-topbar-user .command-alarm-menu>summary.notification-chip::after,
body .topbar-user.command-topbar-user .command-alarm-menu>summary.alarm-mini-summary::before,
body .topbar-user.command-topbar-user .command-alarm-menu>summary.alarm-mini-summary::after{
    display:none!important;
    content:""!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel,
body .topbar-user.command-topbar-user .alarm-mini-panel{
    position:absolute!important;
    top:calc(100% + 12px)!important;
    right:0!important;
    left:auto!important;
    width:300px!important;
    min-width:300px!important;
    max-width:min(340px,calc(100vw - 24px))!important;
    margin:0!important;
    padding:14px!important;
    border-radius:18px!important;
    background:#fff!important;
    color:#0f172a!important;
    border:1px solid #dbe7f5!important;
    box-shadow:0 24px 55px rgba(15,23,42,.28)!important;
    z-index:6500!important;
    display:grid!important;
    gap:10px!important;
    text-align:right!important;
    visibility:visible!important;
    opacity:1!important;
}
body .topbar-user.command-topbar-user .command-alarm-menu:not([open]) .command-alarm-panel,
body .topbar-user.command-topbar-user .command-alarm-menu:not([open]) .alarm-mini-panel{
    display:none!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel strong,
body .topbar-user.command-topbar-user .alarm-mini-panel strong{
    display:block!important;
    font-size:14px!important;
    font-weight:900!important;
    color:#0f172a!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel a,
body .topbar-user.command-topbar-user .alarm-mini-panel a{
    min-height:38px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    border-radius:12px!important;
    background:#eff6ff!important;
    color:#1d4ed8!important;
    font-size:13px!important;
    font-weight:850!important;
    text-decoration:none!important;
}
body .topbar-user.command-topbar-user .command-alarm-panel a:hover,
body .topbar-user.command-topbar-user .alarm-mini-panel a:hover{
    background:#dbeafe!important;
}
@media (max-width:760px){
    body .topbar-user.command-topbar-user .command-alarm-panel,
    body .topbar-user.command-topbar-user .alarm-mini-panel{
        right:auto!important;
        left:0!important;
        width:min(300px,calc(100vw - 24px))!important;
        min-width:0!important;
    }
}
'''


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT))
    except Exception:
        return str(path)


def backup(path: Path) -> None:
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
    if MARKER_TEMPLATE not in text:
        text = text.replace(
            '<details class="alarm-mini-dropdown nav-link-notification command-alarm-menu">',
            '<details class="alarm-mini-dropdown nav-link-notification command-alarm-menu phase75-alarm-topbar" data-phase75-alarm-topbar>',
            1,
        )
        text = text.replace(
            '<summary class="notification-chip alarm-mini-summary {% if swmap_alarm_critical_count %}is-critical{% endif %}" title="Notifications">',
            '<summary class="notification-chip alarm-mini-summary {% if swmap_alarm_critical_count %}is-critical{% endif %}" title="آلارم‌های فعال" aria-label="آلارم‌های فعال">',
            1,
        )
    if text != original:
        backup(BASE)
        write(BASE, text)
        changed.append(rel(BASE))
        print(f"PATCHED={rel(BASE)}")
    else:
        print(f"NO_TEMPLATE_CHANGE={rel(BASE)}")


def patch_css(changed: list[str]) -> None:
    if not CSS_PHASE.exists():
        raise FileNotFoundError(CSS_PHASE)
    text = read(CSS_PHASE)
    if MARKER_CSS in text:
        print(f"SKIP_MARKER_EXISTS={rel(CSS_PHASE)}")
        return
    backup(CSS_PHASE)
    write(CSS_PHASE, text.rstrip() + CSS_SNIPPET + "\n")
    changed.append(rel(CSS_PHASE))
    print(f"APPENDED={rel(CSS_PHASE)}")


def run(cmd: list[str]) -> int:
    print("RUN=" + " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(PROJECT), text=True)
    print(f"RETURN_CODE={completed.returncode}")
    return completed.returncode


def apply() -> int:
    print("PHASE75_ALARM_NOTIFICATION_TOPBAR_FIX")
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
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    if code != 0:
        return code
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "collectstatic", "--noinput", "-v", "0"])
    if code != 0:
        return code
    print("PHASE75_ALARM_NOTIFICATION_TOPBAR_FIX_DONE")
    return 0


def verify() -> int:
    print("PHASE75_ALARM_NOTIFICATION_TOPBAR_VERIFY")
    print(f"PROJECT={PROJECT}")
    ok = True
    checks = [
        (BASE, MARKER_TEMPLATE),
        (CSS_PHASE, MARKER_CSS),
        (CSS_STATIC_PHASE, MARKER_CSS),
    ]
    for path, marker in checks:
        exists = path.exists()
        has = exists and marker in read(path)
        print(f"CHECK::{rel(path)}::EXISTS={'YES' if exists else 'NO'}::HAS_MARKER={'YES' if has else 'NO'}")
        ok = ok and has
    code = run([str(PROJECT / "venv" / "Scripts" / "python.exe"), "manage.py", "check"])
    ok = ok and code == 0
    print("PHASE75_VERIFY_RESULT=" + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        return verify()
    return apply()


if __name__ == "__main__":
    raise SystemExit(main())
