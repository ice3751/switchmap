from __future__ import annotations

# PHASE83R_ALARM_ENGINE_V2

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from django.db.models import Q
from django.utils import timezone

from .models import (
    AlarmEvidence,
    AlarmNotification,
    AlarmPolicyState,
    AlarmSilence,
    Port,
    SfpMonitorSnapshot,
    Switch,
)
from .alarm_policy import (
    alarm_is_false_positive,
    cisco_crc_alarm_is_actionable,
    is_actionable_interface_down,
    is_actionable_port_error,
    sfp_issue_labels_from_values,
)


@dataclass(frozen=True)
class AlarmEngineRule:
    key: str
    source: str
    category: str
    severity: str
    consecutive_failures: int = 1
    suppress_if_parent_down: bool = True
    threshold: str = ""
    recovery_condition: str = ""
    description: str = ""


RULES: Dict[str, AlarmEngineRule] = {
    "snmp_timeout": AlarmEngineRule(
        key="snmp_timeout",
        source="SNMP",
        category=AlarmNotification.Category.SNMP,
        severity=AlarmNotification.Severity.CRITICAL,
        consecutive_failures=3,
        suppress_if_parent_down=False,
        threshold="snmp_last_error for 3 distinct observations",
        recovery_condition="next successful SNMP poll clears snmp_last_error",
        description="Device-level parent alarm; child alarms are inhibited while active.",
    ),
    "topology_discovery_error": AlarmEngineRule(
        key="topology_discovery_error",
        source="Discovery",
        category=AlarmNotification.Category.TOPOLOGY,
        severity=AlarmNotification.Severity.WARNING,
        consecutive_failures=2,
        threshold="discovery_last_error for 2 distinct observations",
        recovery_condition="successful discovery clears discovery_last_error",
        description="Discovery warning only; one missed poll is ignored.",
    ),
    "interface_error": AlarmEngineRule(
        key="interface_error",
        source="Port Status",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.CRITICAL,
        consecutive_failures=2,
        threshold="port status error for 2 distinct observations",
        recovery_condition="port.status is no longer error",
        description="Hard interface error only; normal down/notconnect is ignored.",
    ),
    "important_interface_down": AlarmEngineRule(
        key="important_interface_down",
        source="Topology",
        category=AlarmNotification.Category.TOPOLOGY,
        severity=AlarmNotification.Severity.CRITICAL,
        consecutive_failures=2,
        threshold="strict monitored target down for 2 distinct observations",
        recovery_condition="port up or no longer strict-monitored",
        description="Down alarm requires explicit monitored evidence; labels/history alone are ignored.",
    ),
    "sfp_err_disabled": AlarmEngineRule(
        key="sfp_err_disabled",
        source="SFP Monitor",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.CRITICAL,
        consecutive_failures=1,
        threshold="err-disabled in latest SFP poll",
        recovery_condition="latest poll no longer reports err-disabled",
        description="Err-disabled is a deterministic interface state.",
    ),
    "cisco_errdisabled": AlarmEngineRule(
        key="cisco_errdisabled",
        source="Cisco Interface Status",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.CRITICAL,
        consecutive_failures=1,
        threshold="fresh Cisco interface status reports err-disabled on any physical port",
        recovery_condition="fresh Cisco interface status no longer reports err-disabled",
        description="Err-disabled is deterministic and is monitored for all Cisco physical ports, not only SFP ports.",
    ),
    "sfp_counter_delta": AlarmEngineRule(
        key="sfp_counter_delta",
        source="SFP Monitor",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.WARNING,
        consecutive_failures=2,
        threshold="physical error delta >= 10 on an up link for 2 distinct SFP polls",
        recovery_condition="next SFP poll has no related physical delta",
        description="Counter alarms use delta/rate and ignore down/module-only/discard-only samples.",
    ),
    "sfp_optical_threshold": AlarmEngineRule(
        key="sfp_optical_threshold",
        source="SFP Monitor",
        category=AlarmNotification.Category.SFP,
        severity=AlarmNotification.Severity.WARNING,
        consecutive_failures=2,
        threshold="optical threshold only when link is up and real module threshold exists",
        recovery_condition="latest SFP poll returns within threshold or value unavailable",
        description="Module-only optical values are not operational alarms.",
    ),
    "cisco_crc_delta": AlarmEngineRule(
        key="cisco_crc_delta",
        source="Cisco CRC Monitor",
        category=AlarmNotification.Category.INTERFACE,
        severity=AlarmNotification.Severity.WARNING,
        consecutive_failures=2,
        threshold="physical CRC/Input/Output delta >= 10 on a fresh up SFP/fiber port with previous baseline; critical delta emits immediately",
        recovery_condition="next successful CRC monitor run has no related physical delta",
        description="First baseline, down ports, copper access ports and outDiscard-only samples are ignored.",
    ),
}

MANAGED_PREFIXES = (
    "snmp-down:",
    "discovery-error:",
    "port-error:",
    "uplink-down:",
    "sfp:",
    "cisco-crc:",
    "cisco-errdisabled:",
)

# CRC and Cisco err-disabled alarms are event/rate driven by the background monitor.
# They must not be stale-resolved by a UI/Topology sync that has no fresh Cisco poll.
# The background monitor resolves them only for switches that were successfully polled.
# CRC alarms are event/rate driven by the background monitor. They must not be
# stale-resolved by a UI/Topology sync that has no fresh CRC poll. They are still
# passed through false-positive validation below.
STALE_RESOLVE_PREFIXES = (
    "snmp-down:",
    "discovery-error:",
    "port-error:",
    "uplink-down:",
    "sfp:",
)


@dataclass
class AlarmEvidenceCandidate:
    rule_key: str
    fingerprint: str
    source: str
    category: str
    severity: str
    title: str
    message: str
    switch: Any = None
    port: Any = None
    details: str = ""
    observed_at: Any = None
    evidence_key: str = ""
    evidence_type: str = ""
    threshold: str = ""
    raw_value: str = ""
    previous_value: str = ""
    delta_value: str = ""
    admin_status: str = ""
    oper_status: str = ""
    link_status: str = ""
    topology_confidence: str = ""
    condition_active: bool = True
    force_immediate: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def _switch_id(obj: Any) -> Optional[int]:
    return getattr(obj, "id", None) or getattr(obj, "switch_id", None)


def _port_id(obj: Any) -> Optional[int]:
    return getattr(obj, "id", None) or getattr(obj, "port_id", None)


def _now_or(value: Any):
    return value or timezone.now()


def _as_key(*parts: Any) -> str:
    return "|".join(str(part or "") for part in parts)[:255]


def _slug(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "item"


def _is_silenced(candidate: AlarmEvidenceCandidate) -> bool:
    now = timezone.now()
    qs = AlarmSilence.objects.filter(active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if candidate.fingerprint and qs.filter(fingerprint=candidate.fingerprint).exists():
        return True
    switch_id = _switch_id(candidate.switch)
    port_id = _port_id(candidate.port)
    scoped = qs.filter(Q(rule_key="") | Q(rule_key=candidate.rule_key))
    if port_id and scoped.filter(port_id=port_id).exists():
        return True
    if switch_id and scoped.filter(port_id__isnull=True, switch_id=switch_id).exists():
        return True
    return False


def _record_evidence(candidate: AlarmEvidenceCandidate, decision: str, reason: str) -> None:
    try:
        AlarmEvidence.objects.create(
            fingerprint=candidate.fingerprint,
            rule_key=candidate.rule_key,
            source=candidate.source,
            switch=candidate.switch,
            port=candidate.port,
            evidence_type=candidate.evidence_type or candidate.rule_key,
            observed_at=candidate.observed_at,
            evidence_key=candidate.evidence_key,
            raw_value=str(candidate.raw_value or "")[:4000],
            previous_value=str(candidate.previous_value or "")[:4000],
            delta_value=str(candidate.delta_value or "")[:4000],
            threshold=candidate.threshold or RULES.get(candidate.rule_key, AlarmEngineRule(candidate.rule_key, "", "", "")).threshold,
            admin_status=str(candidate.admin_status or getattr(candidate.port, "snmp_admin_status", "") or "")[:80],
            oper_status=str(candidate.oper_status or getattr(candidate.port, "snmp_oper_status", "") or "")[:80],
            link_status=str(candidate.link_status or getattr(candidate.port, "status", "") or "")[:80],
            topology_confidence=str(candidate.topology_confidence or "")[:40],
            decision=decision,
            reason=str(reason or "")[:255],
            details=candidate.details or candidate.message,
        )
    except Exception:
        # Evidence logging must never break monitoring.
        return


def _can_reopen_resolved(alarm: AlarmNotification, candidate: AlarmEvidenceCandidate, state: AlarmPolicyState) -> bool:
    if alarm.status != AlarmNotification.Status.RESOLVED:
        return True
    resolved_at = alarm.resolved_at
    observed_at = candidate.observed_at
    if resolved_at and observed_at:
        try:
            if observed_at <= resolved_at:
                return False
        except Exception:
            return False
    if candidate.evidence_key and state.last_evidence_key == candidate.evidence_key:
        return False
    return True


def _upsert_alarm(candidate: AlarmEvidenceCandidate, state: AlarmPolicyState, count_occurrence: bool) -> bool:
    now = _now_or(candidate.observed_at)
    alarm, created = AlarmNotification.objects.get_or_create(
        fingerprint=candidate.fingerprint,
        defaults={
            "source": candidate.source,
            "category": candidate.category,
            "severity": candidate.severity,
            "status": AlarmNotification.Status.ACTIVE,
            "title": candidate.title,
            "message": candidate.message,
            "details": candidate.details,
            "switch": candidate.switch,
            "port": candidate.port,
            "occurrences": 1,
            "last_seen": now,
        },
    )
    if created:
        return True

    if not _can_reopen_resolved(alarm, candidate, state):
        return False

    alarm.source = candidate.source
    alarm.category = candidate.category
    alarm.severity = candidate.severity
    alarm.title = candidate.title
    alarm.message = candidate.message
    alarm.details = candidate.details
    alarm.switch = candidate.switch
    alarm.port = candidate.port
    update_fields = ["source", "category", "severity", "title", "message", "details", "switch", "port"]

    if alarm.status == AlarmNotification.Status.RESOLVED:
        alarm.status = AlarmNotification.Status.ACTIVE
        alarm.resolved_at = None
        update_fields.extend(["status", "resolved_at"])
        count_occurrence = True

    if count_occurrence:
        alarm.last_seen = now
        alarm.occurrences = int(alarm.occurrences or 0) + 1
        update_fields.extend(["last_seen", "occurrences"])

    alarm.save(update_fields=update_fields)
    return True


def process_alarm_candidates(candidates: Iterable[AlarmEvidenceCandidate], parent_down_switch_ids: Optional[Iterable[int]] = None, resolve_stale: bool = True) -> Dict[str, Any]:
    parent_down_switch_ids: Set[int] = {int(x) for x in (parent_down_switch_ids or []) if x}
    candidates = [c for c in candidates if c and c.fingerprint and c.rule_key in RULES]
    active_fingerprints: Set[str] = set()
    emitted = pending = suppressed = silenced = ignored = reopened_blocked = 0

    for candidate in candidates:
        rule = RULES[candidate.rule_key]
        state, _created = AlarmPolicyState.objects.get_or_create(
            fingerprint=candidate.fingerprint,
            defaults={"rule_key": candidate.rule_key, "state": AlarmPolicyState.State.PENDING},
        )
        state.rule_key = candidate.rule_key
        state.last_observed_at = candidate.observed_at or timezone.now()
        state.metadata = {**(state.metadata or {}), **(candidate.metadata or {})}

        if _is_silenced(candidate):
            state.state = AlarmPolicyState.State.SILENCED
            state.suppressed_reason = "silenced"
            state.current_failures = 0
            state.save(update_fields=["rule_key", "state", "suppressed_reason", "current_failures", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.IGNORED, "silenced")
            silenced += 1
            continue

        if rule.suppress_if_parent_down and _switch_id(candidate.switch) in parent_down_switch_ids:
            state.state = AlarmPolicyState.State.SUPPRESSED
            state.suppressed_reason = "parent_snmp_timeout"
            state.current_failures = 0
            state.save(update_fields=["rule_key", "state", "suppressed_reason", "current_failures", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.SUPPRESSED, "parent_snmp_timeout")
            suppressed += 1
            continue

        if not candidate.condition_active:
            state.state = AlarmPolicyState.State.RESOLVED
            state.current_failures = 0
            state.last_resolved_at = timezone.now()
            state.suppressed_reason = ""
            state.save(update_fields=["rule_key", "state", "current_failures", "last_resolved_at", "suppressed_reason", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.RESOLVED, "condition_inactive")
            ignored += 1
            continue

        new_observation = bool(candidate.evidence_key and candidate.evidence_key != state.last_evidence_key)
        if new_observation or not state.last_evidence_key:
            state.current_failures = int(state.current_failures or 0) + 1
            state.last_evidence_key = candidate.evidence_key

        existing_alarm = AlarmNotification.objects.filter(fingerprint=candidate.fingerprint).only("status").first()
        already_active = bool(existing_alarm and existing_alarm.status in {AlarmNotification.Status.ACTIVE, AlarmNotification.Status.ACKNOWLEDGED})
        should_emit = (
            candidate.force_immediate
            or state.state == AlarmPolicyState.State.ACTIVE
            or already_active
            or state.current_failures >= max(1, int(rule.consecutive_failures))
        )
        if not should_emit:
            state.state = AlarmPolicyState.State.PENDING
            state.suppressed_reason = ""
            state.save(update_fields=["rule_key", "state", "last_evidence_key", "current_failures", "suppressed_reason", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.PENDING, "waiting_for_consecutive_evidence")
            pending += 1
            continue

        count_occurrence = bool(new_observation or state.state != AlarmPolicyState.State.ACTIVE or candidate.force_immediate)
        if _upsert_alarm(candidate, state, count_occurrence=count_occurrence):
            state.state = AlarmPolicyState.State.ACTIVE
            state.last_emitted_at = candidate.observed_at or timezone.now()
            state.occurrence_count_v2 = int(state.occurrence_count_v2 or 0) + (1 if count_occurrence else 0)
            state.suppressed_reason = ""
            state.save(update_fields=["rule_key", "state", "last_evidence_key", "current_failures", "occurrence_count_v2", "last_emitted_at", "suppressed_reason", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.EMIT, "active")
            active_fingerprints.add(candidate.fingerprint)
            emitted += 1
        else:
            state.state = AlarmPolicyState.State.RESOLVED
            state.save(update_fields=["rule_key", "state", "last_evidence_key", "current_failures", "last_observed_at", "metadata", "updated_at"])
            _record_evidence(candidate, AlarmEvidence.Decision.IGNORED, "manual_resolve_blocks_same_evidence")
            reopened_blocked += 1

    stale_resolved = 0
    false_positive_resolved = 0
    if resolve_stale:
        stale_q = Q()
        for prefix in STALE_RESOLVE_PREFIXES:
            stale_q |= Q(fingerprint__startswith=prefix)
        stale = AlarmNotification.objects.filter(stale_q).exclude(fingerprint__in=active_fingerprints).exclude(status=AlarmNotification.Status.RESOLVED)
        now = timezone.now()
        stale_fps = list(stale.values_list("fingerprint", flat=True))
        stale_resolved = stale.update(status=AlarmNotification.Status.RESOLVED, resolved_at=now)
        for state in AlarmPolicyState.objects.filter(fingerprint__in=stale_fps):
            state.state = AlarmPolicyState.State.RESOLVED
            state.last_resolved_at = now
            state.save(update_fields=["state", "last_resolved_at", "updated_at"])

        for alarm in AlarmNotification.objects.select_related("switch", "port").exclude(status=AlarmNotification.Status.RESOLVED):
            alarm_fp = str(alarm.fingerprint or "")
            if not any(alarm_fp.startswith(prefix) for prefix in MANAGED_PREFIXES):
                continue
            # Cisco CRC and Cisco err-disabled alarms are owned by the fresh SSH poll.
            # Generic sync must not resolve them using stale DB/SNMP/UI state.
            if alarm_fp.startswith(("cisco-crc:", "cisco-errdisabled:")):
                continue
            is_fp, reason = alarm_is_false_positive(alarm)
            if is_fp:
                alarm.status = AlarmNotification.Status.RESOLVED
                alarm.resolved_at = now
                alarm.details = ((alarm.details or "") + f"\nPhase83R auto-resolved: {reason}").strip()
                alarm.save(update_fields=["status", "resolved_at", "details"])
                state, _ = AlarmPolicyState.objects.get_or_create(fingerprint=alarm.fingerprint, defaults={"rule_key": "legacy"})
                state.state = AlarmPolicyState.State.RESOLVED
                state.last_resolved_at = now
                state.suppressed_reason = reason
                state.save(update_fields=["state", "last_resolved_at", "suppressed_reason", "updated_at"])
                _record_evidence(
                    AlarmEvidenceCandidate(
                        rule_key=state.rule_key if state.rule_key in RULES else "interface_error",
                        fingerprint=alarm.fingerprint,
                        source=alarm.source,
                        category=alarm.category,
                        severity=alarm.severity,
                        title=alarm.title,
                        message=alarm.message,
                        switch=alarm.switch,
                        port=alarm.port,
                        details=alarm.details,
                        observed_at=now,
                        evidence_key=f"legacy-cleanup|{now.isoformat()}|{reason}",
                    ),
                    AlarmEvidence.Decision.RESOLVED,
                    reason,
                )
                false_positive_resolved += 1

    return {
        "candidates": len(candidates),
        "emitted": emitted,
        "pending": pending,
        "suppressed": suppressed,
        "silenced": silenced,
        "ignored": ignored,
        "reopened_blocked": reopened_blocked,
        "stale_resolved": stale_resolved,
        "false_positive_resolved": false_positive_resolved,
        "active": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count(),
        "critical": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count(),
        "warning": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count(),
    }


def latest_sfp_snapshots() -> List[SfpMonitorSnapshot]:
    latest: Dict[tuple, SfpMonitorSnapshot] = {}
    for item in SfpMonitorSnapshot.objects.select_related("switch", "port").order_by("switch_id", "interface_name", "-poll_time", "-id"):
        key = (item.switch_id, item.interface_name)
        if key not in latest:
            latest[key] = item
    return list(latest.values())


def _sfp_rule_key(tag: str) -> str:
    if tag == "Err-disabled":
        return "sfp_err_disabled"
    if tag in {"Rx Power abnormal", "Tx Power abnormal", "Temperature abnormal"}:
        return "sfp_optical_threshold"
    return "sfp_counter_delta"


def _sfp_severity(item: SfpMonitorSnapshot, tag: str) -> str:
    if tag == "Err-disabled" or getattr(item, "err_disabled", False):
        return AlarmNotification.Severity.CRITICAL
    return AlarmNotification.Severity.WARNING


def _sfp_details(item: SfpMonitorSnapshot) -> str:
    return (
        f"link={item.link_status or '-'}, CRCΔ={item.fcs_delta}, alignΔ={item.align_delta}, "
        f"InputΔ={item.input_error_delta}, OutputΔ={item.output_error_delta}, "
        f"rcvΔ={item.rcv_delta}, xmitΔ={item.xmit_delta}, outDiscardΔ={item.out_discard_delta}, "
        f"Rx={item.rx_power_dbm or '-'}, Tx={item.tx_power_dbm or '-'}, Temp={item.temperature_c or '-'}"
    )


def build_current_alarm_candidates() -> List[AlarmEvidenceCandidate]:
    candidates: List[AlarmEvidenceCandidate] = []
    switches = list(Switch.objects.filter(is_active=True).prefetch_related("ports"))
    for switch in switches:
        snmp_error = str(switch.snmp_last_error or "").strip()
        if switch.snmp_enabled and snmp_error:
            candidates.append(AlarmEvidenceCandidate(
                rule_key="snmp_timeout",
                fingerprint=f"snmp-down:{switch.id}",
                source="SNMP",
                category=AlarmNotification.Category.SNMP,
                severity=AlarmNotification.Severity.CRITICAL,
                title="SNMP Down",
                message=f"{switch.name}: {snmp_error}",
                switch=switch,
                details=snmp_error,
                observed_at=switch.snmp_last_poll,
                evidence_key=_as_key("snmp", switch.snmp_last_poll, snmp_error),
                evidence_type="snmp_timeout",
                raw_value=snmp_error,
            ))

        discovery_error = str(switch.discovery_last_error or "").strip()
        if discovery_error:
            candidates.append(AlarmEvidenceCandidate(
                rule_key="topology_discovery_error",
                fingerprint=f"discovery-error:{switch.id}",
                source="Discovery",
                category=AlarmNotification.Category.TOPOLOGY,
                severity=AlarmNotification.Severity.WARNING,
                title="Discovery Error",
                message=f"{switch.name}: {discovery_error}",
                switch=switch,
                details=discovery_error,
                observed_at=switch.discovery_last_poll,
                evidence_key=_as_key("discovery", switch.discovery_last_poll, discovery_error),
                evidence_type="discovery_error",
                raw_value=discovery_error,
            ))

        for port in switch.ports.all():
            observed_at = getattr(port, "snmp_last_poll", None) or getattr(port, "discovery_last_poll", None)
            base_key = _as_key(observed_at, port.status, port.snmp_admin_status, port.snmp_oper_status, port.neighbor_device, port.connected_device)
            if port.status == Port.Status.ERROR and is_actionable_port_error(port):
                candidates.append(AlarmEvidenceCandidate(
                    rule_key="interface_error",
                    fingerprint=f"port-error:{switch.id}:{port.id}",
                    source="Port Status",
                    category=AlarmNotification.Category.INTERFACE,
                    severity=AlarmNotification.Severity.CRITICAL,
                    title="Port Error",
                    message=f"{switch.name} {port.interface_name} status is Error",
                    switch=switch,
                    port=port,
                    details=port.description or port.snmp_alias or "",
                    observed_at=observed_at,
                    evidence_key=_as_key("port-error", base_key),
                    evidence_type="explicit_fault_interface_error",
                    admin_status=port.snmp_admin_status,
                    oper_status=port.snmp_oper_status,
                    link_status=port.status,
                ))
            if is_actionable_interface_down(port):
                candidates.append(AlarmEvidenceCandidate(
                    rule_key="important_interface_down",
                    fingerprint=f"uplink-down:{switch.id}:{port.id}",
                    source="Topology",
                    category=AlarmNotification.Category.TOPOLOGY,
                    severity=AlarmNotification.Severity.CRITICAL,
                    title="Uplink / Neighbor Down",
                    message=f"{switch.name} {port.interface_name} is Down",
                    switch=switch,
                    port=port,
                    details=f"neighbor={port.neighbor_device or '-'}; connected={port.connected_device or '-'}; doc={port.documentation_status}; policy=strict_monitored_target",
                    observed_at=observed_at,
                    evidence_key=_as_key("down", base_key),
                    evidence_type="strict_monitored_interface_down",
                    admin_status=port.snmp_admin_status,
                    oper_status=port.snmp_oper_status,
                    link_status=port.status,
                    topology_confidence="confirmed",
                ))

    for item in latest_sfp_snapshots():
        values = {
            "link_status": item.link_status,
            "err_disabled": item.err_disabled,
            "align_delta": item.align_delta,
            "fcs_delta": item.fcs_delta,
            "input_error_delta": item.input_error_delta,
            "output_error_delta": item.output_error_delta,
            "rcv_delta": item.rcv_delta,
            "xmit_delta": item.xmit_delta,
            "temperature_c": item.temperature_c,
            "rx_power_dbm": item.rx_power_dbm,
            "tx_power_dbm": item.tx_power_dbm,
        }
        for tag in sfp_issue_labels_from_values(values):
            candidates.append(AlarmEvidenceCandidate(
                rule_key=_sfp_rule_key(tag),
                fingerprint=f"sfp:{item.switch_id}:{_slug(item.interface_name)}:{_slug(tag)}",
                source="SFP Monitor",
                category=AlarmNotification.Category.SFP,
                severity=_sfp_severity(item, tag),
                title=tag,
                message=f"{item.switch.name} {item.interface_name}: {tag}",
                switch=item.switch,
                port=item.port,
                details=_sfp_details(item),
                observed_at=item.poll_time,
                evidence_key=_as_key("sfp", item.poll_time, item.link_status, item.err_disabled, item.fcs_delta, item.input_error_delta, item.output_error_delta, item.rx_power_dbm, item.tx_power_dbm, item.temperature_c, tag),
                evidence_type="sfp_snapshot",
                link_status=item.link_status,
                raw_value=_sfp_details(item),
            ))
    return candidates


def sync_alarm_notifications_v2() -> Dict[str, Any]:
    parent_down_switch_ids = set(
        Switch.objects.filter(is_active=True, snmp_enabled=True)
        .exclude(snmp_last_error="")
        .values_list("id", flat=True)
    )
    return process_alarm_candidates(build_current_alarm_candidates(), parent_down_switch_ids=parent_down_switch_ids, resolve_stale=True)


def make_crc_candidate(*, switch: Switch, port: Optional[Port], iface: str, severity: str, details: str, deltas: Dict[str, Any], observed_at=None) -> Optional[AlarmEvidenceCandidate]:
    actionable, reason = cisco_crc_alarm_is_actionable(port, deltas)
    if not actionable:
        return None
    return AlarmEvidenceCandidate(
        rule_key="cisco_crc_delta",
        fingerprint=f"cisco-crc:{switch.id}:{_slug(iface)}",
        source="Cisco CRC Monitor",
        category=AlarmNotification.Category.INTERFACE,
        severity=severity,
        title="Cisco CRC/Input/Output Error Increased",
        message=f"{switch.name} {iface}: {details}",
        switch=switch,
        port=port,
        details=details,
        observed_at=observed_at or timezone.now(),
        evidence_key=_as_key("crc", observed_at or timezone.now(), switch.id, iface, details),
        evidence_type="crc_counter_delta",
        raw_value=details,
        delta_value=str(deltas),
        threshold=RULES["cisco_crc_delta"].threshold,
        admin_status=getattr(port, "snmp_admin_status", "") if port else "",
        oper_status=getattr(port, "snmp_oper_status", "") if port else "",
        link_status=getattr(port, "status", "") if port else "",
    )


def alarm_engine_summary() -> Dict[str, Any]:
    return {
        "rules": len(RULES),
        "policy_states": AlarmPolicyState.objects.count(),
        "evidence": AlarmEvidence.objects.count(),
        "active": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE).count(),
        "critical": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.CRITICAL).count(),
        "warning": AlarmNotification.objects.filter(status=AlarmNotification.Status.ACTIVE, severity=AlarmNotification.Severity.WARNING).count(),
        "resolved": AlarmNotification.objects.filter(status=AlarmNotification.Status.RESOLVED).count(),
    }
