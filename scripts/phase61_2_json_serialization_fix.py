from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "inventory" / "mikrotik_views.py"

HELPERS = r'''

def _json_safe_mikrotik_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return timezone.localtime(value).isoformat()
        except Exception:
            try:
                return value.isoformat()
            except Exception:
                return str(value)
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if key in {"switch", "device"}:
                continue
            clean[str(key)] = _json_safe_mikrotik_value(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_mikrotik_value(item) for item in value]
    if hasattr(value, "_meta") and hasattr(value, "pk"):
        label = getattr(value, "name", None) or str(value)
        return {"id": value.pk, "label": str(label)}
    return str(value)


def _serialize_insight_row(row: dict) -> dict:
    return {
        "name": row.get("name"),
        "ip": row.get("ip"),
        "site": row.get("site"),
        "role": row.get("role"),
        "state": row.get("state"),
        "severity": row.get("severity"),
        "status_title": row.get("status_title"),
        "result": row.get("result"),
        "recommended_action": row.get("recommended_action"),
        "last_poll": row.get("last_poll_text"),
        "age": row.get("age_text"),
        "snmp_port": row.get("snmp_port"),
        "pollable": row.get("pollable"),
        "priority": row.get("priority"),
        "url": row.get("url"),
    }


def _serialize_insight_dashboard_for_json(insight: dict) -> dict:
    if not isinstance(insight, dict):
        return {}
    clean = _json_safe_mikrotik_value(insight)
    clean["device_insights"] = [
        _serialize_insight_row(row)
        for row in insight.get("device_insights", [])
        if isinstance(row, dict)
    ]
    clean["action_items"] = [
        _serialize_insight_row(row)
        for row in insight.get("action_items", [])
        if isinstance(row, dict)
    ]
    return clean
'''


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    if not VIEWS.exists():
        fail(f"file not found: {VIEWS}")
    text = VIEWS.read_text(encoding="utf-8")

    if "def _serialize_insight_dashboard_for_json" not in text:
        marker = "\ndef _serialize_mikrotik_payload(payload: dict) -> dict:\n"
        if marker not in text:
            fail("serializer function marker not found")
        text = text.replace(marker, HELPERS + marker, 1)

    old = '        "insight_dashboard": payload.get("insight_dashboard", {}),'
    new = '        "insight_dashboard": _serialize_insight_dashboard_for_json(payload.get("insight_dashboard", {})),'
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        fail("insight_dashboard serializer assignment not found")

    old = '        "action_items": payload.get("action_items", []),'
    new = '        "action_items": _json_safe_mikrotik_value(payload.get("action_items", [])),'
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        fail("action_items serializer assignment not found")

    VIEWS.write_text(text, encoding="utf-8")
    compile(VIEWS.read_text(encoding="utf-8"), str(VIEWS), "exec")
    print("PHASE61_2_JSON_SERIALIZER_REPAIR_OK")


if __name__ == "__main__":
    main()
