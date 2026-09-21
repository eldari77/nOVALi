from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from operator_shell.observability import record_counter, record_event, trace_span


def _attrs(**kwargs: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        normalized = str(value).strip() if isinstance(value, str) else value
        if normalized == "":
            continue
        attrs_key = {
            "alert_type": "novali.alert.type",
            "severity": "novali.alert.severity",
            "status": "novali.alert.status",
            "source": "novali.alert.source",
            "adapter_kind": "novali.adapter.kind",
            "adapter_mode": "novali.adapter.mode",
            "lane_id": "novali.controller.lane",
            "lane_role": "novali.controller.role",
            "review_status": "novali.review_status",
            "result": "novali.result",
            "proof_kind": "novali.proof_kind",
        }.get(key, key)
        attrs[attrs_key] = normalized
    return attrs


@contextmanager
def operator_alert_span(name: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
    attrs = _attrs(**kwargs)
    with trace_span(name, attrs):
        yield attrs


def emit_alert_raised(*, alert_type: str, severity: str, source: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, source=source, result=result, proof_kind=proof_kind)
    record_counter("novali.operator_alert.count", 1, attrs)
    record_counter("novali.operator_alert.raised.count", 1, attrs)
    if severity == "critical":
        record_counter("novali.operator_alert.critical.count", 1, attrs)
    if result == "blocked_waiting_operator":
        record_counter("novali.operator_alert.blocked.count", 1, attrs)
    record_event("novali.operator_alert.raised", attrs)
    return attrs


def emit_evidence_bundle_created(*, alert_type: str, source: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, source=source, result=result, proof_kind=proof_kind)
    record_counter("novali.operator_alert.evidence_bundle.count", 1, attrs)
    record_event("novali.operator_alert.evidence_bundle.created", attrs)
    return attrs


def emit_alert_acknowledged(*, alert_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, status="acknowledged", result="success", proof_kind=proof_kind)
    record_counter("novali.operator_alert.acknowledged.count", 1, attrs)
    record_event("novali.operator_alert.acknowledged", attrs)
    return attrs


def emit_alert_reviewed(*, alert_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, status="reviewed", result="success", proof_kind=proof_kind)
    record_counter("novali.operator_alert.reviewed.count", 1, attrs)
    record_event("novali.operator_alert.reviewed", attrs)
    return attrs


def emit_alert_closed_evidence_only(*, alert_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, status="evidence_only_closed", result="success", proof_kind=proof_kind)
    record_event("novali.operator_alert.closed_evidence_only", attrs)
    return attrs


def emit_alert_superseded(*, alert_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, status="superseded", result="success", proof_kind=proof_kind)
    record_event("novali.operator_alert.superseded", attrs)
    return attrs


def emit_read_only_alert_mapped(*, alert_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, severity=severity, source="read_only_adapter", result="success", proof_kind=proof_kind)
    record_counter("novali.operator_alert.read_only.count", 1, attrs)
    record_event("novali.operator_alert.read_only_mapped", attrs)
    return attrs


def emit_runtime_candidate_evaluated(*, alert_type: str, source: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(alert_type=alert_type, source=source, result="success", proof_kind=proof_kind)
    record_counter("novali.operator_alert.telemetry_candidate.count", 1, attrs)
    record_event("novali.operator_alert.telemetry_candidate.evaluate", attrs)
    return attrs


def emit_admission_assessed(*, target_name: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(source=target_name, result=result, proof_kind=proof_kind)
    record_counter("novali.operator_alert.admission_assessment.count", 1, attrs)
    record_event("novali.operator_alert.admission_assessed", attrs)
    return attrs


def emit_operator_alert_proof_completed(*, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(result=result, proof_kind=proof_kind)
    record_event("novali.operator_alert.rc88_proof.completed", attrs)
    return attrs
