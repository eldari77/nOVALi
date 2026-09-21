from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from operator_shell.observability import record_counter, record_event, record_gauge_or_observable, trace_span


def _attrs(
    *,
    lane_role: str | None = None,
    lane_id: str | None = None,
    source_lane_id: str | None = None,
    target_lane_id: str | None = None,
    isolation_status: str | None = None,
    bleed_type: str | None = None,
    review_status: str | None = None,
    review_trigger: str | None = None,
    message_type: str | None = None,
    result: str | None = None,
    proof_kind: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if lane_role:
        payload["novali.controller.role"] = lane_role
    if lane_id:
        payload["novali.controller.lane"] = lane_id
    if source_lane_id:
        payload["novali.controller.source_lane"] = source_lane_id
    if target_lane_id:
        payload["novali.controller.target_lane"] = target_lane_id
    if isolation_status:
        payload["novali.isolation.status"] = isolation_status
    if bleed_type:
        payload["novali.identity_bleed.type"] = bleed_type
    if review_status:
        payload["novali.review_status"] = review_status
    if review_trigger:
        payload["novali.review_trigger"] = review_trigger
    if message_type:
        payload["novali.message_type"] = message_type
    if result:
        payload["novali.result"] = result
    if proof_kind:
        payload["novali.proof_kind"] = proof_kind
    return payload


@contextmanager
def isolation_span(
    name: str,
    **kwargs: Any,
) -> Iterator[dict[str, Any]]:
    attributes = _attrs(**kwargs)
    with trace_span(name, attributes) as span:
        yield {"span": span, "attributes": attributes}


def emit_registry_created(*, lane_count: int, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(result="success", proof_kind=proof_kind)
    record_gauge_or_observable("novali.controller_isolation.lane.count", lane_count, attrs)
    record_event("novali.controller_isolation.registry.created", attrs)
    return attrs


def emit_namespace_check(*, status: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(isolation_status=status, result="success" if status == "pass" else "failure", proof_kind=proof_kind)
    record_counter("novali.controller_isolation.namespace_check.count", 1, attrs)
    record_event(
        "novali.controller_isolation.namespace.check_passed"
        if status == "pass"
        else "novali.controller_isolation.namespace.check_failed",
        attrs,
    )
    return attrs


def emit_cross_lane_message(*, source_lane_id: str, target_lane_id: str, message_type: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        source_lane_id=source_lane_id,
        target_lane_id=target_lane_id,
        message_type=message_type,
        result=result,
        proof_kind=proof_kind,
    )
    record_counter("novali.controller_isolation.cross_message.count", 1, attrs)
    if result == "blocked":
        record_counter("novali.controller_isolation.cross_message.blocked.count", 1, attrs)
        record_event("novali.controller_isolation.cross_message.blocked", attrs)
    elif result == "director_approved":
        record_event("novali.controller_isolation.cross_message.approved_mock_only", attrs)
    else:
        record_event("novali.controller_isolation.cross_message.proposed", attrs)
    return attrs


def emit_identity_bleed(*, lane_id: str, bleed_type: str, severity: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        lane_id=lane_id,
        bleed_type=bleed_type,
        result="failure",
        proof_kind=proof_kind,
        isolation_status="review_required" if severity != "critical" else "review_blocked",
    )
    record_counter("novali.controller_isolation.identity_bleed.finding.count", 1, attrs)
    if severity == "critical":
        record_counter("novali.controller_isolation.identity_bleed.critical.count", 1, attrs)
    record_event("novali.controller_isolation.identity_bleed.detected", attrs)
    return attrs


def emit_review_ticket_created(*, review_status: str, review_trigger: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(review_status=review_status, review_trigger=review_trigger, result="success", proof_kind=proof_kind)
    record_counter("novali.controller_isolation.review_ticket.count", 1, attrs)
    record_event("novali.controller_isolation.review_ticket.created", attrs)
    return attrs


def emit_replay_packet_written(*, lane_id: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, result=result, proof_kind=proof_kind)
    record_counter("novali.controller_isolation.replay_packet.write.count", 1, attrs)
    record_event("novali.controller_isolation.replay_packet.written", attrs)
    return attrs


def emit_proof_completed(*, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(result=result, proof_kind=proof_kind)
    record_event("novali.controller_isolation.rc86_proof.completed", attrs)
    return attrs
