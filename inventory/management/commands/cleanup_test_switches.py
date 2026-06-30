from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from inventory.models import AlarmNotification, Switch


class Command(BaseCommand):
    help = "Remove known SwitchMap smoke/test switches and smoke users from production data."

    def handle(self, *args, **options):
        exact_names = [
            "SmokeTest-SW",
            "SMOKE-SFP-SW",
            "SMOKE-SWITCH",
            "SWITCHMAP_PHASE28_SFP_TEST",
            "PHASE31A-BULK-TEST",
            "SWITCHMAP-PHASE36-1-SMOKE",
            "SWITCHMAP-PHASE36-SMOKE",
            "Phase41-2-Edit-Smoke",
            "Phase41-4-Edit-Smoke",
        ]
        prefixes = [
            "SMOKE30-",
            "PHASE31B1-",
            "PHASE31B-",
            "SMOKE33-",
            "SMOKE33B-",
            "PHASE35-",
        ]

        queryset = Switch.objects.filter(name__in=exact_names)
        for prefix in prefixes:
            queryset = queryset | Switch.objects.filter(name__startswith=prefix)
        queryset = queryset.distinct()
        deleted_switch_names = list(queryset.values_list("name", flat=True))
        deleted_switch_count, _ = queryset.delete()

        stale_alarm_count, _ = AlarmNotification.objects.filter(
            switch__isnull=True,
            source__icontains="smoke",
        ).delete()

        user_model = get_user_model()
        user_prefixes = [
            "switchmap_phase",
            "phase31a_",
            "phase31b_",
            "phase31b1_",
            "phase35_",
        ]
        users = user_model.objects.none()
        for prefix in user_prefixes:
            users = users | user_model.objects.filter(username__startswith=prefix)
        users = users.distinct()
        deleted_usernames = list(users.values_list("username", flat=True))
        deleted_user_count, _ = users.delete()

        self.stdout.write(
            "TEST_DATA_CLEANUP_OK "
            f"switches={len(deleted_switch_names)} "
            f"switch_rows={deleted_switch_count} "
            f"users={len(deleted_usernames)} "
            f"user_rows={deleted_user_count} "
            f"stale_alarms={stale_alarm_count}"
        )
        if deleted_switch_names:
            self.stdout.write("REMOVED_SWITCHES " + ", ".join(sorted(deleted_switch_names)))
        if deleted_usernames:
            self.stdout.write("REMOVED_USERS " + ", ".join(sorted(deleted_usernames)))
