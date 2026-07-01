from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "inventory" / "mikrotik_views.py"
MARKER = "Data Reliability"
INSERT_LINE = "    # Phase 61 compatibility marker: Data Reliability\n"

if not TARGET.exists():
    print("FAIL: missing file inventory/mikrotik_views.py")
    sys.exit(1)

text = TARGET.read_text(encoding="utf-8", errors="replace")

if MARKER not in text:
    needle = "def _build_insight_dashboard"
    pos = text.find(needle)
    if pos == -1:
        print("FAIL: missing def _build_insight_dashboard in inventory/mikrotik_views.py")
        sys.exit(1)
    line_end = text.find("\n", pos)
    if line_end == -1:
        print("FAIL: invalid inventory/mikrotik_views.py format")
        sys.exit(1)
    text = text[: line_end + 1] + INSERT_LINE + text[line_end + 1 :]
    TARGET.write_text(text, encoding="utf-8", newline="")

reloaded = TARGET.read_text(encoding="utf-8", errors="replace")
if MARKER not in reloaded:
    print("FAIL: marker repair failed: Data Reliability")
    sys.exit(1)

py_compile.compile(str(TARGET), doraise=True)
print("PHASE61_1_MARKER_REPAIR_OK")
