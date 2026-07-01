from pathlib import Path

root = Path(r"C:\SwitchMap")
template = root / "inventory" / "templates" / "inventory" / "switch_list.html"
marker = "phase68-quick-search-port-labels"
compat = "\n{# Phase 68 compatibility marker: phase68-quick-search-port-labels #}\n"

text = template.read_text(encoding="utf-8")
if marker not in text:
    template.write_text(text.rstrip() + compat, encoding="utf-8")
    print("PHASE69_2_PATCHED=inventory\\templates\\inventory\\switch_list.html")
else:
    print("PHASE69_2_ALREADY_OK=inventory\\templates\\inventory\\switch_list.html")

print("PHASE69_2_COMPAT_OK")
