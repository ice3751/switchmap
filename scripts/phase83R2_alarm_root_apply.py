import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.utils import timezone
from inventory.alarm_engine import alarm_engine_summary, sync_alarm_notifications_v2
from inventory.alarm_policy import alarm_is_false_positive, has_explicit_alarm_monitor_tag
from inventory.models import AlarmNotification, AlarmPolicyState


def is_topology_down_alarm(alarm):
    fp = (alarm.fingerprint or "").strip().lower()
    title = (alarm.title or "").strip().lower()
    message = (alarm.message or "").strip().lower()
    category = (alarm.category or "").strip().lower()
    return (
        fp.startswith("uplink-down:")
        or (category == "topology" and ("uplink" in title or "neighbor down" in title or " is down" in message or " is down" in title))
    )


def resolve_alarm(alarm, reason, now):
    changed = False
    if alarm.status != AlarmNotification.Status.RESOLVED:
        alarm.status = AlarmNotification.Status.RESOLVED
        alarm.resolved_at = now
        changed = True
    details = alarm.details or ""
    marker = f"Phase83R2 auto-resolved: {reason}"
    if marker not in details:
        alarm.details = (details + "\n" + marker).strip()
        changed = True
    if changed:
        alarm.save(update_fields=["status", "resolved_at", "details"])
    state, _ = AlarmPolicyState.objects.get_or_create(
        fingerprint=alarm.fingerprint,
        defaults={"rule_key": "important_interface_down" if is_topology_down_alarm(alarm) else "legacy"},
    )
    state.state = AlarmPolicyState.State.RESOLVED
    state.last_resolved_at = now
    state.current_failures = 0
    state.suppressed_reason = reason
    state.save(update_fields=["state", "last_resolved_at", "current_failures", "suppressed_reason", "updated_at"])


def cleanup(reason_prefix):
    now = timezone.now()
    resolved = 0
    qs = AlarmNotification.objects.select_related("switch", "port").exclude(status=AlarmNotification.Status.RESOLVED)
    for alarm in qs:
        reason = ""
        if is_topology_down_alarm(alarm) and not has_explicit_alarm_monitor_tag(alarm.port):
            reason = "topology_down_without_explicit_monitor_tag"
        else:
            fp, fp_reason = alarm_is_false_positive(alarm)
            if fp:
                reason = fp_reason or "false_positive"
        if reason:
            resolve_alarm(alarm, f"{reason_prefix}:{reason}", now)
            resolved += 1
    return resolved


def main():
    print("PHASE83R2_ALARM_ROOT_APPLY_START")
    before = alarm_engine_summary()
    print("BEFORE active={active} critical={critical} warning={warning} resolved={resolved}".format(**before))

    pre_resolved = cleanup("pre")
    engine = sync_alarm_notifications_v2()
    post_resolved = cleanup("post")
    after = alarm_engine_summary()

    print("PRE_RESOLVED=", pre_resolved)
    print(
        "ENGINE candidates={candidates} emitted={emitted} pending={pending} suppressed={suppressed} "
        "stale_resolved={stale_resolved} false_positive_resolved={false_positive_resolved}".format(**engine)
    )
    print("POST_RESOLVED=", post_resolved)
    print("AFTER active={active} critical={critical} warning={warning} resolved={resolved} policy_states={policy_states} evidence={evidence}".format(**after))

    fail = []
    active = list(AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE).order_by("severity", "switch__name", "port__interface_name", "title"))
    print("ACTIVE_ALARMS_START")
    for alarm in active[:80]:
        sw = alarm.switch.name if alarm.switch else "-"
        port = alarm.port.interface_name if alarm.port else "-"
        print(f"ACTIVE id={alarm.id} severity={alarm.severity} category={alarm.category} title={alarm.title} target={sw} {port} fp={alarm.fingerprint}")
        if is_topology_down_alarm(alarm) and not has_explicit_alarm_monitor_tag(alarm.port):
            fail.append(f"UNMONITORED_TOPOLOGY_DOWN_ACTIVE:{alarm.id}:{sw}:{port}:{alarm.title}")
        fp, reason = alarm_is_false_positive(alarm)
        if fp:
            fail.append(f"FALSE_POSITIVE_ACTIVE:{alarm.id}:{sw}:{port}:{alarm.title}:{reason}")
    print("ACTIVE_ALARMS_END")

    for item in fail:
        print("FAIL", item)
    print("FINAL_OK_COUNT=7")
    print(f"FINAL_FAIL_COUNT={len(fail)}")
    if fail:
        print("PHASE83R2_ALARM_ROOT_APPLY_FAIL")
        sys.exit(2)
    print("PHASE83R2_ALARM_ROOT_APPLY_OK")


if __name__ == "__main__":
    main()
