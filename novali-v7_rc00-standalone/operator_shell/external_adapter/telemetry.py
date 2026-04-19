from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Mapping

from operator_shell.observability import (
    record_counter,
    record_event,
    record_histogram,
    trace_span,
)


def _attrs(
    *,
    adapter_name: str,
    adapter_kind: str,
    action_type: str | None = None,
    action_status: str | None = None,
    review_status: str | None = None,
    result: str | None = None,
    rollback_candidate: bool | None = None,
    review_severity: str | None = None,
    rollback_ambiguity_level: str | None = None,
    evidence_integrity_status: str | None = None,
    kill_switch_state: str | None = None,
    proof_kind: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "novali.adapter.name": adapter_name,
        "novali.adapter.kind": adapter_kind,
    }
    if action_type:
        payload["novali.action.type"] = action_type
    if action_status:
        payload["novali.action.status"] = action_status
    if review_status:
        payload["novali.review_status"] = review_status
    if result:
        payload["novali.result"] = result
    if rollback_candidate is not None:
        payload["novali.rollback_candidate"] = "true" if rollback_candidate else "false"
    if review_severity:
        payload["novali.review.severity"] = review_severity
    if rollback_ambiguity_level:
        payload["novali.rollback.ambiguity_level"] = rollback_ambiguity_level
    if evidence_integrity_status:
        payload["novali.evidence_integrity_status"] = evidence_integrity_status
    if kill_switch_state:
        payload["novali.kill_switch_state"] = kill_switch_state
    if proof_kind:
        payload["novali.proof_kind"] = proof_kind
    return payload


@contextmanager
def adapter_span(
    name: str,
    *,
    adapter_name: str,
    adapter_kind: str,
    action_type: str | None = None,
    action_status: str | None = None,
    review_status: str | None = None,
    result: str | None = None,
    rollback_candidate: bool | None = None,
    review_severity: str | None = None,
    rollback_ambiguity_level: str | None = None,
    evidence_integrity_status: str | None = None,
    kill_switch_state: str | None = None,
    proof_kind: str | None = None,
    extra_attributes: Mapping[str, Any] | None = None,
):
    attributes = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status=action_status,
        review_status=review_status,
        result=result,
        rollback_candidate=rollback_candidate,
        review_severity=review_severity,
        rollback_ambiguity_level=rollback_ambiguity_level,
        evidence_integrity_status=evidence_integrity_status,
        kill_switch_state=kill_switch_state,
        proof_kind=proof_kind,
    )
    if extra_attributes:
        attributes.update(dict(extra_attributes))
    with trace_span(name, attributes):
        yield


def emit_snapshot(adapter_name: str, adapter_kind: str, *, proof_kind: str) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        result="success",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.snapshot.count", 1, attrs)
    record_event("novali.external_adapter.snapshot", attrs)


def emit_action_proposed(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    review_status: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status="proposed",
        review_status=review_status,
        result="success",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.action.count", 1, attrs)
    record_event("novali.external_adapter.action.proposed", attrs)


def emit_preconditions_result(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    valid: bool,
    review_status: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status="approved_for_mock_execution" if valid else "precondition_failed",
        review_status=review_status,
        result="success" if valid else "failure",
        proof_kind=proof_kind,
    )
    if valid:
        record_event("novali.external_adapter.action.proposed", attrs)
    else:
        record_counter("novali.external_adapter.review_required.count", 1, attrs)
        record_event("novali.external_adapter.preconditions.failed", attrs, severity="warning")


def emit_review_required(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status="review_required",
        review_status="review_required",
        result="failure",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.review_required.count", 1, attrs)
    record_event("novali.external_adapter.action.review_required", attrs, severity="warning")


def emit_action_result(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    status: str,
    duration_ms: int,
    proof_kind: str,
) -> None:
    result = "success"
    if status in {"failed", "precondition_failed"}:
        result = "failure"
    elif status == "uncertain":
        result = "uncertain"
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status=status,
        result=result,
        proof_kind=proof_kind,
        rollback_candidate=status in {"executed", "failed", "uncertain", "kill_switch_triggered"},
        kill_switch_state="triggered" if status == "kill_switch_triggered" else "inactive",
    )
    record_histogram("novali.external_adapter.action.duration_ms", duration_ms, attrs)
    if status == "failed":
        record_counter("novali.external_adapter.action.failure.count", 1, attrs)
        record_event("novali.external_adapter.action.failed", attrs, severity="warning")
    elif status == "uncertain":
        record_counter("novali.external_adapter.action.uncertain.count", 1, attrs)
        record_event("novali.external_adapter.action.uncertain", attrs, severity="warning")
    else:
        record_event("novali.external_adapter.action.mock_executed", attrs)


def emit_result_acknowledged(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    status: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status=status,
        result="success",
        proof_kind=proof_kind,
    )
    record_event("novali.external_adapter.action.result_acknowledged", attrs)


def emit_replay_written(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    status: str,
    rollback_candidate: bool,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status=status,
        result="success",
        rollback_candidate=rollback_candidate,
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.replay_packet.write.count", 1, attrs)
    record_event("novali.external_adapter.replay_packet.written", attrs)


def emit_rollback_analysis(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    rollback_candidate: bool,
    ambiguity_level: str = "low",
    restore_allowed: bool = False,
    restore_performed: bool = False,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        result="success",
        rollback_candidate=rollback_candidate,
        rollback_ambiguity_level=ambiguity_level,
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.rollback_analysis.count", 1, attrs)
    if ambiguity_level not in {"", "none", "low"}:
        record_counter("novali.external_adapter.rollback.ambiguity.count", 1, attrs)
    if restore_allowed:
        record_counter("novali.external_adapter.rollback.restore_allowed.count", 1, attrs)
    if restore_performed:
        record_counter("novali.external_adapter.rollback.restore_performed.count", 1, attrs)
    record_event("novali.external_adapter.rollback_analysis.created", attrs)


def emit_kill_switch(
    adapter_name: str,
    adapter_kind: str,
    *,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        result="success",
        kill_switch_state="triggered",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.kill_switch.count", 1, attrs)
    record_event("novali.external_adapter.kill_switch.triggered", attrs, severity="warning")


def emit_redaction_failure(
    adapter_name: str,
    adapter_kind: str,
    *,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        result="failure",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.redaction.failure.count", 1, attrs)
    record_event("novali.external_adapter.redaction_failure", attrs, severity="critical")


def emit_review_item_created(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    review_status: str,
    review_severity: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status="review_required",
        review_status=review_status,
        review_severity=review_severity,
        result="success",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.review_item.count", 1, attrs)
    if review_status == "pending_review":
        record_counter("novali.external_adapter.review_item.pending.count", 1, attrs)
    if review_status == "evidence_missing":
        record_counter("novali.external_adapter.evidence_missing.count", 1, attrs)
    if review_status == "escalated":
        record_counter("novali.external_adapter.review_item.escalated.count", 1, attrs)
        record_event("novali.external_adapter.review.escalated", attrs, severity="warning")
    else:
        record_event("novali.external_adapter.review.item_created", attrs)


def emit_evidence_integrity(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    integrity_status: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        result="success" if integrity_status == "clean" else "failure",
        evidence_integrity_status=integrity_status,
        proof_kind=proof_kind,
    )
    if integrity_status == "failed":
        record_counter("novali.external_adapter.integrity.failure.count", 1, attrs)
        record_event("novali.external_adapter.evidence.integrity_failed", attrs, severity="warning")
    else:
        record_event("novali.external_adapter.evidence.integrity_clean", attrs)


def emit_rollback_linkage(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    ambiguity_level: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        result="success",
        rollback_ambiguity_level=ambiguity_level,
        proof_kind=proof_kind,
    )
    record_event("novali.external_adapter.rollback.analysis_created", attrs)
    if ambiguity_level not in {"", "none", "low"}:
        record_counter("novali.external_adapter.rollback.ambiguity.count", 1, attrs)
        record_event("novali.external_adapter.rollback.ambiguity_detected", attrs, severity="warning")


def emit_review_hold_summary(
    adapter_name: str,
    adapter_kind: str,
    *,
    review_status: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        review_status=review_status,
        result="success",
        proof_kind=proof_kind,
    )
    record_counter("novali.external_adapter.review_hold.enter.count", 1, attrs)
    record_event("novali.external_adapter.review_hold.enter", attrs)
    record_event("novali.external_adapter.review_hold.summary", attrs)


def emit_live_mutation_refused(
    adapter_name: str,
    adapter_kind: str,
    *,
    action_type: str,
    proof_kind: str,
) -> None:
    attrs = _attrs(
        adapter_name=adapter_name,
        adapter_kind=adapter_kind,
        action_type=action_type,
        action_status="review_required",
        review_status="escalated",
        review_severity="critical",
        result="failure",
        proof_kind=proof_kind,
    )
    record_event("novali.external_adapter.live_mutation.refused", attrs, severity="critical")
