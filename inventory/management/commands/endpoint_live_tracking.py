from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.endpoint_tracking import collect_candidates, choose_best_candidates, summarize, upsert_endpoints, write_candidate_csv


class Command(BaseCommand):
    help = "Phase112R8: live endpoint tracking foundation from DB port identity, SNMP ARP and SNMP FDB."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Collect and report only; do not write Endpoint tables.")
        parser.add_argument("--no-snmp", action="store_true", help="Use existing Port DB identity only; no live SNMP polling.")
        parser.add_argument("--no-db-port", action="store_true", help="Do not read existing Port identity fields.")
        parser.add_argument("--switch", default="", help="Limit to one SwitchMap device name.")
        parser.add_argument("--no-observation-write", action="store_true", help="Upsert NetworkEndpoint only; skip EndpointObservation rows.")
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        include_snmp = not bool(options["no_snmp"])
        include_db = not bool(options["no_db_port"])
        switch_name = (options.get("switch") or "").strip()
        quiet = bool(options["quiet"])
        write_observations = not bool(options["no_observation_write"])
        started = timezone.now()

        candidates, meta = collect_candidates(include_db=include_db, include_snmp=include_snmp, switch_name=switch_name)
        best = choose_best_candidates(candidates)
        summary = summarize(candidates, best, meta)
        stamp = started.strftime("%Y%m%d_%H%M%S")
        report_name = f"endpoint_live_tracking_r8_{'preview' if dry_run else 'apply'}_{stamp}.csv"
        report_path = write_candidate_csv(best.values(), report_name)

        mutation = not dry_run
        write_result = {"created": 0, "updated": 0, "observations_created": 0, "lock_skipped": 0, "db_write_errors": 0, "write_observations": write_observations, "busy_timeout_ms": 0, "retry_attempts": 0}
        if mutation:
            write_result = upsert_endpoints(best, write_observations=write_observations)

        lines = [
            "ENDPOINT_LIVE_TRACKING_R8_RUN",
            f"DB_MUTATION={'NO' if dry_run else 'YES'}",
            f"SNMP_POLL={'YES' if include_snmp else 'NO'}",
            f"DB_PORT_IDENTITY_READ={'YES' if include_db else 'NO'}",
            f"SWITCH_FILTER={switch_name or 'ALL'}",
            f"OBSERVATIONS_TOTAL={summary['observations_total']}",
            f"UNIQUE_ENDPOINT_CANDIDATES={summary['unique_endpoint_candidates']}",
            f"DEVICES_SCANNED={summary['devices_scanned']}",
            f"DEVICE_ERROR_COUNT={summary['device_error_count']}",
            f"BY_SOURCE={summary['by_source']}",
            f"BY_VLAN={summary['by_vlan']}",
            f"BY_CONNECTION_TYPE={summary['by_connection_type']}",
            f"REPORT_CSV={report_path}",
            f"SUMMARY_CREATED={write_result['created']}",
            f"SUMMARY_UPDATED={write_result['updated']}",
            f"SUMMARY_OBSERVATIONS_CREATED={write_result['observations_created']}",
            f"SUMMARY_LOCK_SKIPPED={write_result.get('lock_skipped', 0)}",
            f"SUMMARY_DB_WRITE_ERRORS={write_result.get('db_write_errors', 0)}",
            f"OBSERVATION_WRITE_ENABLED={'YES' if write_result.get('write_observations', write_observations) else 'NO'}",
            f"SQLITE_BUSY_TIMEOUT_MS={write_result.get('busy_timeout_ms', 0)}",
            f"DB_WRITE_RETRY_ATTEMPTS={write_result.get('retry_attempts', 0)}",
            "ENDPOINT_LIVE_TRACKING_R8_DONE=YES",
        ]
        if meta.get("device_errors"):
            lines.append(f"DEVICE_ERRORS_SAMPLE={meta.get('device_errors')[:5]}")
        if not quiet:
            for line in lines:
                self.stdout.write(str(line))
        return " ".join(lines[:8])
