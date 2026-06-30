from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="SwitchMap Phase94 read-only smoke runner")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    os.chdir(str(root))
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    import django
    django.setup()
    from django.core.management import call_command

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = args.output or str(root / "logs" / f"phase94_smoke_runner_{stamp}.json")
    cmd_args = ["--output", output]
    if args.strict:
        cmd_args.insert(0, "--strict")

    print("PHASE94_SMOKE_RUNNER_START")
    print("MODE=read_only_no_visible_test_data_no_network_no_ssh_no_backup_no_restore_no_service")
    print(f"ROOT={root}")
    print(f"REPORT_JSON={output}")
    call_command("phase94_verification_baseline_check", *cmd_args)
    print("PHASE94_SMOKE_RUNNER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
