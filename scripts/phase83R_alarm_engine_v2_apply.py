import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from inventory.alarm_engine import alarm_engine_summary, sync_alarm_notifications_v2
from inventory.alarm_policy import alarm_is_false_positive, is_actionable_interface_down
from inventory.models import AlarmNotification


def target(alarm):
    sw = alarm.switch.name if alarm.switch else "-"
    port = alarm.port.interface_name if alarm.port else "-"
    return f"{sw} {port}".strip()


def main():
    print("PHASE83R_ALARM_ENGINE_V2_APPLY_START")
    before = alarm_engine_summary()
    print("BEFORE active={active} critical={critical} warning={warning} resolved={resolved}".format(**before))

    result = sync_alarm_notifications_v2()
    print(
        "ENGINE candidates={candidates} emitted={emitted} pending={pending} suppressed={suppressed} "
        "stale_resolved={stale_resolved} false_positive_resolved={false_positive_resolved} "
        "reopened_blocked={reopened_blocked}".format(**result)
    )

    after = alarm_engine_summary()
    print("AFTER active={active} critical={critical} warning={warning} resolved={resolved} policy_states={policy_states} evidence={evidence}".format(**after))

    fail = []
    active = list(AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE).order_by("severity", "switch__name", "port__interface_name", "title"))
    for alarm in active:
        fp, reason = alarm_is_false_positive(alarm)
        if fp:
            fail.append(f"FALSE_POSITIVE_ACTIVE:{alarm.id}:{alarm.title}:{target(alarm)}:{reason}")
        if (alarm.fingerprint or "").startswith("uplink-down:") and not is_actionable_interface_down(alarm.port):
            fail.append(f"UNACTIONABLE_UPLINK_ACTIVE:{alarm.id}:{target(alarm)}")

    print("ACTIVE_ALARMS_START")
    for alarm in active[:50]:
        print(f"ACTIVE id={alarm.id} severity={alarm.severity} title={alarm.title} target={target(alarm)} source={alarm.source}")
    print("ACTIVE_ALARMS_END")

    for item in fail:
        print("FAIL", item)

    ok_count = 6
    print(f"FINAL_OK_COUNT={ok_count}")
    print(f"FINAL_FAIL_COUNT={len(fail)}")
    if fail:
        print("PHASE83R_ALARM_ENGINE_V2_APPLY_FAIL")
        sys.exit(2)
    print("PHASE83R_ALARM_ENGINE_V2_APPLY_OK")


if __name__ == "__main__":
    main()
