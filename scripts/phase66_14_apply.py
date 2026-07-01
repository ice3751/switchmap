
from pathlib import Path
from datetime import datetime
import shutil, subprocess, re

PROJECT = Path(r"C:\SwitchMap")
PHASE = "phase66_14"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
PYTHON = PROJECT / "venv" / "Scripts" / "python.exe"

def log(msg):
    print(msg, flush=True)

def backup_file(rel):
    src = PROJECT / rel
    if not src.exists():
        raise SystemExit(f"PHASE66_14_FAIL missing file: {rel}")
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def write_text(path, text):
    path.write_text(text, encoding="utf-8", newline="")

log(f"PHASE66_14_BACKUP_PATH={BACKUP}")
BACKUP.mkdir(parents=True, exist_ok=True)

switch_rel = Path("inventory/templates/inventory/switch_list.html")
css_rel = Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css")
smoke_rel = Path("smoke_tests/switchmap_66_14_toolbar_only_smoke_test.py")
doc_rel = Path("docs/PHASE66_14_TOOLBAR_ONLY.md")

for rel in [switch_rel, css_rel]:
    backup_file(rel)

switch_path = PROJECT / switch_rel
text = switch_path.read_text(encoding="utf-8", errors="replace")
text = re.sub(r"switchmap-dashboard-stable-main\.css' %\}\?v=[^\"']+", "switchmap-dashboard-stable-main.css' %}?v=phase66-14-toolbar-only-fix", text)

new_toolbar = """    <section class=\"sm-main-toolbar sm-main-toolbar-v14\" aria-label=\"Dashboard toolbar\">
        <div class=\"sm-main-titlebox\">
            <h1>داشبورد مانیتورینگ</h1>
            <p>وضعیت عملیاتی شبکه؛ فقط موارد قابل اقدام نمایش داده می‌شود.</p>
        </div>
        <form class=\"sm-main-quick-search modern-search-panel\" action=\"#\" method=\"get\" role=\"search\" aria-label=\"Quick Search\">
            <label for=\"sm-main-search\">Quick Search</label>
            <div class=\"sm-main-searchbox\">
                <input id=\"sm-main-search\" data-switch-search name=\"q\" type=\"search\" placeholder=\"جستجوی سوییچ، IP، پورت، آلارم...\" autocomplete=\"off\">
                <button type=\"button\" data-search-trigger>جستجو</button>
            </div>
            <div class=\"sm-main-search-results\" data-search-results hidden></div>
        </form>
        <div class=\"sm-main-toolbar-actions\">
            <button class=\"sm-main-refresh-btn btn btn-primary\" type=\"button\" data-dashboard-manual-refresh title=\"Refresh dashboard view\">
                <strong data-dashboard-background-icon aria-hidden=\"true\">!</strong>
                <span>Refresh View</span>
            </button>
            <span class=\"sm-main-last-update\">آخرین بروزرسانی: <b data-field=\"generated_at\">{{ dashboard_insight.generated_at }}</b></span>
        </div>
    </section>
"""
pattern = re.compile(r"    <section class=\"sm-main-toolbar[^\n]*?\".*?</section>\s*(?=\n\s*<section class=\"sm-main-grid\")", re.S)
new_text, count = pattern.subn(new_toolbar, text, count=1)
if count != 1:
    raise SystemExit("PHASE66_14_FAIL toolbar block not found")
if "phase66-14-toolbar-compat" not in new_text:
    new_text += '\n{# phase66-14-toolbar-compat: toolbar-only visual adjustment marker #}\n'
write_text(switch_path, new_text)
log(f"PHASE66_14_PATCHED={switch_rel}")

css_path = PROJECT / css_rel
css = css_path.read_text(encoding="utf-8", errors="replace")
css_block = """

/* Phase 66.14: toolbar-only fix - Quick Search alignment + refresh metadata placement */
body.sm-main-dashboard-body .sm-main-toolbar.sm-main-toolbar-v14{
    grid-template-columns:250px minmax(390px,1fr) minmax(330px,420px)!important;
    grid-template-areas:\"actions search title\"!important;
    align-items:center!important;
    gap:18px!important;
    min-height:102px!important;
    padding:18px 22px!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-titlebox{
    grid-area:title!important;
    align-self:center!important;
    min-width:0!important;
    text-align:right!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-titlebox h1{
    margin:0!important;
    font-size:clamp(25px,2.05vw,30px)!important;
    line-height:1.15!important;
    font-weight:850!important;
    letter-spacing:-.035em!important;
    white-space:nowrap!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-titlebox p{
    margin:7px 0 0!important;
    font-size:13px!important;
    line-height:1.6!important;
    font-weight:620!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-quick-search{
    grid-area:search!important;
    align-self:center!important;
    width:100%!important;
    min-width:0!important;
    margin:0!important;
    padding:0!important;
    position:relative!important;
    border:0!important;
    background:transparent!important;
    box-shadow:none!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-quick-search > label{
    position:absolute!important;
    width:1px!important;
    height:1px!important;
    padding:0!important;
    margin:-1px!important;
    overflow:hidden!important;
    clip:rect(0,0,0,0)!important;
    white-space:nowrap!important;
    border:0!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-searchbox{
    height:44px!important;
    display:flex!important;
    flex-direction:row!important;
    direction:rtl!important;
    align-items:center!important;
    gap:8px!important;
    padding:5px!important;
    border:1px solid #cfe0f3!important;
    border-radius:16px!important;
    background:#f8fbff!important;
    overflow:hidden!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-searchbox input{
    flex:1 1 auto!important;
    min-width:0!important;
    height:100%!important;
    padding:0 13px!important;
    border:0!important;
    outline:0!important;
    background:transparent!important;
    text-align:right!important;
    direction:rtl!important;
    font-size:13.7px!important;
    font-weight:650!important;
    color:var(--sm13-text)!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-searchbox input::placeholder{
    color:#8696aa!important;
    font-weight:600!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-searchbox button{
    flex:0 0 auto!important;
    height:32px!important;
    min-width:72px!important;
    margin:0!important;
    padding:0 13px!important;
    border-radius:12px!important;
    font-size:13px!important;
    font-weight:820!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-toolbar-actions{
    grid-area:actions!important;
    align-self:center!important;
    justify-self:start!important;
    width:250px!important;
    min-width:0!important;
    display:flex!important;
    flex-direction:column!important;
    align-items:flex-start!important;
    justify-content:center!important;
    gap:7px!important;
    white-space:normal!important;
    direction:rtl!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-refresh-btn{
    width:auto!important;
    min-width:150px!important;
    height:42px!important;
    padding:0 16px!important;
    margin:0!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-last-update{
    display:block!important;
    width:250px!important;
    max-width:250px!important;
    margin:0!important;
    padding:0 2px!important;
    text-align:right!important;
    direction:rtl!important;
    unicode-bidi:plaintext!important;
    font-size:12.4px!important;
    line-height:1.45!important;
    font-weight:700!important;
    color:#64748b!important;
    white-space:normal!important;
    overflow:visible!important;
}
body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-last-update b{
    direction:ltr!important;
    unicode-bidi:isolate!important;
    font-weight:800!important;
}
@media (max-width:1100px){
    body.sm-main-dashboard-body .sm-main-toolbar.sm-main-toolbar-v14{
        grid-template-columns:1fr minmax(300px,440px)!important;
        grid-template-areas:\"title actions\" \"search search\"!important;
    }
    body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-toolbar-actions{
        justify-self:start!important;
    }
}
@media (max-width:760px){
    body.sm-main-dashboard-body .sm-main-toolbar.sm-main-toolbar-v14{
        grid-template-columns:1fr!important;
        grid-template-areas:\"title\" \"search\" \"actions\"!important;
        padding:16px!important;
    }
    body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-toolbar-actions{
        width:100%!important;
        max-width:none!important;
        align-items:stretch!important;
    }
    body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-refresh-btn,
    body.sm-main-dashboard-body .sm-main-toolbar-v14 .sm-main-last-update{
        width:100%!important;
        max-width:none!important;
    }
}
"""
if "Phase 66.14: toolbar-only fix" not in css:
    css = css.rstrip() + css_block + "\n"
else:
    start = css.find("/* Phase 66.14: toolbar-only fix")
    css = css[:start].rstrip() + css_block + "\n"
write_text(css_path, css)
log(f"PHASE66_14_PATCHED={css_rel}")

src_root = Path(__file__).resolve().parents[1] / "patches" / "phase66_14_toolbar_only"
for rel in [smoke_rel, doc_rel]:
    src = src_root / rel
    dst = PROJECT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists(): backup_file(rel)
    shutil.copy2(src, dst)
    log(f"PHASE66_14_COPIED={rel}")

def run(label, args):
    log(f"PHASE66_14_RUN={label}")
    p = subprocess.run(args, cwd=str(PROJECT), text=True)
    if p.returncode != 0:
        log(f"PHASE66_14_FAIL={label}")
        log("Rollback example:")
        log(f'xcopy /E /Y "{BACKUP}\\*" "{PROJECT}\\"')
        raise SystemExit(p.returncode)

run("phase66.14 smoke", [str(PYTHON), "smoke_tests\\switchmap_66_14_toolbar_only_smoke_test.py"])
run("manage.py check", [str(PYTHON), "manage.py", "check"])
run("collectstatic", [str(PYTHON), "manage.py", "collectstatic", "--noinput"])
restart = PROJECT / "scripts" / "12_vm_restart_waitress_task.cmd"
if restart.exists():
    run("restart waitress", [str(restart)])
else:
    log("PHASE66_14_WARN missing waitress restart script")
log("PHASE66_14_APPLY_OK")
