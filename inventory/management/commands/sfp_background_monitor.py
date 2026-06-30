from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from inventory.models import AlarmNotification, AlarmPolicyState, Port, SfpMonitorSnapshot, Switch
from inventory.alarm_rules import AlarmCandidate, evaluate_alarm_candidates, sfp_alarm_details, sfp_rule_key_for_tag, sfp_severity_for_tag
from inventory.alarm_policy import cisco_crc_alarm_is_actionable, physical_error_delta
from inventory.secure_credentials import SecureCredentialError, load_ssh_monitor_credentials
from inventory.ssh_tools import SshActionError, run_switch_show_commands
from inventory.views import (
    _alarm_slug,
    _is_dashboard_test_device,
    _latest_sfp_alarm_items,
    _poll_sfp_monitor,
    _sfp_issue_labels_for_snapshot,
    _sync_alarm_notifications,
)


STATUS_FILE = Path(settings.BASE_DIR) / "logs" / "sfp-background-monitor-status.json"
CRC_STATE_FILE = Path(settings.BASE_DIR) / "logs" / "cisco-crc-monitor-state.json"
CRC_PREFIX = "cisco-crc:"
CISCO_ERRDISABLED_PREFIX = "cisco-errdisabled:"
CRC_WARNING_DELTA = 10
CRC_CRITICAL_DELTA = 100


def _force_alarm_upsert(*, fingerprint, source, category, severity, title, message, switch=None, port=None, details="", count_occurrence=True, observed_at=None):
    # PHASE83R_ALARM_ENGINE_V2_SINGLE_WRITER
    from inventory.alarm_engine import AlarmEvidenceCandidate, process_alarm_candidates
    from inventory.alarm_policy import _deltas_from_alarm_details

    if str(fingerprint or "").startswith("cisco-errdisabled:"):
        rule_key = "cisco_errdisabled"
        evidence_type = "cisco_interface_status"
        delta_value = details or ""
    elif str(fingerprint or "").startswith("cisco-crc:") or title == "Cisco CRC/Input/Output Error Increased":
        rule_key = "cisco_crc_delta"
        evidence_type = "crc_counter_delta"
        delta_value = str(_deltas_from_alarm_details(details or message))
    elif str(fingerprint or "").startswith("sfp:"):
        if title == "Err-disabled":
            rule_key = "sfp_err_disabled"
        elif title in {"Rx Power abnormal", "Tx Power abnormal", "Temperature abnormal"}:
            rule_key = "sfp_optical_threshold"
        else:
            rule_key = "sfp_counter_delta"
        evidence_type = "sfp_snapshot"
        delta_value = details or ""
    else:
        rule_key = "interface_error"
        evidence_type = "legacy_background_alarm"
        delta_value = ""

    candidate = AlarmEvidenceCandidate(
        rule_key=rule_key,
        fingerprint=fingerprint,
        source=source,
        category=category,
        severity=severity,
        title=title,
        message=message,
        switch=switch,
        port=port,
        details=details,
        observed_at=observed_at,
        evidence_key=f"{rule_key}|{observed_at}|{fingerprint}|{details or message}",
        evidence_type=evidence_type,
        raw_value=message,
        delta_value=delta_value,
        admin_status=getattr(port, "snmp_admin_status", "") if port else "",
        oper_status=getattr(port, "snmp_oper_status", "") if port else "",
        link_status=getattr(port, "status", "") if port else "",
        force_immediate=bool(
            count_occurrence
            and (
                rule_key in {"cisco_errdisabled", "sfp_err_disabled"}
                or (rule_key == "cisco_crc_delta" and severity == AlarmNotification.Severity.CRITICAL)
            )
        ),
    )
    process_alarm_candidates([candidate], resolve_stale=False)
    return AlarmNotification.objects.filter(fingerprint=fingerprint).first()

def _reactivate_current_sfp_alarms() -> int:
    # PHASE83R_ALARM_ENGINE_V2_SINGLE_WRITER
    from inventory.alarm_engine import sync_alarm_notifications_v2
    result = sync_alarm_notifications_v2()
    return int(result.get("emitted", 0) or 0)

COUNTER_ALIASES = {
    "align-err": "align_errors",
    "fcs-err": "fcs_errors",
    "xmit-err": "xmit_errors",
    "rcv-err": "rcv_errors",
    "in-err": "input_errors",
    "input-err": "input_errors",
    "input-errors": "input_errors",
    "out-err": "output_errors",
    "output-err": "output_errors",
    "output-errors": "output_errors",
    "outdiscards": "out_discards",
    "out-discards": "out_discards",
}


def _switch_text(switch: Switch) -> str:
    return " ".join([
        str(getattr(switch, "vendor", "") or ""),
        str(getattr(switch, "device_family", "") or ""),
        str(getattr(switch, "model", "") or ""),
        str(getattr(switch, "name", "") or ""),
    ]).lower()


def _is_cisco_switch(switch: Switch) -> bool:
    return any(token in _switch_text(switch) for token in ("cisco", "catalyst", "nexus", "3850"))


def _is_nexus_switch(switch: Switch) -> bool:
    return "nexus" in _switch_text(switch)


def _normalize_interface_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        return value
    value = re.sub(r"^Ethernet(?=\d+/\d+)", "Ethernet", value, flags=re.IGNORECASE)
    value = re.sub(r"^Eth(?=\d+/\d+)", "Ethernet", value, flags=re.IGNORECASE)
    value = re.sub(r"^GigabitEthernet(?=\d+/\d+/\d+)", "Gi", value, flags=re.IGNORECASE)
    value = re.sub(r"^TenGigabitEthernet(?=\d+/\d+/\d+)", "Te", value, flags=re.IGNORECASE)
    value = re.sub(r"^Gi(?=\d+/\d+/\d+)", "Gi", value, flags=re.IGNORECASE)
    value = re.sub(r"^Te(?=\d+/\d+/\d+)", "Te", value, flags=re.IGNORECASE)
    return value


def _short_interface_alias(name: str) -> str:
    value = str(name or "").strip()
    return re.sub(r"^Ethernet(?=\d+/\d+)", "Eth", value, flags=re.IGNORECASE)


def _status_from_nxos_oper(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"connected", "up"}:
        return "connected"
    if text in {"notconnect", "down", "sfpabsent", "xcvrabsent"}:
        return "notconnect"
    if text in {"disabled", "admin-down", "admin down"}:
        return "disabled"
    if "err" in text and "disable" in text:
        return "err-disabled"
    return text or "unknown"


def _eligible_switches(switch_name: str = ""):
    qs = Switch.objects.filter(is_active=True, ssh_enabled=True).order_by("topology_position", "name")
    if switch_name:
        qs = qs.filter(name=switch_name)
    return [switch for switch in qs if _is_cisco_switch(switch) and not _is_dashboard_test_device(switch)]


def _to_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def _to_decimal(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_all_cisco_error_counters(output: str) -> dict:
    counters = {}
    headers = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("port"):
            headers = [part.strip().lower() for part in re.split(r"\s+", lower)]
            continue
        if not headers:
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        iface = parts[0].strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9/_.:-]{1,80}$", iface):
            continue
        values = [_to_int(value) for value in parts[1:]]
        item = {}
        for header, value in zip(headers[1:], values):
            field = COUNTER_ALIASES.get(header)
            if field:
                item[field] = item.get(field, 0) + value
        if item:
            counters[iface] = item
    return counters


def _load_crc_state() -> dict:
    if not CRC_STATE_FILE.exists():
        return {}
    try:
        return json.loads(CRC_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_crc_state(state: dict):
    CRC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CRC_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _delta(current: int, previous: int) -> int:
    current = _to_int(current)
    previous = _to_int(previous)
    if current < previous:
        return 0
    return current - previous


def _port_map_for_switch(switch: Switch) -> dict:
    result = {}
    for port in Port.objects.filter(switch=switch):
        result[port.interface_name] = port
        result[_short_interface_alias(port.interface_name)] = port
        result[_normalize_interface_name(port.interface_name)] = port
    return result


def _sfp_interface_port_map_for_background(switch: Switch) -> dict:
    if _is_nexus_switch(switch):
        result = {}
        for port in Port.objects.filter(switch=switch).order_by("display_order", "interface_name"):
            result[port.interface_name] = port
            result[_short_interface_alias(port.interface_name)] = port
            result[_normalize_interface_name(port.interface_name)] = port
        return result
    return _port_map_for_switch(switch)


def _parse_nxos_status(output: str) -> dict:
    status_map = {}
    for raw_line in str(output or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        if line.lower().lstrip().startswith("port"):
            continue
        parts = re.split(r"\s+", line.strip(), maxsplit=6)
        if len(parts) < 4:
            continue
        iface = _normalize_interface_name(parts[0])
        if not re.match(r"^Ethernet\d+/\d+$", iface, re.IGNORECASE):
            continue
        status = parts[2] if len(parts) >= 3 else ""
        vlan = parts[3] if len(parts) >= 4 else ""
        duplex = parts[4] if len(parts) >= 5 else ""
        speed = parts[5] if len(parts) >= 6 else ""
        media_type = parts[6] if len(parts) >= 7 else ""
        status_map[iface] = {
            "interface_name": iface,
            "link_status": _status_from_nxos_oper(status),
            "vlan_text": vlan,
            "duplex": duplex,
            "speed": speed,
            "media_type": media_type,
            "raw_status_line": line.strip(),
        }
    return status_map


def _parse_nxos_transceiver_details(output: str) -> dict:
    data = {}
    current_iface = ""
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        iface_match = re.match(r"^(Ethernet|Eth)(?P<num>\d+/\d+)\b", line, re.IGNORECASE)
        if iface_match:
            current_iface = _normalize_interface_name(iface_match.group(0))
            data.setdefault(current_iface, {})
            continue
        if not current_iface:
            continue
        numbers = re.findall(r"-?\d+(?:\.\d+)?", line)
        if not numbers:
            continue
        lower = line.lower()
        value = numbers[0]
        item = data.setdefault(current_iface, {})
        if "temperature" in lower:
            item["temperature_c"] = _to_decimal(value)
        elif "voltage" in lower:
            item["voltage_v"] = _to_decimal(value)
        elif "current" in lower:
            item["current_ma"] = _to_decimal(value)
        elif "tx" in lower and "power" in lower:
            item["tx_power_dbm"] = _to_decimal(value)
        elif "rx" in lower and "power" in lower:
            item["rx_power_dbm"] = _to_decimal(value)
    return {iface: values for iface, values in data.items() if values}


def _create_sfp_snapshots_from_maps(switch, status_map, counter_map, transceiver_map):
    from inventory.views import (
        SFP_HISTORY_KEEP,
        _delta,
        _health_for_sfp,
        _latest_sfp_snapshot_map,
    )

    port_map = _sfp_interface_port_map_for_background(switch)
    latest_map = _latest_sfp_snapshot_map(switch)
    interface_names = set()
    interface_names.update(_normalize_interface_name(k) for k in status_map)
    interface_names.update(_normalize_interface_name(k) for k in counter_map)
    interface_names.update(_normalize_interface_name(k) for k in transceiver_map)
    interface_names.update(_normalize_interface_name(port.interface_name) for port in set(port_map.values()))

    created = []
    for interface_name in sorted(interface_names):
        data = {
            "interface_name": interface_name,
            "link_status": "",
            "vlan_text": "",
            "duplex": "",
            "speed": "",
            "media_type": "",
            "raw_status_line": "",
            "align_errors": 0,
            "fcs_errors": 0,
            "xmit_errors": 0,
            "rcv_errors": 0,
            "input_errors": 0,
            "output_errors": 0,
            "out_discards": 0,
        }
        data.update(status_map.get(interface_name, {}))
        data.update(counter_map.get(interface_name, {}))
        data.update(transceiver_map.get(interface_name, {}))
        if not data.get("input_errors") and data.get("rcv_errors"):
            data["input_errors"] = data["rcv_errors"]
        if not data.get("output_errors") and data.get("xmit_errors"):
            data["output_errors"] = data["xmit_errors"]
        data["err_disabled"] = "err-disabled" in str(data.get("link_status") or "").lower()

        previous = latest_map.get(interface_name)
        if previous is None:
            data["align_delta"] = 0
            data["fcs_delta"] = 0
            data["xmit_delta"] = 0
            data["rcv_delta"] = 0
            data["input_error_delta"] = 0
            data["output_error_delta"] = 0
            data["out_discard_delta"] = 0
        else:
            data["align_delta"] = _delta(data.get("align_errors"), getattr(previous, "align_errors", 0))
            data["fcs_delta"] = _delta(data.get("fcs_errors"), getattr(previous, "fcs_errors", 0))
            data["xmit_delta"] = _delta(data.get("xmit_errors"), getattr(previous, "xmit_errors", 0))
            data["rcv_delta"] = _delta(data.get("rcv_errors"), getattr(previous, "rcv_errors", 0))
            data["input_error_delta"] = _delta(data.get("input_errors"), getattr(previous, "input_errors", 0))
            data["output_error_delta"] = _delta(data.get("output_errors"), getattr(previous, "output_errors", 0))
            data["out_discard_delta"] = _delta(data.get("out_discards"), getattr(previous, "out_discards", 0))
        data["health_state"], data["health_note"] = _health_for_sfp(data)

        port = port_map.get(interface_name) or port_map.get(_short_interface_alias(interface_name))
        created.append(SfpMonitorSnapshot.objects.create(
            switch=switch,
            port=port,
            **data,
        ))

        old_ids = list(
            SfpMonitorSnapshot.objects
            .filter(switch=switch, interface_name=interface_name)
            .order_by("-poll_time", "-id")
            .values_list("id", flat=True)[SFP_HISTORY_KEEP:]
        )
        if old_ids:
            SfpMonitorSnapshot.objects.filter(id__in=old_ids).delete()
    return created


def _poll_nexus_sfp_monitor(switch, username: str, password: str, enable_password: str = "") -> dict:
    commands = [
        "show interface status",
        "show interface counters errors",
        "show interface transceiver details",
    ]
    result = run_switch_show_commands(
        switch=switch,
        username=username,
        password=password,
        enable_password=enable_password,
        commands=commands,
        command_wait=1.8,
    )
    outputs = result.get("outputs", {})
    status_map = _parse_nxos_status(outputs.get("show interface status", ""))
    counter_map = {
        _normalize_interface_name(iface): values
        for iface, values in _parse_all_cisco_error_counters(outputs.get("show interface counters errors", "")).items()
    }
    transceiver_map = _parse_nxos_transceiver_details(outputs.get("show interface transceiver details", ""))
    created = _create_sfp_snapshots_from_maps(switch, status_map, counter_map, transceiver_map)
    return {"ok": True, "created": len(created), "snapshots": created, "commands": commands}


IOS_INTERFACE_STATUS_RE = re.compile(
    r"^\s*(?P<iface>[A-Za-z]+\d+/\d+/\d+)\s+(?P<name>.*?)\s+"
    r"(?P<status>connected|notconnect|disabled|err-disabled|inactive|suspended|monitoring|up|down)\s+"
    r"(?P<vlan>\S+)\s+(?P<duplex>\S+)\s+(?P<speed>\S+)\s*(?P<type>.*)$",
    re.IGNORECASE,
)


def _parse_ios_interface_status_all(output: str) -> dict:
    status_map = {}
    for raw_line in str(output or "").splitlines():
        match = IOS_INTERFACE_STATUS_RE.match(raw_line)
        if not match:
            continue
        iface = _normalize_interface_name(match.group("iface"))
        status_map[iface] = {
            "interface_name": iface,
            "link_status": str(match.group("status") or "").strip().lower(),
            "vlan_text": str(match.group("vlan") or "").strip(),
            "duplex": str(match.group("duplex") or "").strip(),
            "speed": str(match.group("speed") or "").strip(),
            "media_type": str(match.group("type") or "").strip(),
            "raw_status_line": raw_line.strip(),
        }
    return status_map


def _is_errdisabled_status(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text == "err-disabled" or ("err" in text and "disable" in text)


def _is_fresh_link_up_status(value: str) -> bool:
    return str(value or "").strip().lower() in {"connected", "up"}


def _is_probable_sfp_crc_target(switch: Switch, iface: str, port: Port | None, status_values: dict | None = None) -> bool:
    """Restrict Cisco CRC alarms to likely SFP/fiber interfaces to avoid access copper noise."""
    iface_text = str(iface or getattr(port, "interface_name", "") or "").strip().lower()
    switch_text = _switch_text(switch)
    media_text = str((status_values or {}).get("media_type") or "").strip().lower()
    port_text = " ".join([
        str(getattr(port, "interface_name", "") or ""),
        str(getattr(port, "snmp_raw_name", "") or ""),
        str(getattr(port, "cable_type", "") or ""),
        str(getattr(port, "description", "") or ""),
        str(getattr(port, "notes", "") or ""),
    ]).lower()

    copper_tokens = ("rj45", "copper", "utp", "10/100/1000base-t", "1000base-t", "base-t", "base-tx", "tx")
    if media_text and any(token in media_text for token in copper_tokens):
        return False

    optic_tokens = ("sfp", "xfp", "qsfp", "gbic", "transceiver", "twinax", "dac", "fiber", "fibre", "optic", "sr", "lr", "lx", "lh", "er", "zr", "bx", "cx")
    if media_text and any(token in media_text for token in optic_tokens):
        return True
    if any(token in port_text for token in ("sfp", "fiber", "fibre", "optic", "transceiver", "uplink fiber")):
        return True
    if re.match(r"^(te|tengigabitethernet|fo|fortygigabitethernet|hu|hundredgig|twe|twentyfivegig)", iface_text):
        return True
    if iface_text.startswith("ethernet") and "nexus" in switch_text:
        return True
    return False


def _run_cisco_errdisabled_monitor(switches, username: str, password: str, enable_password: str = "") -> dict:
    """Detect err-disabled on all Cisco physical ports, not only SFP/uplink ports."""
    from inventory.alarm_engine import AlarmEvidenceCandidate, process_alarm_candidates

    now = timezone.now()
    active_fingerprints = set()
    candidates = []
    results = []
    ok_switch_ids = []
    ok = 0
    failed = 0

    for switch in switches:
        command = "show interface status" if _is_nexus_switch(switch) else "show interfaces status"
        item = {"switch": switch.name, "ip": str(switch.management_ip), "ok": False, "interfaces": 0, "errdisabled": 0, "error": ""}
        try:
            result = run_switch_show_commands(
                switch=switch,
                username=username,
                password=password,
                enable_password=enable_password,
                commands=[command],
                command_wait=1.6,
            )
            output = result.get("outputs", {}).get(command, "")
            status_map = _parse_nxos_status(output) if _is_nexus_switch(switch) else _parse_ios_interface_status_all(output)
            if not status_map:
                raise ValueError("interface_status_parse_empty")
            port_map = _port_map_for_switch(switch)
            item["interfaces"] = len(status_map)

            for iface, values in sorted(status_map.items()):
                if not _is_errdisabled_status(values.get("link_status")):
                    continue
                port = port_map.get(iface) or port_map.get(_short_interface_alias(iface)) or port_map.get(_normalize_interface_name(iface))
                fingerprint = f"{CISCO_ERRDISABLED_PREFIX}{switch.id}:{_alarm_slug(iface)}"
                active_fingerprints.add(fingerprint)
                raw_line = values.get("raw_status_line") or ""
                details = (
                    f"status=err-disabled; vlan={values.get('vlan_text') or '-'}; "
                    f"duplex={values.get('duplex') or '-'}; speed={values.get('speed') or '-'}; "
                    f"type={values.get('media_type') or '-'}; raw={raw_line}"
                )
                candidates.append(AlarmEvidenceCandidate(
                    rule_key="cisco_errdisabled",
                    fingerprint=fingerprint,
                    source="Cisco Interface Status",
                    category=AlarmNotification.Category.INTERFACE,
                    severity=AlarmNotification.Severity.CRITICAL,
                    title="Err-disabled",
                    message=f"{switch.name} {iface}: err-disabled",
                    switch=switch,
                    port=port,
                    details=details,
                    observed_at=now,
                    evidence_key=f"cisco-errdisabled|{switch.id}|{iface}|err-disabled",
                    evidence_type="cisco_interface_status",
                    raw_value=raw_line,
                    admin_status=getattr(port, "snmp_admin_status", "") if port else "",
                    oper_status="err-disabled",
                    link_status="err-disabled",
                ))
                item["errdisabled"] += 1
            item["ok"] = True
            ok_switch_ids.append(switch.id)
            ok += 1
        except Exception as exc:
            failed += 1
            item["error"] = str(exc)
        results.append(item)

    alarm_result = process_alarm_candidates(candidates, resolve_stale=False) if candidates else {"emitted": 0, "pending": 0, "active": 0}

    stale = (
        AlarmNotification.objects
        .filter(fingerprint__startswith=CISCO_ERRDISABLED_PREFIX, switch_id__in=ok_switch_ids)
        .exclude(fingerprint__in=active_fingerprints)
        .exclude(status=AlarmNotification.Status.RESOLVED)
    )
    stale_fps = list(stale.values_list("fingerprint", flat=True))
    stale_resolved = stale.update(status=AlarmNotification.Status.RESOLVED, resolved_at=now)
    if stale_fps:
        AlarmPolicyState.objects.filter(fingerprint__in=stale_fps).update(
            state=AlarmPolicyState.State.RESOLVED,
            last_resolved_at=now,
            updated_at=now,
        )

    return {
        "ok": ok,
        "failed": failed,
        "interfaces": sum(int(item.get("interfaces", 0) or 0) for item in results),
        "errdisabled": sum(int(item.get("errdisabled", 0) or 0) for item in results),
        "alarms_emitted": int(alarm_result.get("emitted", 0) or 0),
        "alarms_pending": int(alarm_result.get("pending", 0) or 0),
        "stale_resolved": int(stale_resolved or 0),
        "results": results,
    }


def _run_cisco_crc_monitor(switches, username: str, password: str, enable_password: str = "") -> dict:
    state = _load_crc_state()
    now = timezone.now()
    active_fingerprints = set()
    results = []
    ok_switch_ids = []
    ok = 0
    failed = 0
    alarm_count = 0

    for switch in switches:
        item = {"switch": switch.name, "ip": str(switch.management_ip), "ok": False, "interfaces": 0, "alarms": 0, "error": ""}
        try:
            crc_command = "show interface counters errors" if _is_nexus_switch(switch) else "show interfaces counters errors"
            status_command = "show interface status" if _is_nexus_switch(switch) else "show interfaces status"
            result = run_switch_show_commands(
                switch=switch,
                username=username,
                password=password,
                enable_password=enable_password,
                commands=[crc_command, status_command],
                command_wait=1.6,
            )
            outputs = result.get("outputs", {})
            output = outputs.get(crc_command, "")
            status_output = outputs.get(status_command, "")
            counters = {
                _normalize_interface_name(iface): values
                for iface, values in _parse_all_cisco_error_counters(output).items()
            }
            status_map = _parse_nxos_status(status_output) if _is_nexus_switch(switch) else _parse_ios_interface_status_all(status_output)
            if not counters:
                raise ValueError("crc_counter_parse_empty")
            if not status_map:
                raise ValueError("interface_status_parse_empty")
            item["interfaces"] = len(counters)
            port_map = _port_map_for_switch(switch)
            switch_state = state.setdefault(str(switch.id), {})

            for iface, values in counters.items():
                previous = switch_state.get(iface, {})
                deltas = {
                    "align_delta": _delta(values.get("align_errors", 0), previous.get("align_errors", 0)),
                    "fcs_delta": _delta(values.get("fcs_errors", 0), previous.get("fcs_errors", 0)),
                    "input_delta": _delta(values.get("input_errors", values.get("rcv_errors", 0)), previous.get("input_errors", previous.get("rcv_errors", 0))),
                    "output_delta": _delta(values.get("output_errors", values.get("xmit_errors", 0)), previous.get("output_errors", previous.get("xmit_errors", 0))),
                    "rcv_delta": _delta(values.get("rcv_errors", 0), previous.get("rcv_errors", 0)),
                    "xmit_delta": _delta(values.get("xmit_errors", 0), previous.get("xmit_errors", 0)),
                    "out_discard_delta": _delta(values.get("out_discards", 0), previous.get("out_discards", 0)),
                }
                switch_state[iface] = {**values, "last_poll": now.isoformat()}

                if not previous:
                    continue

                port = port_map.get(iface) or port_map.get(_short_interface_alias(iface)) or port_map.get(_normalize_interface_name(iface))
                fresh_status = status_map.get(iface) or status_map.get(_short_interface_alias(iface)) or status_map.get(_normalize_interface_name(iface)) or {}
                if not _is_fresh_link_up_status(fresh_status.get("link_status")):
                    continue
                if not _is_probable_sfp_crc_target(switch, iface, port, fresh_status):
                    continue
                policy_deltas = {
                    "align_delta": deltas["align_delta"],
                    "fcs_delta": deltas["fcs_delta"],
                    "input_error_delta": deltas["input_delta"],
                    "output_error_delta": deltas["output_delta"],
                    "rcv_delta": deltas["rcv_delta"],
                    "xmit_delta": deltas["xmit_delta"],
                    "out_discard_delta": deltas["out_discard_delta"],
                }
                actionable, policy_reason = cisco_crc_alarm_is_actionable(
                    port,
                    policy_deltas,
                    fresh_link_up=True,
                    fresh_sfp_target=True,
                    require_port=False,
                )
                if not actionable:
                    continue

                total_error_delta = physical_error_delta(policy_deltas)
                fingerprint = f"{CRC_PREFIX}{switch.id}:{_alarm_slug(iface)}"
                active_fingerprints.add(fingerprint)
                severity = AlarmNotification.Severity.CRITICAL if total_error_delta >= CRC_CRITICAL_DELTA else AlarmNotification.Severity.WARNING
                details = (
                    f"alignΔ={deltas['align_delta']}, fcsΔ={deltas['fcs_delta']}, inputΔ={deltas['input_delta']}, "
                    f"outputΔ={deltas['output_delta']}, rcvΔ={deltas['rcv_delta']}, xmitΔ={deltas['xmit_delta']}, "
                    f"outDiscardΔ={deltas['out_discard_delta']}; policy={policy_reason}"
                )
                _force_alarm_upsert(
                    fingerprint=fingerprint,
                    source="Cisco CRC Monitor",
                    category=AlarmNotification.Category.INTERFACE,
                    severity=severity,
                    title="Cisco CRC/Input/Output Error Increased",
                    message=f"{switch.name} {iface}: {details}",
                    switch=switch,
                    port=port,
                    details=details,
                )
                item["alarms"] += 1
                alarm_count += 1

            item["ok"] = True
            ok_switch_ids.append(switch.id)
            ok += 1
        except Exception as exc:
            failed += 1
            item["error"] = str(exc)
        results.append(item)

    _save_crc_state(state)

    stale_q = Q(fingerprint__startswith=CRC_PREFIX, switch_id__in=ok_switch_ids)
    stale = AlarmNotification.objects.filter(stale_q).exclude(fingerprint__in=active_fingerprints).exclude(status=AlarmNotification.Status.RESOLVED)
    stale_fps = list(stale.values_list("fingerprint", flat=True))
    stale_resolved = stale.update(status=AlarmNotification.Status.RESOLVED, resolved_at=now)
    if stale_fps:
        AlarmPolicyState.objects.filter(fingerprint__in=stale_fps).update(
            state=AlarmPolicyState.State.RESOLVED,
            last_resolved_at=now,
            updated_at=now,
        )

    return {"ok": ok, "failed": failed, "alarms": alarm_count, "stale_resolved": int(stale_resolved or 0), "results": results}


class Command(BaseCommand):
    help = "Permanent background SFP and Cisco CRC monitor using Windows DPAPI protected SSH credential."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--switch", default="")
        parser.add_argument("--no-crc", action="store_true")
        parser.add_argument("--no-sfp", action="store_true")
        parser.add_argument("--no-errdisabled", action="store_true")

    def handle(self, *args, **options):
        quiet = bool(options.get("quiet"))
        switch_name = str(options.get("switch") or "").strip()
        started = timezone.now()
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            credential = load_ssh_monitor_credentials(profile="cisco")
        except SecureCredentialError as exc:
            status = {
                "phase_marker": "Phase 72 SFP/CRC Background Monitor",
                "status": "credential_missing",
                "started_at": started.isoformat(),
                "completed_at": timezone.now().isoformat(),
                "error": str(exc),
                "summary": "credential_missing",
            }
            STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            if not quiet:
                self.stdout.write("PHASE72_SFP_CRC_BACKGROUND credential_missing")
            return status["summary"]

        switches = _eligible_switches(switch_name)
        sfp_results = []
        sfp_ok = 0
        sfp_failed = 0
        sfp_created = 0

        if not options.get("no_sfp"):
            for switch in switches:
                item = {"switch": switch.name, "ip": str(switch.management_ip), "ok": False, "created": 0, "error": ""}
                try:
                    if _is_nexus_switch(switch):
                        result = _poll_nexus_sfp_monitor(
                            switch=switch,
                            username=credential["username"],
                            password=credential["password"],
                            enable_password=credential.get("enable_password", ""),
                        )
                    else:
                        result = _poll_sfp_monitor(
                            switch=switch,
                            username=credential["username"],
                            password=credential["password"],
                            enable_password=credential.get("enable_password", ""),
                        )
                    item["ok"] = True
                    item["created"] = int(result.get("created", 0))
                    sfp_created += item["created"]
                    sfp_ok += 1
                except SshActionError as exc:
                    sfp_failed += 1
                    item["error"] = str(exc)
                except Exception as exc:
                    sfp_failed += 1
                    item["error"] = str(exc)
                sfp_results.append(item)

        crc_result = {"ok": 0, "failed": 0, "alarms": 0, "results": []}
        if not options.get("no_crc"):
            crc_result = _run_cisco_crc_monitor(
                switches=switches,
                username=credential["username"],
                password=credential["password"],
                enable_password=credential.get("enable_password", ""),
            )

        errdisabled_result = {"ok": 0, "failed": 0, "interfaces": 0, "errdisabled": 0, "alarms_emitted": 0, "stale_resolved": 0, "results": []}
        if not options.get("no_errdisabled"):
            errdisabled_result = _run_cisco_errdisabled_monitor(
                switches=switches,
                username=credential["username"],
                password=credential["password"],
                enable_password=credential.get("enable_password", ""),
            )

        alarm_status = {"active": 0}
        sfp_alarm_reactivated = 0
        try:
            alarm_status = _sync_alarm_notifications()
            sfp_alarm_reactivated = _reactivate_current_sfp_alarms()
            alarm_status["sfp_reactivated"] = sfp_alarm_reactivated
        except Exception as exc:
            alarm_status = {"error": str(exc)}

        completed = timezone.now()
        status_value = "ok"
        if sfp_failed or crc_result.get("failed") or errdisabled_result.get("failed"):
            status_value = "warning"
        if not switches:
            status_value = "no_switches"

        status = {
            "phase_marker": "Phase 72 SFP/CRC Background Monitor",
            "status": status_value,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "switches": len(switches),
            "sfp_ok": sfp_ok,
            "sfp_failed": sfp_failed,
            "sfp_snapshots_created": sfp_created,
            "crc_ok": crc_result.get("ok", 0),
            "crc_failed": crc_result.get("failed", 0),
            "crc_alarms": crc_result.get("alarms", 0),
            "crc_stale_resolved": crc_result.get("stale_resolved", 0),
            "errdisabled_ok": errdisabled_result.get("ok", 0),
            "errdisabled_failed": errdisabled_result.get("failed", 0),
            "errdisabled_interfaces": errdisabled_result.get("interfaces", 0),
            "errdisabled_ports": errdisabled_result.get("errdisabled", 0),
            "errdisabled_alarms_emitted": errdisabled_result.get("alarms_emitted", 0),
            "errdisabled_stale_resolved": errdisabled_result.get("stale_resolved", 0),
            "alarm_status": alarm_status,
            "sfp_results": sfp_results[:50],
            "crc_results": crc_result.get("results", [])[:50],
            "errdisabled_results": errdisabled_result.get("results", [])[:50],
            "summary": (
                f"switches={len(switches)} sfp_ok={sfp_ok} sfp_failed={sfp_failed} "
                f"sfp_snapshots={sfp_created} crc_ok={crc_result.get('ok', 0)} "
                f"crc_failed={crc_result.get('failed', 0)} crc_alarms={crc_result.get('alarms', 0)} "
                f"crc_stale_resolved={crc_result.get('stale_resolved', 0)} "
                f"errdisabled_ok={errdisabled_result.get('ok', 0)} "
                f"errdisabled_failed={errdisabled_result.get('failed', 0)} "
                f"errdisabled_ports={errdisabled_result.get('errdisabled', 0)} "
                f"errdisabled_alarms_emitted={errdisabled_result.get('alarms_emitted', 0)} "
                f"alarms={alarm_status.get('active', 0)}"
            ),
        }
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        if not quiet:
            self.stdout.write("PHASE72_SFP_CRC_BACKGROUND " + status["summary"])
        return status["summary"]
