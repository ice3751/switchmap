from __future__ import annotations

import getpass
import time

from django.core.management.base import BaseCommand, CommandError

from inventory.models import Switch
from inventory.secure_credentials import (
    CREDENTIAL_PROFILES,
    SecureCredentialError,
    credential_exists,
    credential_file,
    credential_status,
    delete_ssh_monitor_credentials,
    load_ssh_monitor_credentials,
    migrate_legacy_credential,
    save_ssh_monitor_credentials,
)
from inventory.ssh_tools import SshActionError, run_switch_show_commands

try:
    from inventory.views import _is_dashboard_test_device
except Exception:  # pragma: no cover
    def _is_dashboard_test_device(switch):
        name = str(getattr(switch, "name", "") or "").lower()
        return any(token in name for token in ("test", "smoke", "phase"))


def _switch_text(switch: Switch) -> str:
    return " ".join([
        str(getattr(switch, "vendor", "") or ""),
        str(getattr(switch, "device_family", "") or ""),
        str(getattr(switch, "model", "") or ""),
        str(getattr(switch, "name", "") or ""),
    ]).lower()


def _is_cisco_switch(switch: Switch) -> bool:
    return any(token in _switch_text(switch) for token in ("cisco", "catalyst", "nexus", "3850"))


def _is_mikrotik_switch(switch: Switch) -> bool:
    text = _switch_text(switch)
    return any(token in text for token in ("mikrotik", "routeros", "rb", "crs", "hex", "hap", "ax3", "cap-"))


def _eligible_ssh_test_switches(profile: str, switch_name: str = ""):
    qs = Switch.objects.filter(is_active=True, ssh_enabled=True).order_by("topology_position", "name")
    if switch_name:
        qs = qs.filter(name=switch_name)
    result = []
    for switch in qs:
        if _is_dashboard_test_device(switch):
            continue
        if profile == "cisco" and _is_cisco_switch(switch):
            result.append(switch)
        if profile == "mikrotik" and _is_mikrotik_switch(switch):
            result.append(switch)
    return result


def _require_paramiko():
    try:
        import paramiko
    except Exception as exc:
        raise SshActionError("Paramiko نصب یا قابل Import نیست.") from exc
    return paramiko


def _read_channel(channel, timeout=1.0):
    output = ""
    end = time.time() + timeout
    while time.time() < end:
        while channel.recv_ready():
            output += channel.recv(65535).decode("utf-8", errors="ignore")
            end = time.time() + 0.35
        time.sleep(0.08)
    return output


def _run_mikrotik_readonly_test(switch, username: str, password: str) -> dict:
    paramiko = _require_paramiko()
    client = None
    output = ""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            str(switch.management_ip),
            port=int(switch.ssh_port or 22),
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=12,
            auth_timeout=12,
            banner_timeout=12,
        )
        channel = client.invoke_shell(width=160, height=40)
        output += _read_channel(channel, 1.0)
        channel.send("/system identity print\n")
        output += _read_channel(channel, 1.4)
        if "bad username" in output.lower() or "failure" in output.lower():
            raise SshActionError("MikroTik SSH command failed.")
        return {"ok": True, "output": output}
    except paramiko.AuthenticationException as exc:
        raise SshActionError("SSH Authentication failed.") from exc
    except (TimeoutError, OSError) as exc:
        raise SshActionError("SSH Timeout.") from exc
    except SshActionError:
        raise
    except Exception as exc:
        raise SshActionError(str(exc)) from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


class Command(BaseCommand):
    help = "Set/status/delete/test Windows DPAPI protected SSH credentials for scheduled backup by vendor profile."

    def add_arguments(self, parser):
        parser.add_argument("--status", action="store_true")
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--test", action="store_true")
        parser.add_argument("--migrate-legacy", action="store_true")
        parser.add_argument("--switch", default="")
        parser.add_argument("--profile", choices=sorted(CREDENTIAL_PROFILES.keys()), default="cisco")
        parser.add_argument("--all", action="store_true")

    def _print_status_for_profile(self, profile: str):
        status = credential_status(profile)
        prefix = profile.upper()
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_EXISTS={'YES' if status['exists'] else 'NO'}")
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_FILE={status['file']}")
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_LOCATION={status.get('location', '')}")
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_RECOMMENDED_FILE={status.get('recommended_file', '')}")
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_LEGACY={'YES' if status.get('legacy') else 'NO'}")
        self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_WINDOWS_USER={status.get('windows_user', '')}")
        if status["exists"]:
            try:
                payload = load_ssh_monitor_credentials(profile=profile)
                self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_USER={payload.get('username', '')}")
                self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_CREATED_AT={payload.get('created_at', '')}")
                self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_SCOPE={payload.get('scope', '')}")
                self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_DECRYPT=OK")
            except SecureCredentialError as exc:
                self.stdout.write(f"{prefix}_SSH_MONITOR_CREDENTIAL_DECRYPT=FAIL {exc}")

    def handle(self, *args, **options):
        profile = str(options.get("profile") or "cisco").lower()

        if options["delete"]:
            removed = delete_ssh_monitor_credentials(profile=profile)
            self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_DELETED={'YES' if removed else 'NO_FILE'}")
            return

        if options["migrate_legacy"]:
            profiles = sorted(CREDENTIAL_PROFILES.keys()) if options.get("all") else [profile]
            for item in profiles:
                result = migrate_legacy_credential(profile=item)
                self.stdout.write(f"{item.upper()}_SSH_MONITOR_CREDENTIAL_MIGRATE={result}")
            return

        if options["status"]:
            profiles = sorted(CREDENTIAL_PROFILES.keys()) if options.get("all") else [profile]
            for item in profiles:
                self._print_status_for_profile(item)
            return

        if options["test"]:
            try:
                payload = load_ssh_monitor_credentials(profile=profile)
            except SecureCredentialError as exc:
                raise CommandError(str(exc)) from exc

            switch_name = str(options.get("switch") or "").strip()
            switches = _eligible_ssh_test_switches(profile, switch_name)
            if not switches:
                if switch_name:
                    raise CommandError(f"No {profile} SSH-enabled operational switch found for test: {switch_name}")
                raise CommandError(f"No {profile} SSH-enabled operational switch found for credential test.")

            last_error = ""
            for switch in switches:
                try:
                    if profile == "cisco":
                        result = run_switch_show_commands(
                            switch=switch,
                            username=payload["username"],
                            password=payload["password"],
                            enable_password=payload.get("enable_password", ""),
                            commands=["show clock"],
                            command_wait=1.0,
                        )
                        self.stdout.write(f"CISCO_SSH_MONITOR_CREDENTIAL_TEST=OK switch={switch.name} commands={len(result.get('commands', []))}")
                        return
                    result = _run_mikrotik_readonly_test(
                        switch=switch,
                        username=payload["username"],
                        password=payload["password"],
                    )
                    self.stdout.write(f"MIKROTIK_SSH_MONITOR_CREDENTIAL_TEST=OK switch={switch.name} ok={result.get('ok')}")
                    return
                except SshActionError as exc:
                    last_error = f"switch={switch.name} error={exc}"
            raise CommandError(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_TEST=FAIL {last_error}")

        username = input(f"{profile.upper()} scheduled backup username: ").strip()
        password = getpass.getpass(f"{profile.upper()} scheduled backup password: ")
        enable_password = ""
        if profile == "cisco":
            enable_password = getpass.getpass("Cisco enable password (blank = none): ")
        try:
            path = save_ssh_monitor_credentials(
                username=username,
                password=password,
                enable_password=enable_password,
                profile=profile,
            )
        except SecureCredentialError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_SAVED={path}")
        self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_SCOPE=Windows Current User DPAPI")
        self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_STORAGE=outside-project")
        self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_EXISTS={'YES' if credential_exists(profile=profile) else 'NO'}")
        self.stdout.write(f"{profile.upper()}_SSH_MONITOR_CREDENTIAL_FILE={credential_file(profile)}")
