import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.utils import timezone
from inventory.models import AlarmNotification
from inventory.alarm_policy import alarm_is_false_positive
from inventory.views import _sync_alarm_notifications


def resolve_false_positives():
    now = timezone.now()
    resolved = []
    for alarm in AlarmNotification.objects.select_related("switch", "port").exclude(status=AlarmNotification.Status.RESOLVED):
        is_fp, reason = alarm_is_false_positive(alarm)
        if not is_fp:
            continue
        alarm.status = AlarmNotification.Status.RESOLVED
        alarm.resolved_at = now
        alarm.details = ((alarm.details or "") + f"\nAuto-resolved by Phase83.1 apply: {reason}").strip()
        alarm.save(update_fields=["status", "resolved_at", "details"])
        resolved.append((alarm.id, alarm.fingerprint, reason))
    return resolved


def main():
    print("PHASE83_1_ALARM_NOISE_ROOT_FIX_START")
    summary = _sync_alarm_notifications()
    resolved = resolve_false_positives()

    active = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count()
    critical = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count()
    warning = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count()

    remaining_false = []
    for alarm in AlarmNotification.objects.select_related("switch", "port").filter(status=AlarmNotification.Status.ACTIVE):
        is_fp, reason = alarm_is_false_positive(alarm)
        if is_fp:
            remaining_false.append((alarm.id, alarm.fingerprint, reason))

    print(f"OK sync_active={summary.get('active')}")
    print(f"OK sync_false_positive_resolved={summary.get('phase83_1_false_positive_resolved', 0)}")
    print(f"OK apply_false_positive_resolved={len(resolved)}")
    print(f"OK active={active} critical={critical} warning={warning}")
    print(f"OK remaining_false_positive={len(remaining_false)}")
    for item in resolved[:30]:
        print(f"RESOLVED id={item[0]} fp={item[1]} reason={item[2]}")
    if remaining_false:
        for item in remaining_false[:30]:
            print(f"FAIL remaining id={item[0]} fp={item[1]} reason={item[2]}")
        print("PHASE83_1_ALARM_NOISE_ROOT_FIX_FAIL")
        return 1
    print("PHASE83_1_ALARM_NOISE_ROOT_FIX_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
