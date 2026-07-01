from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "inventory" / "phase79_history.py"
BACKUP_ROOT = ROOT / "backups" / ("phase79_2_6_history_import_fix_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))

HELPERS = r'''

def history_has_identity_data(history) -> bool:
    # Phase79.2.6: compatibility helper for views/imports and strict UI truth guard.
    # Do not count poll timestamps, VLAN, status, mode, neighbor_source or mac_count alone
    # as endpoint identity. Only real endpoint/device evidence is accepted.
    if history is None:
        return False
    if _identity_clean(getattr(history, "connected_device", "")):
        return True
    if _identity_clean(getattr(history, "neighbor_device", "")) or _identity_clean(getattr(history, "neighbor_port", "")):
        return True
    if _identity_clean(getattr(history, "neighbor_ip", "")) or _identity_clean(getattr(history, "ip_address", "")):
        return True
    if _identity_clean(getattr(history, "mac_address", "")) or _first_mac(getattr(history, "mac_addresses", "")):
        return True
    device_type = _identity_clean(getattr(history, "device_type", ""))
    if device_type and device_type.lower() not in ("unknown", "نامشخص"):
        return True
    if _identity_clean(getattr(history, "owner", "")):
        return True
    return False
'''

STRICT_LATEST = r'''
def latest_port_connection(port: Port) -> Optional[PortConnectionHistory]:
    # Phase79.2.6: return only records that contain real endpoint identity.
    # Old empty snapshots may have non-empty identity_hash because VLAN/mode existed.
    qs = PortConnectionHistory.objects.filter(port=port).order_by("-observed_at", "-id")[:50]
    for item in qs:
        if history_has_identity_data(item):
            return item
    return None
'''


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    rel = path.relative_to(ROOT)
    dst = BACKUP_ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    path.write_text(text, encoding="utf-8")


def ensure_helper(text: str) -> str:
    if "def history_has_identity_data(" in text:
        return text
    marker = "def record_port_identity_snapshot("
    if marker in text:
        return text.replace(marker, HELPERS + "\n\n" + marker, 1)
    marker = "def latest_port_connection("
    if marker in text:
        return text.replace(marker, HELPERS + "\n\n" + marker, 1)
    raise RuntimeError("phase79_history: insertion point not found")


def ensure_strict_latest(text: str) -> str:
    pattern = re.compile(r"def latest_port_connection\(port: Port\) -> Optional\[PortConnectionHistory\]:.*?(?=\n\ndef |\Z)", re.S)
    new_text, count = pattern.subn(STRICT_LATEST.strip(), text, count=1)
    if count != 1:
        raise RuntimeError("phase79_history: latest_port_connection block not found")
    return new_text


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    text = read(HISTORY)
    text = ensure_helper(text)
    text = ensure_strict_latest(text)
    write(HISTORY, text)
    print(f"PHASE79_2_6_PATCH_OK backup_dir={BACKUP_ROOT}")


if __name__ == "__main__":
    main()
