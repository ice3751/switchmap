import argparse
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

MARKER_JS = "Phase 73.2 Force Hide Refresh View"
MARKER_CSS = "Phase 73.2 Force Hide Refresh View"

JS_SNIPPET = r"""
/* Phase 73.2 Force Hide Refresh View */
(function () {
  function smPhase732HideRefreshView() {
    var nodes = document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"]');
    nodes.forEach(function (el) {
      var text = ((el.textContent || el.value || '') + '').replace(/\s+/g, ' ').trim().toLowerCase();
      var attrs = [
        el.id || '',
        el.className || '',
        el.getAttribute('href') || '',
        el.getAttribute('onclick') || '',
        el.getAttribute('title') || '',
        el.getAttribute('aria-label') || '',
        el.getAttribute('data-action') || '',
        el.getAttribute('data-manual-refresh') || '',
        el.getAttribute('data-dashboard-refresh') || ''
      ].join(' ').toLowerCase();

      var isRefreshView =
        text.indexOf('refresh view') !== -1 ||
        attrs.indexOf('refresh-view') !== -1 ||
        attrs.indexOf('manual-refresh') !== -1 ||
        attrs.indexOf('dashboard-refresh') !== -1;

      if (isRefreshView) {
        el.setAttribute('data-phase73-hidden-refresh-view', '1');
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', smPhase732HideRefreshView);
  } else {
    smPhase732HideRefreshView();
  }
  window.addEventListener('load', smPhase732HideRefreshView);
  setTimeout(smPhase732HideRefreshView, 250);
  setTimeout(smPhase732HideRefreshView, 1000);
})();
"""

CSS_SNIPPET = r"""
/* Phase 73.2 Force Hide Refresh View */
[data-phase73-hidden-refresh-view],
button[data-manual-refresh],
a[data-manual-refresh],
button[data-dashboard-refresh],
a[data-dashboard-refresh],
.refresh-view,
.refresh-view-btn,
.dashboard-refresh-btn,
.manual-refresh,
.manual-refresh-btn,
#refresh-view,
#refreshView,
#dashboard-refresh,
#dashboardRefresh {
  display: none !important;
  visibility: hidden !important;
}
"""

BUTTON_PATTERNS = [
    re.compile(r'<button\b(?=[\s\S]*?Refresh\s+View)[\s\S]*?</button>', re.IGNORECASE),
    re.compile(r'<a\b(?=[\s\S]*?Refresh\s+View)[\s\S]*?</a>', re.IGNORECASE),
]

def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "cp1256", "cp1252"):
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore"), "utf-8"

def write_text(path, text, enc):
    path.write_text(text, encoding="utf-8")

def backup_file(path, backup_root):
    rel = path.relative_to(Path.cwd())
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

def append_if_missing(path, snippet, marker, backup_root, changed):
    if not path.exists():
        print(f"SKIP_MISSING={path}")
        return
    text, enc = read_text(path)
    if marker in text:
        print(f"MARKER_EXISTS={path}")
        return
    backup_file(path, backup_root)
    path.write_text(text.rstrip() + "\n\n" + snippet.strip() + "\n", encoding="utf-8")
    changed.append(str(path))
    print(f"PATCHED={path}")

def remove_refresh_buttons_from_templates(backup_root, changed):
    roots = [Path("inventory/templates")]
    total = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.html"):
            text, enc = read_text(path)
            if "Refresh View" not in text:
                continue
            new_text = text
            removed = 0
            for pat in BUTTON_PATTERNS:
                def repl(m):
                    nonlocal removed
                    removed += 1
                    return "<!-- Phase 73.2 removed Refresh View control -->"
                new_text = pat.sub(repl, new_text)
            if new_text != text:
                backup_file(path, backup_root)
                path.write_text(new_text, encoding="utf-8")
                changed.append(str(path))
                total += removed
                print(f"TEMPLATE_REFRESH_BUTTON_REMOVED={path} count={removed}")
            else:
                print(f"TEMPLATE_REFRESH_VIEW_FOUND_NOT_REMOVED={path}")
    print(f"TEMPLATE_REMOVED_TOTAL={total}")

def verify():
    template_hits = []
    for root in [Path("inventory/templates")]:
        if root.exists():
            for path in root.rglob("*.html"):
                text, enc = read_text(path)
                if "Refresh View" in text:
                    template_hits.append(str(path))
    print(f"TEMPLATE_REFRESH_VIEW_REMAINING_COUNT={len(template_hits)}")
    for hit in template_hits[:50]:
        print(f"TEMPLATE_REFRESH_VIEW_REMAINING={hit}")

    paths = [
        Path("inventory/static/inventory/switchmap.js"),
        Path("staticfiles/inventory/switchmap.js"),
        Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"),
        Path("staticfiles/inventory/css/switchmap-dashboard-stable-main.css"),
    ]
    for path in paths:
        if path.exists():
            text, enc = read_text(path)
            print(f"CHECK::{path}::HAS_PHASE73_2_MARKER={'YES' if 'Phase 73.2 Force Hide Refresh View' in text else 'NO'}")
        else:
            print(f"CHECK::{path}::MISSING=YES")

def apply():
    project = Path.cwd()
    backup_root = project / "backups" / ("phase73_2_force_hide_refresh_view_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    backup_root.mkdir(parents=True, exist_ok=True)
    print(f"BACKUP={backup_root}")

    changed = []
    remove_refresh_buttons_from_templates(backup_root, changed)
    append_if_missing(Path("inventory/static/inventory/switchmap.js"), JS_SNIPPET, MARKER_JS, backup_root, changed)
    append_if_missing(Path("inventory/static/inventory/css/switchmap-dashboard-stable-main.css"), CSS_SNIPPET, MARKER_CSS, backup_root, changed)

    manifest = backup_root / "manifest.txt"
    manifest.write_text("\n".join(changed) + "\n", encoding="utf-8")
    print(f"CHANGED_COUNT={len(changed)}")
    print(f"MANIFEST={manifest}")
    verify()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
    elif args.verify:
        verify()
    else:
        parser.error("use --apply or --verify")

if __name__ == "__main__":
    main()
