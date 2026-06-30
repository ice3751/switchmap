from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError

from inventory.models import Port, Switch


EXPECTED_SWITCH_INDEXES = {
    "p77_sw_active_pos_idx": ["is_active", "topology_position"],
    "p77_sw_family_active_idx": ["device_family", "is_active"],
    "p77_sw_role_active_idx": ["device_role", "is_active"],
}

EXPECTED_PORT_INDEXES = {
    "p77_port_desc_idx": ["description"],
    "p77_port_cable_idx": ["cable_label"],
    "p77_port_iface_idx": ["interface_name"],
    "p77_port_status_idx": ["status"],
    "p77_port_mode_idx": ["port_mode"],
    "p77_port_doc_idx": ["documentation_status"],
    "p77_port_owner_idx": ["owner"],
    "p77_port_asset_idx": ["asset_tag"],
}


def _model_index_map(model) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for index in model._meta.indexes:
        result[index.name] = list(index.fields)
    return result


class Command(BaseCommand):
    help = "Phase96 read-only guard for model metadata alignment with Phase77 indexes."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        output = options.get("output") or ""
        self.stdout.write("PHASE96_MODEL_INDEX_ALIGNMENT_CHECK_START")
        self.stdout.write("MODE=read_only_model_metadata_no_db_no_migration_no_service")

        failures = []
        warnings = []

        switch_indexes = _model_index_map(Switch)
        port_indexes = _model_index_map(Port)

        for name, fields in EXPECTED_SWITCH_INDEXES.items():
            actual = switch_indexes.get(name)
            if actual == fields:
                self.stdout.write(f"OK=switch_index:{name}:{','.join(fields)}")
            else:
                failures.append({"type": "switch_index", "name": name, "expected": fields, "actual": actual})
                self.stdout.write(f"FAIL=switch_index:{name}:expected={fields}:actual={actual}")

        for name, fields in EXPECTED_PORT_INDEXES.items():
            actual = port_indexes.get(name)
            if actual == fields:
                self.stdout.write(f"OK=port_index:{name}:{','.join(fields)}")
            else:
                failures.append({"type": "port_index", "name": name, "expected": fields, "actual": actual})
                self.stdout.write(f"FAIL=port_index:{name}:expected={fields}:actual={actual}")

        report = {
            "phase": "PHASE96",
            "mode": "read_only_model_metadata_no_db_no_migration_no_service",
            "switch_indexes_checked": len(EXPECTED_SWITCH_INDEXES),
            "port_indexes_checked": len(EXPECTED_PORT_INDEXES),
            "warnings": warnings,
            "failures": failures,
            "final_fail_count": len(failures),
            "db_mutation": "NO",
            "migration_write": "NO",
            "service_restart": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "backup_write": "NO",
        }

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"REPORT_JSON={out_path}")

        self.stdout.write(f"FINAL_WARNING_COUNT={len(warnings)}")
        self.stdout.write(f"FINAL_FAIL_COUNT={len(failures)}")
        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("MIGRATION_WRITE=NO")
        self.stdout.write("SERVICE_RESTART=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("BACKUP_WRITE=NO")

        if failures and strict:
            self.stdout.write("PHASE96_MODEL_INDEX_ALIGNMENT_CHECK_FAIL")
            raise CommandError("Phase96 model index alignment failed")

        self.stdout.write("PHASE96_MODEL_INDEX_ALIGNMENT_CHECK_OK")
