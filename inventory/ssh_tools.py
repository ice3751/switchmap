import re
import time


class SshActionError(Exception):
    pass


SUPPORTED_ACTIONS = {
    "set_access_vlan": "تغییر VLAN دسترسی",
    "set_description": "ثبت Description",
    "clear_description": "حذف Description",
    "set_voice_vlan": "تغییر Voice VLAN",
    "remove_voice_vlan": "حذف Voice VLAN",
    "set_trunk_allowed": "تنظیم VLAN های Trunk",
    "add_trunk_vlan": "افزودن VLAN به Trunk",
    "remove_trunk_vlan": "حذف VLAN از Trunk",
    "shutdown": "Shutdown",
    "no_shutdown": "No Shutdown",
    "poe_auto": "PoE Auto",
    "poe_never": "PoE Off",
    "force_trunk": "Force Trunk",
}

RISKY_ACTIONS = {
    "shutdown",
    "poe_never",
    "set_voice_vlan",
    "remove_voice_vlan",
    "set_trunk_allowed",
    "add_trunk_vlan",
    "remove_trunk_vlan",
    "force_trunk",
}

TRUNK_FORCE_ACTIONS = {
    "set_trunk_allowed",
    "add_trunk_vlan",
    "remove_trunk_vlan",
    "force_trunk",
}

VLAN_LIST_PATTERN = re.compile(r"^[0-9,\- ]+$")
INVALID_OUTPUT_MARKERS = (
    "% invalid",
    "% incomplete",
    "% ambiguous",
    "authentication failed",
    "denied",
    "bad secrets",
)


def action_label(action):
    return SUPPORTED_ACTIONS.get(action, action or "-")


def action_requires_confirmation(action):
    return action in RISKY_ACTIONS


def action_requires_force(action, port=None):
    if action in TRUNK_FORCE_ACTIONS:
        return True
    if action in {"set_access_vlan", "set_voice_vlan", "remove_voice_vlan"} and port is not None:
        return getattr(port, "port_mode", "") == getattr(port, "PortMode", object()).TRUNK
    return False


def action_risk_text(action):
    risks = {
        "shutdown": "پورت خاموش می‌شود و ارتباط دستگاه قطع می‌شود.",
        "poe_never": "برق PoE قطع می‌شود؛ تلفن، دوربین یا AP ممکن است خاموش شود.",
        "set_voice_vlan": "Voice VLAN تغییر می‌کند؛ تلفن IP ممکن است رجیستر نشود.",
        "remove_voice_vlan": "Voice VLAN حذف می‌شود؛ تلفن IP ممکن است از کار بیفتد.",
        "set_trunk_allowed": "لیست Allowed VLAN روی Trunk بازنویسی می‌شود.",
        "add_trunk_vlan": "VLAN جدید به Trunk اضافه می‌شود.",
        "remove_trunk_vlan": "VLAN از Trunk حذف می‌شود و ممکن است ارتباط آن VLAN قطع شود.",
        "force_trunk": "پورت به Trunk تبدیل می‌شود.",
    }
    return risks.get(action, "")


def _require_paramiko():
    try:
        import paramiko
    except Exception as exc:
        raise SshActionError("Paramiko نصب یا قابل Import نیست. دستور نصب: pip install paramiko") from exc
    return paramiko


def _clean_interface(interface_name):
    interface_name = (interface_name or "").strip()
    if not interface_name:
        raise SshActionError("Interface نامعتبر است.")
    if any(token in interface_name for token in ["\n", "\r", ";", "|", "&"]):
        raise SshActionError("Interface نامعتبر است.")
    if not re.match(r"^[A-Za-z][A-Za-z0-9/_. -]{1,64}$", interface_name):
        raise SshActionError("Interface نامعتبر است.")
    return interface_name


def _parse_vlan(value):
    try:
        vlan = int(str(value).strip())
    except ValueError as exc:
        raise SshActionError("VLAN باید عددی باشد.") from exc

    if vlan < 1 or vlan > 4094:
        raise SshActionError("VLAN باید بین 1 و 4094 باشد.")
    return vlan


def _parse_vlan_list(value):
    raw_value = str(value or "").strip().replace(" ", "")
    if not raw_value:
        raise SshActionError("لیست VLAN خالی است.")
    if not VLAN_LIST_PATTERN.match(raw_value):
        raise SshActionError("فرمت VLAN مجاز نیست. نمونه: 1,100,101-110")

    parts = raw_value.split(",")
    for part in parts:
        if not part:
            raise SshActionError("لیست VLAN نامعتبر است.")
        if "-" in part:
            range_parts = part.split("-")
            if len(range_parts) != 2:
                raise SshActionError("Range VLAN نامعتبر است.")
            start = _parse_vlan(range_parts[0])
            end = _parse_vlan(range_parts[1])
            if start > end:
                raise SshActionError("Range VLAN نامعتبر است.")
        else:
            _parse_vlan(part)
    return raw_value


def _clean_description(value):
    description = str(value or "").strip()
    if not description:
        raise SshActionError("Description خالی است.")
    if "\n" in description or "\r" in description:
        raise SshActionError("Description نباید چند خطی باشد.")
    if len(description) > 180:
        raise SshActionError("Description بیش از حد طولانی است.")
    return description


def build_port_commands(port, action, value=None, force=False):
    interface_name = _clean_interface(port.interface_name)
    action = (action or "").strip()

    if action not in SUPPORTED_ACTIONS:
        raise SshActionError("Action نامعتبر است.")

    if action == "set_access_vlan":
        if port.port_mode == port.PortMode.TRUNK and not force:
            raise SshActionError("این پورت Trunk است. تغییر Access VLAN متوقف شد.")
        vlan = _parse_vlan(value)
        return [
            f"interface {interface_name}",
            "switchport mode access",
            f"switchport access vlan {vlan}",
        ]

    if action == "set_description":
        description = _clean_description(value)
        return [
            f"interface {interface_name}",
            f"description {description}",
        ]

    if action == "clear_description":
        return [
            f"interface {interface_name}",
            "no description",
        ]

    if action == "set_voice_vlan":
        if port.port_mode == port.PortMode.TRUNK and not force:
            raise SshActionError("این پورت Trunk است. تغییر Voice VLAN متوقف شد.")
        vlan = _parse_vlan(value)
        return [
            f"interface {interface_name}",
            "switchport mode access",
            f"switchport voice vlan {vlan}",
        ]

    if action == "remove_voice_vlan":
        if port.port_mode == port.PortMode.TRUNK and not force:
            raise SshActionError("این پورت Trunk است. حذف Voice VLAN متوقف شد.")
        return [
            f"interface {interface_name}",
            "no switchport voice vlan",
        ]

    if action == "set_trunk_allowed":
        if not force:
            raise SshActionError("برای تغییر Trunk باید تیک اجازه تغییر روی پورت Trunk فعال باشد.")
        vlan_list = _parse_vlan_list(value)
        return [
            f"interface {interface_name}",
            "switchport mode trunk",
            f"switchport trunk allowed vlan {vlan_list}",
        ]

    if action == "add_trunk_vlan":
        if not force:
            raise SshActionError("برای تغییر Trunk باید تیک اجازه تغییر روی پورت Trunk فعال باشد.")
        vlan_list = _parse_vlan_list(value)
        return [
            f"interface {interface_name}",
            "switchport mode trunk",
            f"switchport trunk allowed vlan add {vlan_list}",
        ]

    if action == "remove_trunk_vlan":
        if not force:
            raise SshActionError("برای تغییر Trunk باید تیک اجازه تغییر روی پورت Trunk فعال باشد.")
        vlan_list = _parse_vlan_list(value)
        return [
            f"interface {interface_name}",
            f"switchport trunk allowed vlan remove {vlan_list}",
        ]

    if action == "force_trunk":
        if not force:
            raise SshActionError("برای Force Trunk باید تیک اجازه تغییر روی پورت Trunk فعال باشد.")
        return [
            f"interface {interface_name}",
            "switchport mode trunk",
        ]

    if action == "shutdown":
        return [
            f"interface {interface_name}",
            "shutdown",
        ]

    if action == "no_shutdown":
        return [
            f"interface {interface_name}",
            "no shutdown",
        ]

    if action == "poe_auto":
        return [
            f"interface {interface_name}",
            "power inline auto",
        ]

    if action == "poe_never":
        return [
            f"interface {interface_name}",
            "power inline never",
        ]

    raise SshActionError("Action پشتیبانی نمی‌شود.")


def _read_channel(channel, timeout=1.0):
    output = ""
    end = time.time() + timeout
    while time.time() < end:
        while channel.recv_ready():
            output += channel.recv(65535).decode("utf-8", errors="ignore")
            end = time.time() + 0.35
        time.sleep(0.08)
    return output


def _send(channel, command, wait=0.8):
    channel.send(command + "\n")
    return _read_channel(channel, wait)



READONLY_COMMAND_PREFIXES = (
    "show ",
    "terminal length",
)


def _clean_readonly_command(command):
    command = str(command or "").strip()
    if not command:
        raise SshActionError("Command خالی است.")
    if any(token in command for token in ["\n", "\r", ";", "|", "&"]):
        raise SshActionError("Command نامعتبر است.")
    lowered = command.lower()
    if not lowered.startswith(READONLY_COMMAND_PREFIXES):
        raise SshActionError("فقط دستورهای Read-Only مجاز است.")
    return command


def run_switch_show_commands(switch, username, password, commands, enable_password="", command_wait=1.2):
    if not switch.ssh_enabled:
        raise SshActionError("SSH برای این سوییچ فعال نیست.")

    username = (username or switch.ssh_username or "").strip()
    password = password or ""
    enable_password = enable_password or ""
    clean_commands = [_clean_readonly_command(command) for command in commands]

    if not username:
        raise SshActionError("Username خالی است.")
    if not password:
        raise SshActionError("Password خالی است.")

    paramiko = _require_paramiko()
    client = None
    output = ""
    command_outputs = {}

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

        channel = client.invoke_shell(width=220, height=80)
        output += _read_channel(channel, 1.0)
        terminal_output = _send(channel, "terminal length 0", 0.8)
        output += terminal_output
        command_outputs["terminal length 0"] = terminal_output

        if enable_password:
            enable_output = _send(channel, "enable", 0.8)
            output += enable_output
            if "password" in enable_output.lower():
                password_output = _send(channel, enable_password, 0.9)
                output += password_output

        for command in clean_commands:
            current_output = _send(channel, command, command_wait)
            output += current_output
            command_outputs[command] = current_output

        if any(marker in output.lower() for marker in INVALID_OUTPUT_MARKERS):
            raise SshActionError("سوییچ خطا برگرداند.")

        return {
            "ok": True,
            "commands": clean_commands,
            "output": output,
            "outputs": command_outputs,
        }
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

def run_port_action(switch, port, username, password, action, value=None, enable_password="", force=False):
    if not switch.ssh_enabled:
        raise SshActionError("SSH برای این سوییچ فعال نیست.")

    username = (username or switch.ssh_username or "").strip()
    password = password or ""
    enable_password = enable_password or password

    if not username:
        raise SshActionError("Username خالی است.")
    if not password:
        raise SshActionError("Password خالی است.")

    commands = build_port_commands(
        port=port,
        action=action,
        value=value,
        force=force,
    )

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

        channel = client.invoke_shell(width=180, height=50)
        output += _read_channel(channel, 1.0)
        output += _send(channel, "terminal length 0", 0.8)

        if enable_password:
            output += _send(channel, "enable", 0.8)
            if "password" in output.lower():
                output += _send(channel, enable_password, 0.9)

        output += _send(channel, "configure terminal", 0.8)
        for command in commands:
            output += _send(channel, command, 0.9)
        output += _send(channel, "end", 0.8)

        if any(marker in output.lower() for marker in INVALID_OUTPUT_MARKERS):
            raise SshActionError("سوییچ خطا برگرداند.")

        verify = _send(channel, f"show running-config interface {port.interface_name}", 1.0)
        status_output = _send(channel, "show interfaces status", 1.0)
        mac_output = _send(channel, f"show mac address-table interface {port.interface_name}", 1.0)

        return {
            "ok": True,
            "commands": commands,
            "output": output,
            "verify": verify,
            "status_output": status_output,
            "mac_output": mac_output,
        }
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


def run_bulk_port_actions(switch, ports, username, password, action, value=None, enable_password="", force=False):
    if not switch.ssh_enabled:
        raise SshActionError("SSH برای این سوییچ فعال نیست.")

    username = (username or switch.ssh_username or "").strip()
    password = password or ""
    enable_password = enable_password or password

    if not username:
        raise SshActionError("Username خالی است.")
    if not password:
        raise SshActionError("Password خالی است.")

    prepared = []
    results = []
    for port in ports:
        try:
            commands = build_port_commands(
                port=port,
                action=action,
                value=value,
                force=force,
            )
            prepared.append((port, commands))
        except SshActionError as exc:
            results.append({
                "ok": False,
                "port_id": port.id,
                "interface": port.interface_name,
                "commands": [],
                "message": str(exc),
            })

    if not prepared:
        return {"ok": False, "results": results}

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

        channel = client.invoke_shell(width=180, height=70)
        output += _read_channel(channel, 1.0)
        output += _send(channel, "terminal length 0", 0.8)

        if enable_password:
            enable_output = _send(channel, "enable", 0.8)
            output += enable_output
            if "password" in enable_output.lower():
                password_output = _send(channel, enable_password, 0.9)
                output += password_output

        output += _send(channel, "configure terminal", 0.8)
        for port, commands in prepared:
            port_output = ""
            for command in commands:
                port_output += _send(channel, command, 0.55)
            if any(marker in port_output.lower() for marker in INVALID_OUTPUT_MARKERS):
                results.append({
                    "ok": False,
                    "port_id": port.id,
                    "interface": port.interface_name,
                    "commands": commands,
                    "message": "سوییچ خطا برگرداند.",
                    "output": port_output,
                })
            else:
                results.append({
                    "ok": True,
                    "port_id": port.id,
                    "interface": port.interface_name,
                    "commands": commands,
                    "message": "OK",
                    "output": port_output,
                })
            output += port_output
        output += _send(channel, "end", 0.8)

        return {
            "ok": all(item.get("ok") for item in results),
            "results": results,
            "output": output,
        }
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
