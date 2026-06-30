from pathlib import Path
from datetime import datetime
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
PHASE = "phase70_2_svg_gradient_scope_fix"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = PROJECT / "backups" / f"{PHASE}_{STAMP}"
REL = "inventory/templates/inventory/includes/cisco_3850_svg.html"

UID = "{{ switch_obj.id }}"
MARKER = "PHASE70_2_SVG_GRADIENT_SCOPE_FIX"

def fail(msg):
    print(f"PHASE70_2_FAIL {msg}")
    sys.exit(1)

def path(rel=REL):
    return PROJECT / rel

def read():
    p = path()
    if not p.exists():
        fail(f"missing {REL}")
    return p.read_text(encoding="utf-8")

def write(text):
    path().write_text(text, encoding="utf-8", newline="")

def backup_file():
    src = path()
    dst = BACKUP / REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"PHASE70_2_BACKUP={BACKUP}")

def patch_template(text):
    original = text

    ids = [
        "sm3850Body",
        "sm3850Panel",
        "sm3850Port",
        "sm3850Jack",
        "sm3850Nm",
        "sm3850Shadow",
    ]
    for name in ids:
        text = text.replace(f'id="{name}"', f'id="{name}-{UID}"')

    # Direct SVG attributes that already reference the shared IDs.
    attr_refs = {
        'fill="url(#sm3850Body)"': f'fill="url(#sm3850Body-{UID})"',
        'filter="url(#sm3850Shadow)"': f'filter="url(#sm3850Shadow-{UID})"',
    }
    for old, new in attr_refs.items():
        text = text.replace(old, new)

    # These fills were previously injected by global CSS with duplicate SVG IDs.
    # Inline style scopes each rendered switch without changing size/layout.
    text = text.replace(
        '<rect x="210" y="50" width="800" height="62" rx="4"/>',
        f'<rect x="210" y="50" width="800" height="62" rx="4" style="fill:url(#sm3850Panel-{UID})"/>'
    )
    text = text.replace(
        '<rect class="port-frame" x="0" y="0" width="25" height="21" rx="3"/>',
        f'<rect class="port-frame" x="0" y="0" width="25" height="21" rx="3" style="fill:url(#sm3850Port-{UID})"/>'
    )
    text = text.replace(
        '<rect class="port-jack" x="7" y="11" width="14" height="6" rx="1.5"/>',
        f'<rect class="port-jack" x="7" y="11" width="14" height="6" rx="1.5" style="fill:url(#sm3850Jack-{UID})"/>'
    )
    text = text.replace(
        '<rect x="1038" y="42" width="108" height="76" rx="6"/>',
        f'<rect x="1038" y="42" width="108" height="76" rx="6" style="fill:url(#sm3850Nm-{UID})"/>'
    )
    text = text.replace(
        '<rect class="port-frame" x="0" y="0" width="41" height="24" rx="3"/>',
        f'<rect class="port-frame" x="0" y="0" width="41" height="24" rx="3" style="fill:url(#sm3850Port-{UID})"/>'
    )
    text = text.replace(
        '<rect class="port-jack" x="13" y="14" width="18" height="6" rx="1.5"/>',
        f'<rect class="port-jack" x="13" y="14" width="18" height="6" rx="1.5" style="fill:url(#sm3850Jack-{UID})"/>'
    )

    if MARKER not in text:
        text = text.rstrip() + f"\n{{# {MARKER}: scoped SVG gradient/filter IDs per switch; no layout/render size change #}}\n"

    return text, text != original

def validate(text):
    checks = {
        "scoped body gradient": f'id="sm3850Body-{UID}"' in text,
        "scoped panel gradient": f'id="sm3850Panel-{UID}"' in text,
        "scoped port gradient": f'id="sm3850Port-{UID}"' in text,
        "scoped jack gradient": f'id="sm3850Jack-{UID}"' in text,
        "scoped nm gradient": f'id="sm3850Nm-{UID}"' in text,
        "scoped shadow filter": f'id="sm3850Shadow-{UID}"' in text,
        "body uses scoped fill": f'fill="url(#sm3850Body-{UID})"' in text,
        "body uses scoped filter": f'filter="url(#sm3850Shadow-{UID})"' in text,
        "panel uses scoped style": f'style="fill:url(#sm3850Panel-{UID})"' in text,
        "ports use scoped style": f'style="fill:url(#sm3850Port-{UID})"' in text,
        "jacks use scoped style": f'style="fill:url(#sm3850Jack-{UID})"' in text,
        "nm uses scoped style": f'style="fill:url(#sm3850Nm-{UID})"' in text,
        "marker": MARKER in text,
    }
    for name, ok in checks.items():
        print(f"PHASE70_2_CHECK::{name}={'OK' if ok else 'FAIL'}")
        if not ok:
            fail(f"validation {name}")

backup_file()
text = read()
text, changed = patch_template(text)
write(text)
validate(text)
print(f"PHASE70_2_CHANGED={'YES' if changed else 'NO'}")
print("PHASE70_2_SVG_GRADIENT_SCOPE_FIX_OK")
