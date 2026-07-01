from pathlib import Path

checks = []
root = Path(__file__).resolve().parents[1]
js = root / "inventory/static/inventory/switchmap.js"
css = root / "inventory/static/inventory/css/switchmap-phase79.css"
base = root / "inventory/templates/inventory/base.html"
for p in [js, css, base]:
    if not p.exists():
        raise SystemExit(f"FAIL missing:{p}")

j = js.read_text(encoding="utf-8", errors="replace")
c = css.read_text(encoding="utf-8", errors="replace")
b = base.read_text(encoding="utf-8", errors="replace")

required = {
    "js_marker": "PHASE79_6_4_LAST_CONNECTED_SAFE_RENDER" in j,
    "js_local_escape": "const localEscape" in j,
    "js_try_catch": "PHASE79_6_4_LAST_CONNECTED_RENDER_ERROR" in j,
    "js_current_title": "Current Connected Device" in j,
    "js_last_known_title": "Last Known Device" in j,
    "css_marker": "PHASE79_6_4_LAST_CONNECTED_SAFE_RENDER" in c,
    "base_cache_bust": "phase79-6-4-last-connected-safe-render" in b,
    "no_undefined_esc_call": "esc(" not in j,
}
failed = [k for k,v in required.items() if not v]
for k,v in required.items():
    print(("OK" if v else "FAIL"), k)
if failed:
    raise SystemExit("PHASE79_6_4_VERIFY_FAIL " + ",".join(failed))
print("PHASE79_6_4_VERIFY_OK")
