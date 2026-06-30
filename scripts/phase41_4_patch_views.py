from pathlib import Path

path = Path("inventory/views.py")
text = path.read_text(encoding="utf-8")
needle = "from .forms import "
start = text.find(needle)
if start < 0:
    raise SystemExit("FORMS_IMPORT_NOT_FOUND")
end = text.find("\n", start)
line = text[start:end]
items = [item.strip() for item in line[len(needle):].split(",") if item.strip()]
if "SwitchForm" not in items:
    insert_at = min(3, len(items))
    items.insert(insert_at, "SwitchForm")
new_line = needle + ", ".join(dict.fromkeys(items))
text = text[:start] + new_line + text[end:]
path.write_text(text, encoding="utf-8")
print("SWITCHFORM_IMPORT_OK")
