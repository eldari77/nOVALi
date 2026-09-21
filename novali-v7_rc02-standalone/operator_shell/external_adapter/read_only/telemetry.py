from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from operator_shell.observability import record_counter, record_event, trace_span

from .schemas import DEFAULT_READ_ONLY_ADAPTER_KIND, DEFAULT_READ_ONLY_ADAPTER_NAME


def _attrs(
    *,
    adapter_name: str = DEFAULT_READ_ONLY_ADAPTER_NAME,
    adapter_kind: str = DEFAULT_READ_ONLY_ADAPTER_KIND,
    adapter_mode: str = "fixture_read_only",
    source_kind: str = "static_fixture",
    environment_kind: str = "generic_non_se_sandbox",
    validation_status: str | None = None,
    integrity_status: str | None = None,
    review_status: str | None = None,
    review_trigger: str | None = None,
    lane_id: str | None = None,
    lane_role: str | None = None,
    result: str | None = None,
    proof_kind: str | None = None,
) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "novali.adapter.name": adapter_name,
        "novali.adapter.kind": adapter_kind,
        "novali.adapter.mode": adapter_mode,
        "novali.source.kind": source_kind,
        "novali.environment.kind": environment_kind,
    }
    if validation_status:
        attrs["novali.validation.status"] = validation_status
    if integrity_status:
        attrs["novali.integrity.status"] = integrity_status
    if review_status:
        attrs["novali.review_status"] = review_status
    if review_trigger:
        attrs["novali.review_trigger"] = review_trigger
    if lane_id:
        attrs["novali.controller.lane"] = lane_id
    if lane_role:
        attrs["novali.controller.role"] = lane_role
    if result:
        attrs["novali.result"] = result
    if proof_kind:
        attrs["novali.proof_kind"] = proof_kind
    return attrs


@contextmanager
def read_only_span(name: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
    attributes = _attrs(**kwargs)
    with trace_span(name, attributes):
        yield {"attributes": attributes}


def emit_snapshot_loaded(*, lane_id: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, result=result, proof_kind=proof_kind)
    record_counter("novali.read_only_adapter.snapshot.load.count", 1, attrs)
    record_event("novali.read_only_adapter.snapshot.loaded", attrs)
    return attrs


def emit_schema_validated(*, lane_id: str, validation_status: str, review_status: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        lane_id=lane_id,
        validation_status=validation_status,
        review_status=review_status,
        result="success" if validation_status == "clean" else "failure",
        proof_kind=proof_kind,
    )
    record_counter("novali.read_only_adapter.snapshot.validation.count", 1, attrs)
    record_event("novali.read_only_adapter.schema.validated", attrs)
    return attrs


def emit_integrity_result(*, lane_id: str, integrity_status: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        lane_id=lane_id,
        integrity_status=integrity_status,
        result="success" if integrity_status in {"clean", "warning"} else "failure",
        proof_kind=proof_kind,
    )
    if integrity_status not in {"clean", "warning"}:
        record_counter("novali.read_only_adapter.integrity.failure.count", 1, attrs)
        record_event("novali.read_only_adapter.integrity.failed", attrs, severity="warning")
    else:
        record_event("novali.read_only_adapter.integrity.clean", attrs)
    return attrs


def emit_conflict_detected(*, lane_id: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, review_trigger="read_only_conflicting_observation", result="failure", proof_kind=proof_kind)
    record_counter("novali.read_only_adapter.conflict.count", 1, attrs)
    record_event("novali.read_only_adapter.conflict.detected", attrs, severity="warning")
    return attrs


def emit_stale_snapshot_detected(*, lane_id: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, review_trigger="read_only_stale_snapshot", result="warning", proof_kind=proof_kind)
    record_counter("novali.read_only_adapter.stale_snapshot.count", 1, attrs)
    record_event("novali.read_only_adapter.stale_snapshot.detected", attrs, severity="warning")
    return attrs


def emit_replay_written(*, lane_id: str, validation_status: str, integrity_status: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        lane_id=lane_id,
        validation_status=validation_status,
        integrity_status=integrity_status,
        result="success",
        proof_kind=proof_kind,
    )
    record_counter("novali.read_only_adapter.replay_packet.write.count", 1, attrs)
    record_event("novali.read_only_adapter.replay_packet.written", attrs)
    return attrs


def emit_review_ticket_created(*, lane_id: str, review_trigger: str, review_status: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(
        lane_id=lane_id,
        review_trigger=review_trigger,
        review_status=review_status,
        result="failure",
        proof_kind=proof_kind,
    )
    record_counter("novali.read_only_adapter.review_ticket.count", 1, attrs)
    record_event("novali.read_only_adapter.review_ticket.created", attrs, severity="warning")
    return attrs


def emit_rollback_analysis_created(*, lane_id: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, result=result, proof_kind=proof_kind)
    record_counter("novali.read_only_adapter.rollback_analysis.count", 1, attrs)
    record_event("novali.read_only_adapter.rollback_analysis.created", attrs)
    return attrs


def emit_mutation_refused(*, lane_id: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, review_trigger="read_only_mutation_requested", result="failure", proof_kind=proof_kind)
    record_counter("novali.read_only_adapter.mutation.refusal.count", 1, attrs)
    record_event("novali.read_only_adapter.mutation.refused", attrs, severity="warning")
    return attrs


def emit_lane_attribution_result(*, lane_id: str, lane_role: str, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(lane_id=lane_id, lane_role=lane_role, result=result, proof_kind=proof_kind)
    if result != "success":
        record_counter("novali.read_only_adapter.lane_attribution.failure.count", 1, attrs)
        record_event("novali.read_only_adapter.lane_attribution.failed", attrs, severity="warning")
    return attrs


def emit_proof_completed(*, result: str, proof_kind: str) -> dict[str, Any]:
    attrs = _attrs(result=result, proof_kind=proof_kind)
    record_event("novali.read_only_adapter.rc87_proof.completed", attrs)
    return attrs
