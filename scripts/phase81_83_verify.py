from __future__ import annotations

from django.core.management import call_command
from django.urls import reverse

from inventory.models import AlarmNotification
from inventory.views import _build_topology_payload
from inventory.topology_engine import edge_warning_allowed

ok = 0
warn = 0
fail = 0


def out(status, msg):
    print(f"{status} {msg}")

print("PHASE81_83_COMBINED_VERIFY_START")
try:
    call_command("check")
    ok += 1
    out("OK", "django_check")
except Exception as exc:
    fail += 1
    out("FAIL", f"django_check:{exc}")

for name, args in [
    ("alarm_center", []),
    ("alarm_rules", []),
    ("topology", []),
    ("topology_edge_detail", [1]),
]:
    try:
        url = reverse(f"inventory:{name}", args=args)
        ok += 1
        out("OK", f"url:{name}:{url}")
    except Exception as exc:
        fail += 1
        out("FAIL", f"url:{name}:{exc}")

try:
    sample_alarm = AlarmNotification.objects.order_by("id").first()
    if sample_alarm:
        url = reverse("inventory:alarm_detail", args=[sample_alarm.id])
        ok += 1
        out("OK", f"url:alarm_detail:{url}")
    else:
        warn += 1
        out("WARNING", "url:alarm_detail:no_alarm_rows")
except Exception as exc:
    fail += 1
    out("FAIL", f"url:alarm_detail:{exc}")

try:
    payload = _build_topology_payload()
    links = payload.get("links", [])
    warn_edges = [item for item in links if edge_warning_allowed(item)]
    no_evidence_warn = [item for item in warn_edges if int(item.get("evidence_count") or 0) <= 0]
    missing_detail = [item for item in links if not item.get("detail_url")]
    confidence_counts = {}
    for item in links:
        confidence_counts[item.get("confidence") or "unknown"] = confidence_counts.get(item.get("confidence") or "unknown", 0) + 1
    ok += 1
    out("OK", f"topology_payload:links={len(links)} warning_edges={len(warn_edges)} confidence={confidence_counts}")
    if no_evidence_warn:
        fail += 1
        out("FAIL", f"warning_without_evidence:{len(no_evidence_warn)}")
    else:
        ok += 1
        out("OK", "warning_edges_have_evidence")
    if missing_detail:
        fail += 1
        out("FAIL", f"links_missing_detail_url:{len(missing_detail)}")
    else:
        ok += 1
        out("OK", "links_have_detail_url")
    ok += 1
    out("OK", f"topology_counts:confirmed={payload.get('confirmed_link_count',0)} partial={payload.get('partial_link_count',0)} inferred={payload.get('inferred_link_count',0)} stale={payload.get('stale_link_count',0)} suppressed={payload.get('suppressed_link_count',0)}")
except Exception as exc:
    fail += 1
    out("FAIL", f"topology_payload:{exc}")

print(f"FINAL_OK_COUNT={ok}")
print(f"FINAL_WARNING_COUNT={warn}")
print(f"FINAL_FAIL_COUNT={fail}")
if fail:
    print("PHASE81_83_COMBINED_VERIFY_FAIL")
    raise SystemExit(1)
print("PHASE81_83_COMBINED_VERIFY_OK")
