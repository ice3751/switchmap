from pathlib import Path

root = Path(__file__).resolve().parents[1]
checks = []

def ok(name, cond):
    if cond:
        print(f"OK {name}")
    else:
        print(f"FAIL {name}")
        raise SystemExit(1)

tpl = root / "inventory" / "templates" / "inventory" / "alarm_center.html"
text = tpl.read_text(encoding="utf-8")
ok("marker:PHASE79_9_2_COMPACT_ALARM_FILTER", "PHASE79_9_2_COMPACT_ALARM_FILTER" in text)
ok("old_large_filter_removed", "phase79-9-alarm-filter-grid" not in text and "Filter Alarms</strong>" not in text)
ok("inline_filter_icon", "alarm-filter-icon" in text and "🔎 فیلتر" in text)
ok("inline_filter_form", "alarm-inline-filter-form" in text and 'name="q"' in text and 'type="search"' in text)
ok("preserve_status_hidden", 'name="status"' in text and 'selected_status' in text)
ok("table_toolbar", "phase79-9-2-alarm-toolbar" in text)
print("PHASE79_9_2_VERIFY_OK")
