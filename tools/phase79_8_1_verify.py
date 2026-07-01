from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = [
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "PHASE79_8_1_MULTI_SSH_UI_RESULT_ORDER"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "data-phase79-order-up"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "ensureMultiResultBox"),
    ("inventory/static/inventory/switchmap-phase79-lc-override.js", "setMultiResult"),
    ("inventory/static/inventory/switchmap.css", "PHASE79_8_1_MULTI_SSH_UI_RESULT_ORDER"),
    ("inventory/templates/inventory/base.html", "phase79-8-1-multi-ssh-ui-result-order"),
]
fail = 0
for rel, marker in checks:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        print(f"OK marker:{rel}:{marker}")
    else:
        print(f"FAIL marker:{rel}:{marker}")
        fail += 1
if fail:
    print("PHASE79_8_1_VERIFY_FAIL")
    raise SystemExit(1)
print("PHASE79_8_1_VERIFY_OK")
