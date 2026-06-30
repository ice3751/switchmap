from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

from inventory.models import AlarmNotification, SfpMonitorSnapshot, Switch


class Command(BaseCommand):
    help = "Phase 78 read-only alarm cleanup report and verification."

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true")

    def handle(self, *args, **options):
        ok = []
        warnings = []
        fails = []

        required_urls = [
            "phase78_alarm_cleanup",
            "phase78_alarm_recheck",
            "phase78_alarm_resolve_stale",
            "phase78_alarm_cleanup_status_json",
            "alarm_center",
            "switch_list",
            "phase77_noc_dashboard",
        ]
        for name in required_urls:
            try:
                reverse(f"inventory:{name}")
                ok.append(f"url:{name}")
            except NoReverseMatch as exc:
                fails.append(f"url:{name}: {exc}")

        active = AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE)
        active_count = active.count()
        critical_count = active.filter(severity=AlarmNotification.Severity.CRITICAL).count()
        warning_count = active.filter(severity=AlarmNotification.Severity.WARNING).count()
        snmp_timeout = Switch.objects.filter(is_active=True, snmp_enabled=True).exclude(snmp_last_error="").count()
        sfp_snapshots = SfpMonitorSnapshot.objects.count()

        ok.append(f"data:active_alarms:{active_count}")
        ok.append(f"data:critical_alarms:{critical_count}")
        ok.append(f"data:warning_alarms:{warning_count}")
        ok.append(f"data:snmp_timeout_devices:{snmp_timeout}")
        ok.append(f"data:sfp_snapshots:{sfp_snapshots}")

        if active_count:
            warnings.append(f"monitoring:active_alarms:{active_count} operational alarms present")
        if snmp_timeout:
            warnings.append(f"monitoring:snmp_timeout_devices:{snmp_timeout} devices have SNMP errors")

        self.stdout.write("PHASE78_ALARM_CLEANUP_REPORT")
        self.stdout.write(f"OK_COUNT={len(ok)}")
        self.stdout.write(f"WARNING_COUNT={len(warnings)}")
        self.stdout.write(f"FAIL_COUNT={len(fails)}")
        self.stdout.write("")
        self.stdout.write("[OK]")
        for item in ok:
            self.stdout.write(f"OK {item}")
        self.stdout.write("")
        self.stdout.write("[WARNING]")
        if warnings:
            for item in warnings:
                self.stdout.write(f"WARNING {item}")
        else:
            self.stdout.write("- none")
        self.stdout.write("")
        self.stdout.write("[FAIL]")
        if fails:
            for item in fails:
                self.stdout.write(f"FAIL {item}")
        else:
            self.stdout.write("- none")

        if fails:
            raise SystemExit(1)
        if options["verify"]:
            self.stdout.write("PHASE78_VERIFY_OK")
