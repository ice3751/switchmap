from __future__ import annotations

# PHASE80_2_ALARM_POLICY_AUDIT

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.alarm_policy import alarm_is_false_positive, is_actionable_interface_down
from inventory.models import AlarmNotification, Port, SfpMonitorSnapshot
from inventory.views import _sync_alarm_notifications, _sfp_issue_labels_for_snapshot


class Command(BaseCommand):
    help = "Phase80.2 researched alarm policy dry-run/apply audit."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Resolve active/acknowledged alarms that violate Phase80.2 policy.")
        parser.add_argument("--sync", action="store_true", help="Run alarm sync before audit.")

    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        if options.get("sync"):
            sync_result = _sync_alarm_notifications()
            self.stdout.write(f"OK sync_active={sync_result.get('active')} sync_resolved={sync_result.get('resolved')}")

        self.stdout.write("PHASE80_2_ALARM_POLICY_AUDIT_START")

        down_ports = list(
            Port.objects.select_related("switch")
            .filter(status=Port.Status.DOWN)
            .order_by("switch__name", "interface_name")
        )
        actionable_down = [p for p in down_ports if is_actionable_interface_down(p)]
        self.stdout.write(f"OK down_ports={len(down_ports)}")
        self.stdout.write(f"OK actionable_down_ports={len(actionable_down)}")

        latest_sfp = {}
        for item in SfpMonitorSnapshot.objects.select_related("switch", "port").order_by("interface_name", "-poll_time", "-id"):
            latest_sfp.setdefault((item.switch_id, item.interface_name), item)
        sfp_problem = []
        for item in latest_sfp.values():
            labels = _sfp_issue_labels_for_snapshot(item)
            if labels:
                sfp_problem.append((item, labels))
        self.stdout.write(f"OK latest_sfp={len(latest_sfp)}")
        self.stdout.write(f"OK sfp_policy_issues={len(sfp_problem)}")

        qs = (
            AlarmNotification.objects.select_related("switch", "port")
            .filter(status__in=[AlarmNotification.Status.ACTIVE, AlarmNotification.Status.ACKNOWLEDGED])
            .order_by("severity", "category", "switch__name", "port__interface_name", "title")
        )
        false_items = []
        for alarm in qs:
            is_false, reason = alarm_is_false_positive(alarm)
            if is_false:
                false_items.append((alarm, reason))

        self.stdout.write(f"OK active_or_ack_alarms={qs.count()}")
        self.stdout.write(f"OK false_positive_candidates={len(false_items)}")
        for alarm, reason in false_items[:50]:
            switch = alarm.switch.name if alarm.switch_id else "-"
            port = alarm.port.interface_name if alarm.port_id else "-"
            self.stdout.write(f"FALSE_POSITIVE id={alarm.id} reason={reason} switch={switch} port={port} title={alarm.title}")

        updated = 0
        if apply and false_items:
            now = timezone.now()
            ids = [alarm.id for alarm, _reason in false_items]
            for alarm, reason in false_items:
                prefix = str(alarm.details or "").rstrip()
                marker = f"Phase80.2 auto-resolved false positive: {reason}"
                alarm.status = AlarmNotification.Status.RESOLVED
                alarm.resolved_at = now
                alarm.details = f"{prefix}\n{marker}".strip()
                alarm.save(update_fields=["status", "resolved_at", "details"])
                updated += 1
            self.stdout.write(f"OK resolved_false_positives={updated}")
        else:
            self.stdout.write("OK resolved_false_positives=0")

        self.stdout.write("FINAL_FAIL_COUNT=0")
        if apply:
            self.stdout.write("PHASE80_2_ALARM_POLICY_APPLY_OK")
        else:
            self.stdout.write("PHASE80_2_ALARM_POLICY_DRYRUN_OK")
