from __future__ import annotations

# PHASE80_ALARM_RULE_ENGINE

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
from typing import Any, Dict, Iterable, List, Optional, Set

from django.conf import settings
from django.utils import timezone

from .models import AlarmNotification, SfpMonitorSnapshot


PHASE80_RULE_ENGINE_MARKER = "PHASE80_ALARM_RULE_ENGINE"
RULE_STATE_FILENAME = "phase80-alarm-rule-state.json"


@dataclass(frozen=True)
class AlarmRule:
    key: str
    source: str
    device_type: str
    category: str
    severity: str
    threshold: str
    consecutive_failures: int
    recovery_condition: str
    dedup_key: str
    suppress_if_parent_down: bool
    cooldown_seconds: int
    description: str = ""


@dataclass
class AlarmCandidate:
    rule_key: str
    fingerprint: str
    source: str
    category: str
    severity: str
    title: str
    message: str
    details: str = ""
    switch: Any = None
    port: Any = None
    observed_at: Any = None
    observed_key: str = ""
    condition_active: bool = True
    force_immediate: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def switch_id(self):
        return getattr(self.switch, "id", None)


@dataclass
class AlarmDecision:
    candidate: AlarmCandidate
    rule: AlarmRule
    count_occurrence: bool
    current_failures: int
    reason: str = ""


RULES: Dict[str, AlarmRule] = {
    "snmp_timeout": AlarmRule(
        key="snmp_timeout",
        source="SNMP",
        device_type="switch/router",
        category=AlarmNotification.Category.SNMP,
        severity=AlarmNotification.Severity.CRITICAL,
        threshold="snmp_last_error present for 3 distinct polls",
        consecutive_failures=3,
        recovery_condition="next successful SNMP poll clears snmp_last_error",
        dedup_key="snmp-down:{device_id}",
        suppress_if_parent_down=False,
        cooldown_seconds=900,
        description="Device-level SNMP timeout; child alarms are suppressed while this condition exists.",
    ),
    "topology_discovery_error": AlarmRule(
        key="topology_discovery_error",
        source="Discovery",
        device_type="switch/router",
        category=AlarmNotification.Category.TOPOLOGY,
        severity=AlarmNotification.Severity.WARNING,
        threshold="discovery_last_error present for 2 distinct discovery polls",
        consecutive_failures=2,
        recovery_condition="successful discovery clears discovery_last_error",
        dedup_key="discovery-error:{device_id}",
        suppress_if_parent_down=True,
        cooldown_seconds=1800,
        description="Discovery warnings must not be created from a single missed poll.",
    ),
    "interface_error": AlarmRule(
        key="interface_error",
        source="Port Status",
        device_type="network-interface",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.CRITICAL,
        threshold="port.status=error for 2 distinct SNMP/discovery observations",
        consecutive_failures=2,
        recovery_condition="port.status is no longer error",
        dedup_key="port-error:{device_id}:{port_id}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Hard interface errors only; normal access-port down is ignored.",
    ),
    "important_interface_down": AlarmRule(
        key="important_interface_down",
        source="Topology",
        device_type="uplink/trunk/documented-port",
        category=AlarmNotification.Category.TOPOLOGY,
        severity=AlarmNotification.Severity.CRITICAL,
        threshold="actionable down only: confirmed neighbor, identity evidence, or explicit critical text for 2 distinct observations",
        consecutive_failures=2,
        recovery_condition="port returns up or no longer has actionable critical evidence",
        dedup_key="uplink-down:{device_id}:{port_id}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Interface name, trunk mode, or module-only uplink labels are not enough to create alarms.",
    ),
    "sfp_err_disabled": AlarmRule(
        key="sfp_err_disabled",
        source="SFP Monitor",
        device_type="sfp/transceiver",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.CRITICAL,
        threshold="err-disabled in latest SFP poll",
        consecutive_failures=1,
        recovery_condition="latest SFP poll no longer reports err-disabled",
        dedup_key="sfp:{device_id}:{interface}:{issue}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Err-disabled is accepted immediately because it is a deterministic interface state.",
    ),
    "cisco_errdisabled": AlarmRule(
        key="cisco_errdisabled",
        source="Cisco Interface Status",
        device_type="cisco-interface",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.CRITICAL,
        threshold="fresh Cisco interface status reports err-disabled on any physical port",
        consecutive_failures=1,
        recovery_condition="fresh Cisco interface status no longer reports err-disabled",
        dedup_key="cisco-errdisabled:{device_id}:{interface}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Err-disabled is accepted immediately because it is a deterministic Cisco interface state.",
    ),
    "sfp_counter_delta": AlarmRule(
        key="sfp_counter_delta",
        source="SFP Monitor",
        device_type="sfp/transceiver",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.WARNING,
        threshold="CRC/Input/Output physical error delta >= 10 on an up link for 2 distinct SFP polls; discard-only is ignored",
        consecutive_failures=2,
        recovery_condition="next SFP poll has no related counter delta",
        dedup_key="sfp:{device_id}:{interface}:{issue}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Counter alarms require link-up and physical error delta; discard-only and first-baseline deltas are ignored.",
    ),
    "sfp_optical_threshold": AlarmRule(
        key="sfp_optical_threshold",
        source="SFP Monitor",
        device_type="sfp/transceiver",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.WARNING,
        threshold="Rx/Tx outside threshold only when link is up; Temperature only outside broad -40..85 sanity range",
        consecutive_failures=2,
        recovery_condition="latest SFP poll returns within threshold or value is unavailable",
        dedup_key="sfp:{device_id}:{interface}:{issue}",
        suppress_if_parent_down=True,
        cooldown_seconds=1800,
        description="Module-only/disconnected optical values and generic 0..70 temperature false positives are suppressed.",
    ),
    "cisco_crc_delta": AlarmRule(
        key="cisco_crc_delta",
        source="Cisco CRC Monitor",
        device_type="cisco-interface",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.WARNING,
        threshold="CRC/Input/Output physical error delta >= 10 on a fresh up SFP/fiber port; discard-only is ignored; critical delta emits immediately",
        consecutive_failures=2,
        recovery_condition="next successful CRC monitor run has no related delta",
        dedup_key="cisco-crc:{device_id}:{interface}",
        suppress_if_parent_down=True,
        cooldown_seconds=900,
        description="Background CRC monitor must not alert on outDiscards alone, down ports, copper access ports, or first baseline samples.",
    ),
}


def _state_path() -> Path:
    path = Path(settings.BASE_DIR) / "logs" / RULE_STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_state() -> Dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"version": 1, "rules": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "rules": {}}
        data.setdefault("version", 1)
        data.setdefault("rules", {})
        return data
    except Exception:
        return {"version": 1, "rules": {}}


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _observed_key(candidate: AlarmCandidate) -> str:
    if candidate.observed_key:
        return str(candidate.observed_key)
    observed_at = candidate.observed_at
    if observed_at:
        try:
            return observed_at.isoformat()
        except Exception:
            return str(observed_at)
    return ""


def _active_alarm_fingerprints(fingerprints: Iterable[str]) -> Set[str]:
    fps = [fp for fp in fingerprints if fp]
    if not fps:
        return set()
    return set(
        AlarmNotification.objects.filter(
            fingerprint__in=fps,
            status__in=[AlarmNotification.Status.ACTIVE, AlarmNotification.Status.ACKNOWLEDGED],
        ).values_list("fingerprint", flat=True)
    )


def _seconds_since(dt, now) -> Optional[float]:
    if not dt:
        return None
    try:
        return (now - dt).total_seconds()
    except Exception:
        return None


def _candidate_is_parent_suppressed(candidate: AlarmCandidate, rule: AlarmRule, parent_down_switch_ids: Set[int]) -> bool:
    if not rule.suppress_if_parent_down:
        return False
    switch_id = candidate.switch_id
    return bool(switch_id and switch_id in parent_down_switch_ids)


def evaluate_alarm_candidates(candidates: Iterable[AlarmCandidate], parent_down_switch_ids: Optional[Iterable[int]] = None) -> Dict[str, Any]:
    """Evaluate alarm candidates without polling devices.

    The engine counts consecutive failures only when the evidence key changes.
    This prevents Dashboard/Alarm page refreshes from creating fake duplicate occurrences.
    """
    now = timezone.now()
    parent_down_switch_ids = {int(item) for item in (parent_down_switch_ids or []) if item}
    candidates = [item for item in candidates if item and item.fingerprint and item.rule_key in RULES]
    existing_active = _active_alarm_fingerprints(item.fingerprint for item in candidates)
    state = _load_state()
    rule_state = state.setdefault("rules", {})
    decisions: List[AlarmDecision] = []
    suppressed: List[AlarmCandidate] = []
    skipped: List[AlarmCandidate] = []

    for candidate in candidates:
        rule = RULES[candidate.rule_key]
        fp = candidate.fingerprint
        item_state = rule_state.setdefault(fp, {})
        item_state["rule_key"] = rule.key
        item_state["source"] = rule.source
        item_state["dedup_key"] = rule.dedup_key
        item_state["updated_at"] = now.isoformat()

        if _candidate_is_parent_suppressed(candidate, rule, parent_down_switch_ids):
            item_state["suppressed"] = True
            item_state["suppressed_reason"] = "parent_snmp_timeout"
            item_state["current_failures"] = 0
            suppressed.append(candidate)
            continue

        if not candidate.condition_active:
            item_state["current_failures"] = 0
            item_state["last_recovery_at"] = now.isoformat()
            skipped.append(candidate)
            continue

        key = _observed_key(candidate)
        previous_key = item_state.get("last_observed_key", "")
        new_observation = bool(key and key != previous_key)
        if new_observation:
            item_state["last_observed_key"] = key
            item_state["current_failures"] = int(item_state.get("current_failures") or 0) + 1
            item_state["last_failure_at"] = now.isoformat()
            item_state["suppressed"] = False
        elif not key and not item_state.get("last_failure_at"):
            item_state["current_failures"] = int(item_state.get("current_failures") or 0) + 1
            item_state["last_failure_at"] = now.isoformat()

        current_failures = int(item_state.get("current_failures") or 0)
        already_active = fp in existing_active
        should_emit = candidate.force_immediate or already_active or current_failures >= int(rule.consecutive_failures or 1)
        if not should_emit:
            skipped.append(candidate)
            continue

        count_occurrence = bool(new_observation or candidate.force_immediate or not already_active)
        if count_occurrence and already_active:
            last_counted = item_state.get("last_counted_at")
            if last_counted:
                try:
                    parsed = datetime.fromisoformat(str(last_counted))
                    if parsed.tzinfo is None:
                        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                    if _seconds_since(parsed, now) is not None and _seconds_since(parsed, now) < rule.cooldown_seconds and not new_observation:
                        count_occurrence = False
                except Exception:
                    pass
        if count_occurrence:
            item_state["last_counted_at"] = now.isoformat()

        decisions.append(
            AlarmDecision(
                candidate=candidate,
                rule=rule,
                count_occurrence=count_occurrence,
                current_failures=current_failures,
                reason="active_existing" if already_active else "threshold_met",
            )
        )

    _save_state(state)
    return {
        "active": decisions,
        "suppressed": suppressed,
        "skipped": skipped,
        "state_path": str(_state_path()),
    }


def sfp_rule_key_for_tag(tag: str) -> str:
    tag = str(tag or "").strip()
    if tag == "Err-disabled":
        return "sfp_err_disabled"
    if tag in {"Rx Power abnormal", "Tx Power abnormal", "Temperature abnormal"}:
        return "sfp_optical_threshold"
    return "sfp_counter_delta"


def sfp_severity_for_tag(item: SfpMonitorSnapshot, tag: str) -> str:
    if getattr(item, "err_disabled", False) or getattr(item, "health_state", "") == SfpMonitorSnapshot.Health.CRITICAL:
        return AlarmNotification.Severity.CRITICAL
    if tag in {"Err-disabled"}:
        return AlarmNotification.Severity.CRITICAL
    return AlarmNotification.Severity.WARNING


def sfp_alarm_details(item: SfpMonitorSnapshot) -> str:
    return (
        f"CRCΔ={getattr(item, 'fcs_delta', 0)}, "
        f"InputΔ={getattr(item, 'input_error_delta', 0)}, "
        f"OutputΔ={getattr(item, 'output_error_delta', 0)}, "
        f"Rx={getattr(item, 'rx_power_dbm', None) or '-'}, "
        f"Tx={getattr(item, 'tx_power_dbm', None) or '-'}, "
        f"Temp={getattr(item, 'temperature_c', None) or '-'}"
    )


def alarm_rule_report() -> List[Dict[str, Any]]:
    rows = []
    for rule in RULES.values():
        rows.append({
            "key": rule.key,
            "source": rule.source,
            "device_type": rule.device_type,
            "severity": rule.severity,
            "category": rule.category,
            "threshold": rule.threshold,
            "consecutive_failures": rule.consecutive_failures,
            "recovery_condition": rule.recovery_condition,
            "dedup_key": rule.dedup_key,
            "suppress_if_parent_down": rule.suppress_if_parent_down,
            "cooldown_seconds": rule.cooldown_seconds,
            "cooldown_text": f"{int(rule.cooldown_seconds // 60)} min",
            "description": rule.description,
        })
    return rows


def phase80_state_summary() -> Dict[str, Any]:
    # PHASE83R_ALARM_ENGINE_V2_STATE_SUMMARY
    try:
        from .models import AlarmEvidence, AlarmPolicyState
        return {
            "state_path": "database:inventory_alarmpolicystate",
            "tracked_keys": AlarmPolicyState.objects.count(),
            "suppressed": AlarmPolicyState.objects.filter(state=AlarmPolicyState.State.SUPPRESSED).count(),
            "confirmed": AlarmPolicyState.objects.filter(state=AlarmPolicyState.State.ACTIVE).count(),
            "evidence": AlarmEvidence.objects.count(),
        }
    except Exception:
        state = _load_state()
        rules = state.get("rules", {}) if isinstance(state, dict) else {}
        return {
            "state_path": str(_state_path()),
            "tracked_keys": len(rules),
            "suppressed": sum(1 for item in rules.values() if isinstance(item, dict) and item.get("suppressed")),
            "confirmed": sum(1 for item in rules.values() if isinstance(item, dict) and int(item.get("current_failures") or 0) > 0),
        }
