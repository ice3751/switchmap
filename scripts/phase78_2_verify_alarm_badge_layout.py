from pathlib import Path

ROOT = Path.cwd()
CSS = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase78.css"
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "phase78" / "alarm_cleanup.html"
MARKER = "PHASE78_2_ALARM_BADGE_LAYOUT_FIX"
REQUIRED_CSS = [
    MARKER,
    ".phase77-kpi .phase78-severity-split",
    "display: flex !important",
    ".phase77-kpi .phase78-severity-split .phase78-badge",
    "display: inline-flex !important",
    ".phase78-badge .ltr",
]
REQUIRED_TEMPLATE = [
    "PHASE78_1_ALARM_BADGE_UI",
    "phase78-severity-split",
    "phase78-badge-critical",
    "phase78-badge-warning",
]

ok = []
warn = []
fail = []


def check(condition, good, bad):
    if condition:
        ok.append(good)
    else:
        fail.append(bad)


def main():
    check(CSS.exists(), f"css_exists:{CSS}", f"missing_css:{CSS}")
    check(TEMPLATE.exists(), f"template_exists:{TEMPLATE}", f"missing_template:{TEMPLATE}")
    if not CSS.exists() or not TEMPLATE.exists():
        report()
        raise SystemExit(1)

    css = CSS.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    for item in REQUIRED_CSS:
        check(item in css, f"css_marker:{item}", f"missing_css_marker:{item}")
    for item in REQUIRED_TEMPLATE:
        check(item in template, f"template_marker:{item}", f"missing_template_marker:{item}")

    if css.count(MARKER) > 1:
        warn.append(f"css_marker_duplicate_count:{css.count(MARKER)}")
    else:
        ok.append("css_marker_not_duplicated")

    report()
    if fail:
        raise SystemExit(1)


def report():
    print("PHASE78_2_ALARM_BADGE_LAYOUT_REPORT")
    print(f"OK_COUNT={len(ok)}")
    print(f"WARNING_COUNT={len(warn)}")
    print(f"FAIL_COUNT={len(fail)}")
    print("\n[OK]")
    for x in ok:
        print(f"OK {x}")
    print("\n[WARNING]")
    if warn:
        for x in warn:
            print(f"WARNING {x}")
    else:
        print("- none")
    print("\n[FAIL]")
    if fail:
        for x in fail:
            print(f"FAIL {x}")
    else:
        print("- none")
    if not fail:
        print("PHASE78_2_VERIFY_OK")


if __name__ == "__main__":
    main()
