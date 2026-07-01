from pathlib import Path

ROOT = Path.cwd()
TEMPLATE = ROOT / "inventory" / "templates" / "inventory" / "phase78" / "alarm_cleanup.html"
CSS = ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-phase78.css"
MARKER = "PHASE78_1_ALARM_BADGE_UI"
REQUIRED_TEMPLATE = [
    MARKER,
    "phase78-severity-split",
    "phase78-badge-critical",
    "phase78-badge-warning",
    "{{ summary.critical_count }}",
    "{{ summary.warning_count }}",
]
REQUIRED_CSS = [
    MARKER,
    ".phase78-severity-split",
    ".phase78-badge-critical",
    ".phase78-badge-warning",
    "unicode-bidi: isolate",
]
OLD = "{{ summary.critical_count }} Critical / {{ summary.warning_count }} Warning"

ok = []
warn = []
fail = []


def check(condition, good, bad):
    if condition:
        ok.append(good)
    else:
        fail.append(bad)


def main():
    check(TEMPLATE.exists(), f"template_exists:{TEMPLATE}", f"missing_template:{TEMPLATE}")
    check(CSS.exists(), f"css_exists:{CSS}", f"missing_css:{CSS}")
    if not TEMPLATE.exists() or not CSS.exists():
        report()
        raise SystemExit(1)

    t = TEMPLATE.read_text(encoding="utf-8")
    c = CSS.read_text(encoding="utf-8")

    for item in REQUIRED_TEMPLATE:
        check(item in t, f"template_marker:{item}", f"missing_template_marker:{item}")
    for item in REQUIRED_CSS:
        check(item in c, f"css_marker:{item}", f"missing_css_marker:{item}")
    check(OLD not in t, "old_mixed_ltr_rtl_text_removed", "old_mixed_ltr_rtl_text_still_present")

    if c.count(MARKER) > 1:
        warn.append(f"css_marker_duplicate_count:{c.count(MARKER)}")
    else:
        ok.append("css_marker_not_duplicated")

    report()
    if fail:
        raise SystemExit(1)


def report():
    print("PHASE78_1_ALARM_BADGE_UI_REPORT")
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
        print("PHASE78_1_VERIFY_OK")


if __name__ == "__main__":
    main()
