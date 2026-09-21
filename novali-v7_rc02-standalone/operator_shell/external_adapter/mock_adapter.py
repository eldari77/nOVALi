from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from operator_shell.observability.redaction import redact_attributes, redact_value

from .contract import AdapterContext, ExternalWorldAdapter
from .review import classify_action_request
from .schemas import (
    DEFAULT_ADAPTER_KIND,
    DEFAULT_ADAPTER_NAME,
    ExternalActionPreconditions,
    ExternalActionProposal,
    ExternalActionResult,
    KillSwitchEvent,
    PreconditionValidationResult,
    ReplayPacket,
    RollbackAnalysis,
    WorldSnapshot,
)
from .telemetry import (
    adapter_span,
    emit_action_proposed,
    emit_action_result,
    emit_kill_switch,
    emit_preconditions_result,
    emit_replay_written,
    emit_result_acknowledged,
    emit_review_required,
    emit_rollback_analysis,
    emit_snapshot,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class MockExternalWorldAdapter(ExternalWorldAdapter):
    def __init__(
        self,
        *,
        adapter_name: str = DEFAULT_ADAPTER_NAME,
        adapter_kind: str = DEFAULT_ADAPTER_KIND,
        proof_kind: str = "mock_membrane",
    ) -> None:
        self.adapter_name = adapter_name
        self.adapter_kind = adapter_kind
        self.proof_kind = proof_kind
        self.kill_switch_state = "inactive"
        self._uncertain_count = 0

    def get_world_snapshot(self, context: AdapterContext) -> WorldSnapshot:
        with adapter_span(
            "novali.external_adapter.snapshot",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            result="success",
            proof_kind=self.proof_kind,
        ):
            snapshot = WorldSnapshot(
                snapshot_id=_short_id("snapshot"),
                adapter_name=self.adapter_name,
                adapter_kind=self.adapter_kind,
                source_controller=context.source_controller,
                world_state_ref="mock-world-state",
                summary="Mock external-world snapshot captured without mutating any external system.",
                observed_at=_now_iso(),
                telemetry_context={
                    "proof_kind": context.proof_kind,
                    "trace_hint": context.telemetry_trace_hint,
                },
            )
            emit_snapshot(self.adapter_name, self.adapter_kind, proof_kind=self.proof_kind)
            return snapshot

    def propose_action(
        self,
        snapshot: WorldSnapshot,
        action_request: dict[str, Any],
    ) -> ExternalActionProposal:
        action_type = str(action_request.get("action_type", "") or "").strip()
        with adapter_span(
            "novali.external_adapter.action.proposed",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=action_type,
            action_status="proposed",
            result="success",
            proof_kind=self.proof_kind,
        ):
            missing: list[str] = []
            if self.kill_switch_state == "triggered" and action_type != "noop.kill_switch_test":
                missing.append("kill_switch_inactive")
            if action_type == "noop.annotate" and not str(action_request.get("annotation", "")).strip():
                missing.append("annotation")
            review_requirement = classify_action_request(
                action_type,
                preconditions_missing=missing,
                payload_safe=True,
                repeated_uncertain=self._uncertain_count >= 2,
                kill_switch_triggered=self.kill_switch_state == "triggered" and action_type != "noop.kill_switch_test",
                scope_expansion_pressure=action_type == "noop.trigger_review",
            )
            preconditions = ExternalActionPreconditions(
                summary=(
                    "Mock adapter preconditions are satisfied."
                    if not review_requirement.review_required
                    else "Mock adapter preconditions require review before execution."
                ),
                required=["allowed_action_type", "mock_only_scope"],
                missing=missing,
                safe_scope="mock_only",
                payload_safe=True,
            )
            proposal = ExternalActionProposal(
                action_id=_short_id("action"),
                adapter_name=self.adapter_name,
                adapter_kind=self.adapter_kind,
                action_type=action_type,
                action_version="rc85.v1",
                source_controller=str(action_request.get("source_controller", snapshot.source_controller) or snapshot.source_controller),
                governing_directive_ref=str(action_request.get("governing_directive_ref", "mock.directive.rc85") or "mock.directive.rc85"),
                intended_effect=str(redact_value(action_request.get("intended_effect", "mock_only_proof")) or "mock_only_proof"),
                arguments_redacted=redact_attributes(dict(action_request.get("arguments", {}) or {})),
                preconditions=preconditions,
                expected_duration_ms=int(action_request.get("expected_duration_ms", 25) or 25),
                timeout_ms=int(action_request.get("timeout_ms", 1000) or 1000),
                idempotency_key=str(action_request.get("idempotency_key", _short_id("idem")) or _short_id("idem")),
                requires_review=review_requirement.review_required,
                review_reasons=list(review_requirement.review_reasons),
                created_at=_now_iso(),
                telemetry_context=dict(snapshot.telemetry_context),
                status="review_required" if review_requirement.review_required else "proposed",
            )
            emit_action_proposed(
                self.adapter_name,
                self.adapter_kind,
                action_type=action_type,
                review_status=review_requirement.review_status,
                proof_kind=self.proof_kind,
            )
            if review_requirement.review_required:
                with adapter_span(
                    "novali.external_adapter.action.review_required",
                    adapter_name=self.adapter_name,
                    adapter_kind=self.adapter_kind,
                    action_type=action_type,
                    action_status="review_required",
                    review_status="review_required",
                    result="failure",
                    proof_kind=self.proof_kind,
                ):
                    emit_review_required(
                        self.adapter_name,
                        self.adapter_kind,
                        action_type=action_type,
                        proof_kind=self.proof_kind,
                    )
            return proposal

    def validate_preconditions(
        self,
        proposal: ExternalActionProposal,
        snapshot: WorldSnapshot,
    ) -> PreconditionValidationResult:
        with adapter_span(
            "novali.external_adapter.preconditions.validate",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=proposal.action_type,
            action_status=proposal.status,
            result="success",
            proof_kind=self.proof_kind,
        ):
            missing = list(proposal.preconditions.missing)
            review_requirement = classify_action_request(
                proposal.action_type,
                preconditions_missing=missing,
                payload_safe=proposal.preconditions.payload_safe,
                repeated_uncertain=self._uncertain_count >= 2 and proposal.action_type == "noop.simulate_uncertain",
                kill_switch_triggered=self.kill_switch_state == "triggered" and proposal.action_type != "noop.kill_switch_test",
                scope_expansion_pressure=proposal.action_type == "noop.trigger_review",
            )
            valid = not review_requirement.review_required
            status = "approved_for_mock_execution" if valid else "precondition_failed"
            summary = (
                "Mock adapter preconditions validated successfully."
                if valid
                else review_requirement.summary
            )
            emit_preconditions_result(
                self.adapter_name,
                self.adapter_kind,
                action_type=proposal.action_type,
                valid=valid,
                review_status=review_requirement.review_status,
                proof_kind=self.proof_kind,
            )
            if review_requirement.review_required:
                with adapter_span(
                    "novali.external_adapter.action.review_required",
                    adapter_name=self.adapter_name,
                    adapter_kind=self.adapter_kind,
                    action_type=proposal.action_type,
                    action_status="review_required",
                    review_status="review_required",
                    result="failure",
                    proof_kind=self.proof_kind,
                ):
                    emit_review_required(
                        self.adapter_name,
                        self.adapter_kind,
                        action_type=proposal.action_type,
                        proof_kind=self.proof_kind,
                    )
            return PreconditionValidationResult(
                valid=valid,
                status=status,
                summary=summary,
                preconditions=proposal.preconditions,
                review_requirement=review_requirement,
            )

    def execute_bounded_action(self, proposal: ExternalActionProposal) -> ExternalActionResult:
        duration_ms = max(1, int(proposal.expected_duration_ms or 25))
        with adapter_span(
            "novali.external_adapter.action.mock_execute",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=proposal.action_type,
            action_status="approved_for_mock_execution",
            result="success",
            proof_kind=self.proof_kind,
        ):
            status = "executed"
            result_summary = "Mock adapter executed the bounded action without mutating any external system."
            failure_reason = None
            uncertainty_reason = None
            review_required = False
            review_reasons: list[str] = []

            if proposal.action_type == "noop.simulate_failure":
                status = "failed"
                result_summary = "Mock adapter simulated a bounded external failure."
                failure_reason = "mock failure outcome requested for proof coverage"
            elif proposal.action_type == "noop.simulate_uncertain":
                status = "uncertain"
                result_summary = "Mock adapter simulated an uncertain bounded external outcome."
                uncertainty_reason = "mock uncertainty outcome requested for proof coverage"
                self._uncertain_count += 1
            elif proposal.action_type == "noop.kill_switch_test":
                kill_switch = self.trigger_kill_switch(
                    "mock kill switch test requested",
                    "mock_adapter_proof_scope",
                )
                status = "kill_switch_triggered"
                result_summary = "Mock adapter kill switch triggered for proof-only state."
                review_required = True
                review_reasons = ["kill switch triggered"]
                uncertainty_reason = kill_switch.reason_redacted
            elif proposal.action_type == "noop.trigger_review":
                status = "review_required"
                result_summary = "Mock adapter raised a review-required outcome without execution."
                review_required = True
                review_reasons = ["scope expansion pressure"]
            elif proposal.action_type.startswith("real.") or proposal.action_type in {
                "game.server_action",
                "filesystem.mutation",
                "outbound.message",
                "account.create",
                "spaceengineers.action",
            }:
                status = "review_required"
                result_summary = "Mock adapter refused a live external mutation request."
                review_required = True
                review_reasons = ["live external mutation requested in rc85"]
                failure_reason = "mock adapter refused a non-noop external action"
            elif proposal.action_type not in {"noop.observe", "noop.annotate", "noop.simulate_success"}:
                status = "review_required"
                result_summary = "Mock adapter refused to execute an unknown action type."
                review_required = True
                review_reasons = ["unknown action type"]

            result = ExternalActionResult(
                action_id=proposal.action_id,
                adapter_name=self.adapter_name,
                adapter_kind=self.adapter_kind,
                action_type=proposal.action_type,
                status=status,
                result_summary=str(redact_value(result_summary) or ""),
                completed_at=_now_iso(),
                duration_ms=duration_ms,
                failure_reason_redacted=str(redact_value(failure_reason) or "") or None,
                uncertainty_reason_redacted=str(redact_value(uncertainty_reason) or "") or None,
                review_required=review_required,
                review_reasons=list(review_reasons),
                mock_mutation_performed=False,
            )
            emit_action_result(
                self.adapter_name,
                self.adapter_kind,
                action_type=proposal.action_type,
                status=result.status,
                duration_ms=duration_ms,
                proof_kind=self.proof_kind,
            )
            if review_required:
                emit_review_required(
                    self.adapter_name,
                    self.adapter_kind,
                    action_type=proposal.action_type,
                    proof_kind=self.proof_kind,
                )
            return result

    def acknowledge_result(
        self,
        action_id: str,
        result: ExternalActionResult,
    ) -> dict[str, Any]:
        with adapter_span(
            "novali.external_adapter.action.result_acknowledged",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=result.action_type,
            action_status=result.status,
            result="success",
            proof_kind=self.proof_kind,
        ):
            emit_result_acknowledged(
                self.adapter_name,
                self.adapter_kind,
                action_type=result.action_type,
                status=result.status,
                proof_kind=self.proof_kind,
            )
            return {
                "action_id": action_id,
                "acknowledged": True,
                "acknowledgement_state": "recorded",
                "acknowledged_at": _now_iso(),
                "summary": "Mock adapter recorded the result acknowledgement without changing authority.",
            }

    def emit_replay_packet(
        self,
        proposal: ExternalActionProposal,
        result: ExternalActionResult,
        snapshot: WorldSnapshot,
        review_state: dict[str, Any],
    ) -> ReplayPacket:
        with adapter_span(
            "novali.external_adapter.replay_packet.write",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=proposal.action_type,
            action_status=result.status,
            result="success",
            proof_kind=self.proof_kind,
        ):
            rollback_candidate = result.status in {
                "executed",
                "failed",
                "uncertain",
                "kill_switch_triggered",
            }
            packet = ReplayPacket(
                schema_version="rc85.v1",
                replay_packet_id=_short_id("replay"),
                action_id=proposal.action_id,
                adapter_name=self.adapter_name,
                adapter_kind=self.adapter_kind,
                source_controller=proposal.source_controller,
                governing_directive_ref=proposal.governing_directive_ref,
                action_type=proposal.action_type,
                intended_effect=proposal.intended_effect,
                preconditions_summary=proposal.preconditions.summary,
                pre_state_snapshot_ref=snapshot.snapshot_id,
                post_state_result=result.status,
                status=result.status,
                result_summary=result.result_summary,
                failure_reason_redacted=result.failure_reason_redacted,
                uncertainty_reason_redacted=result.uncertainty_reason_redacted,
                retry_count=0,
                timeout_ms=proposal.timeout_ms,
                rollback_candidate=rollback_candidate,
                rollback_analysis_ref=None,
                review_required=bool(review_state.get("review_required", result.review_required)),
                review_reasons=list(
                    review_state.get("review_reasons", result.review_reasons) or []
                ),
                kill_switch_state=self.kill_switch_state,
                telemetry_trace_hint=str(
                    proposal.telemetry_context.get("trace_hint", "") or self.proof_kind
                ),
                created_at=proposal.created_at,
                completed_at=result.completed_at,
                review_item_id=str(review_state.get("review_item_id", "")).strip() or None,
                review_status=str(review_state.get("review_status", "clear") or "clear"),
                rollback_analysis_id=str(review_state.get("rollback_analysis_id", "")).strip() or None,
                checkpoint_ref=str(review_state.get("checkpoint_ref", "")).strip() or None,
                prior_stable_state_ref=str(
                    review_state.get("prior_stable_state_ref", snapshot.world_state_ref)
                    or snapshot.world_state_ref
                ),
                escalation_status=str(review_state.get("escalation_status", "clear") or "clear"),
                escalation_reasons=list(review_state.get("escalation_reasons", []) or []),
                evidence_integrity_status=str(
                    review_state.get("evidence_integrity_status", "warning") or "warning"
                ),
                restore_allowed=bool(review_state.get("restore_allowed", False)),
                restore_performed=bool(review_state.get("restore_performed", False)),
            )
            emit_replay_written(
                self.adapter_name,
                self.adapter_kind,
                action_type=proposal.action_type,
                status=result.status,
                rollback_candidate=rollback_candidate,
                proof_kind=self.proof_kind,
            )
            return packet

    def request_rollback_analysis(self, replay_packet: ReplayPacket) -> RollbackAnalysis:
        with adapter_span(
            "novali.external_adapter.rollback_analysis.requested",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            action_type=replay_packet.action_type,
            result="success",
            rollback_candidate=bool(replay_packet.rollback_candidate),
            proof_kind=self.proof_kind,
        ):
            analysis = RollbackAnalysis(
                rollback_analysis_id=_short_id("rollback"),
                replay_packet_id=replay_packet.replay_packet_id,
                action_id=replay_packet.action_id,
                rollback_possible=bool(replay_packet.rollback_candidate),
                rollback_candidate=bool(replay_packet.rollback_candidate),
                rollback_scope="mock_adapter_only",
                prior_stable_state_ref=str(
                    replay_packet.prior_stable_state_ref or replay_packet.pre_state_snapshot_ref
                ),
                checkpoint_ref=str(replay_packet.checkpoint_ref or "") or None,
                checkpoint_available=bool(str(replay_packet.checkpoint_ref or "").strip()),
                evidence_preserved=True,
                evidence_paths=[],
                operator_action_required=bool(
                    replay_packet.review_required
                    or replay_packet.status in {"uncertain", "kill_switch_triggered"}
                ),
                reason_redacted=(
                    "Rollback is analysis-only in rc85 because the mock adapter never mutates a real external world."
                ),
                ambiguity_level=(
                    "high"
                    if "rollback ambiguity" in list(replay_packet.review_reasons or [])
                    else "low"
                ),
                ambiguity_reasons=(
                    ["rollback ambiguity"]
                    if "rollback ambiguity" in list(replay_packet.review_reasons or [])
                    else []
                ),
                restore_allowed=False,
                restore_performed=False,
                created_at=_now_iso(),
            )
            emit_rollback_analysis(
                self.adapter_name,
                self.adapter_kind,
                action_type=replay_packet.action_type,
                rollback_candidate=analysis.rollback_candidate,
                proof_kind=self.proof_kind,
            )
            return analysis

    def trigger_kill_switch(self, reason: str, scope: str) -> KillSwitchEvent:
        with adapter_span(
            "novali.external_adapter.kill_switch.triggered",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            result="success",
            kill_switch_state="triggered",
            proof_kind=self.proof_kind,
        ):
            self.kill_switch_state = "triggered"
            emit_kill_switch(
                self.adapter_name,
                self.adapter_kind,
                proof_kind=self.proof_kind,
            )
            return KillSwitchEvent(
                kill_switch_event_id=_short_id("kill-switch"),
                adapter_name=self.adapter_name,
                adapter_kind=self.adapter_kind,
                reason_redacted=str(redact_value(reason) or ""),
                scope=str(redact_value(scope) or ""),
                state=self.kill_switch_state,
                created_at=_now_iso(),
            )
