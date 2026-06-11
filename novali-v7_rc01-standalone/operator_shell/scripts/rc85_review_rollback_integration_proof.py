from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.external_adapter import (
    AdapterContext,
    MockExternalWorldAdapter,
    build_review_item,
    evaluate_evidence_integrity,
    load_external_adapter_review_status,
    load_external_adapter_status,
    resolve_rc85_artifact_root,
    resolve_replay_ledger_path,
    resolve_replay_packets_root,
    resolve_review_items_root,
    resolve_rollback_analysis_root,
    summarize_replay_ledger,
    summarize_review_items,
    summarize_rollback_analyses,
    write_evidence_integrity_summary,
    write_replay_packet,
    write_review_item,
    write_review_rollback_analysis,
)
from operator_shell.external_adapter.review import classify_action_request
from operator_shell.external_adapter.schemas import ExternalActionResult
from operator_shell.external_adapter.telemetry import (
    adapter_span,
    emit_evidence_integrity,
    emit_live_mutation_refused,
    emit_redaction_failure,
    emit_review_hold_summary,
    emit_review_item_created,
    emit_rollback_linkage,
)
from operator_shell.observability import (
    flush_observability,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    shutdown_observability,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts
from operator_shell.observability.redaction import redact_value
from operator_shell.web_operator import OperatorWebService

SUMMARY_JSON_NAME = "review_rollback_integration_summary.json"
SUMMARY_MD_NAME = "review_rollback_integration_summary.md"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "RC85", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "external_payload": _fake_seed("external", "payload", "secret"),
        "rollback_context": _fake_seed("rollback", "context"),
        "OTEL_EXPORTER_OTLP_HEADERS": f"authorization=Bearer {_fake_seed('otel', 'header')}",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"rc85-review-rollback-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _review_only_result(
    *,
    proposal: Any,
    status: str,
    summary: str,
    review_reasons: list[str],
    failure_reason: str | None = None,
    uncertainty_reason: str | None = None,
) -> ExternalActionResult:
    return ExternalActionResult(
        action_id=proposal.action_id,
        adapter_name=proposal.adapter_name,
        adapter_kind=proposal.adapter_kind,
        action_type=proposal.action_type,
        status=status,
        result_summary=str(redact_value(summary) or ""),
        completed_at=_now_iso(),
        duration_ms=max(1, int(proposal.expected_duration_ms or 1)),
        failure_reason_redacted=str(redact_value(failure_reason) or "") or None,
        uncertainty_reason_redacted=str(redact_value(uncertainty_reason) or "") or None,
        review_required=True,
        review_reasons=list(review_reasons),
        mock_mutation_performed=False,
    )


def _clear_existing_artifacts(
    *,
    package_root: Path,
    env: dict[str, str],
) -> None:
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    for root in (
        resolve_replay_packets_root(package_root, env=env, version="rc85"),
        resolve_review_items_root(package_root, env=env),
        resolve_rollback_analysis_root(package_root, env=env),
    ):
        if root.exists():
            for path in root.glob("*"):
                if path.is_file():
                    path.unlink()
    replay_ledger_path = resolve_replay_ledger_path(package_root, env=env, version="rc85")
    if replay_ledger_path.exists():
        replay_ledger_path.unlink()
    for name in (
        SUMMARY_JSON_NAME,
        SUMMARY_MD_NAME,
        "review_item_ledger_summary.json",
        "review_item_ledger_summary.md",
        "replay_ledger_summary.json",
        "replay_ledger_summary.md",
        "rollback_analysis_summary.json",
        "rollback_analysis_summary.md",
        "evidence_integrity_summary.json",
        "evidence_integrity_summary.md",
    ):
        target = artifact_root / name
        if target.exists():
            target.unlink()


def _persist_flow(
    *,
    adapter: MockExternalWorldAdapter,
    snapshot: Any,
    proposal: Any,
    result: ExternalActionResult,
    package_root: Path,
    env: dict[str, str],
    checkpoint_ref: str,
    prior_stable_state_ref: str,
    review_reasons: list[str],
    evidence_integrity_status: str = "clean",
    create_review_item_flag: bool = False,
    evidence_missing: bool = False,
    rollback_ambiguity: bool = False,
    fake_seed_values: dict[str, str],
) -> dict[str, Any]:
    review_state: dict[str, Any] = {
        "review_required": bool(review_reasons or result.review_required),
        "review_reasons": list(review_reasons or result.review_reasons),
        "checkpoint_ref": checkpoint_ref,
        "prior_stable_state_ref": prior_stable_state_ref,
        "evidence_integrity_status": evidence_integrity_status,
        "restore_allowed": False,
        "restore_performed": False,
    }
    replay_packet = adapter.emit_replay_packet(
        proposal,
        result,
        snapshot,
        review_state,
    )

    rollback_analysis = None
    rollback_path = None
    if replay_packet.rollback_candidate:
        rollback_analysis = adapter.request_rollback_analysis(replay_packet)
        rollback_analysis.checkpoint_ref = checkpoint_ref
        rollback_analysis.checkpoint_available = True
        rollback_analysis.prior_stable_state_ref = prior_stable_state_ref
        if rollback_ambiguity:
            rollback_analysis.ambiguity_level = "high"
            rollback_analysis.ambiguity_reasons = ["rollback ambiguity"]
            rollback_analysis.operator_action_required = True
        rollback_path = write_review_rollback_analysis(
            rollback_analysis,
            package_root=package_root,
            env=env,
        )
        replay_packet.rollback_analysis_id = rollback_analysis.rollback_analysis_id
        replay_packet.rollback_analysis_ref = f"rollback_analysis/{rollback_analysis.rollback_analysis_id}.json"
        emit_rollback_linkage(
            adapter.adapter_name,
            adapter.adapter_kind,
            action_type=proposal.action_type,
            ambiguity_level=rollback_analysis.ambiguity_level,
            proof_kind=adapter.proof_kind,
        )

    review_item = None
    review_path = None
    if create_review_item_flag:
        review_item = build_review_item(
            action_id=proposal.action_id,
            action_type=proposal.action_type,
            action_status=result.status,
            review_reasons=review_reasons or result.review_reasons,
            governing_directive_ref=proposal.governing_directive_ref,
            adapter_name=adapter.adapter_name,
            adapter_kind=adapter.adapter_kind,
            replay_packet_id=replay_packet.replay_packet_id,
            replay_packet_path_hint=f"replay_packets/{replay_packet.replay_packet_id}.json",
            rollback_analysis_id=(
                rollback_analysis.rollback_analysis_id if rollback_analysis is not None else None
            ),
            rollback_analysis_path_hint=(
                f"rollback_analysis/{rollback_analysis.rollback_analysis_id}.json"
                if rollback_analysis is not None
                else None
            ),
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            kill_switch_state=adapter.kill_switch_state,
            telemetry_trace_hint=replay_packet.telemetry_trace_hint,
            evidence_integrity_status=evidence_integrity_status,
            evidence_missing=evidence_missing,
        )
        review_path = write_review_item(review_item, package_root=package_root, env=env)
        replay_packet.review_item_id = review_item.review_item_id
        replay_packet.review_status = review_item.review_status
        replay_packet.escalation_status = review_item.escalation_status
        replay_packet.escalation_reasons = list(review_item.escalation_reasons)
        emit_review_item_created(
            adapter.adapter_name,
            adapter.adapter_kind,
            action_type=proposal.action_type,
            review_status=review_item.review_status,
            review_severity=review_item.severity,
            proof_kind=adapter.proof_kind,
        )
        emit_review_hold_summary(
            adapter.adapter_name,
            adapter.adapter_kind,
            review_status=review_item.review_status,
            proof_kind=adapter.proof_kind,
        )
        if "live external mutation requested in rc85" in list(review_item.review_reasons or []):
            emit_live_mutation_refused(
                adapter.adapter_name,
                adapter.adapter_kind,
                action_type=proposal.action_type,
                proof_kind=adapter.proof_kind,
            )

    replay_paths = write_replay_packet(
        replay_packet,
        package_root=package_root,
        env=env,
        version="rc85",
    )

    integrity = evaluate_evidence_integrity(
        replay_packet=replay_packet.to_dict(),
        rollback_analysis=rollback_analysis.to_dict() if rollback_analysis is not None else None,
        review_item=review_item.to_dict() if review_item is not None else None,
        required_paths=[
            replay_paths["packet_path"],
            *([rollback_path] if rollback_path else []),
            *([review_path] if review_path else []),
        ],
        fake_seeds=fake_seed_values.values(),
    )
    emit_evidence_integrity(
        adapter.adapter_name,
        adapter.adapter_kind,
        action_type=proposal.action_type,
        integrity_status=integrity.evidence_integrity_status,
        proof_kind=adapter.proof_kind,
    )

    return {
        "snapshot": snapshot.to_dict(),
        "proposal": proposal.to_dict(),
        "result": result.to_dict(),
        "replay_packet": replay_packet.to_dict(),
        "replay_packet_path": replay_paths["packet_path"],
        "rollback_analysis": rollback_analysis.to_dict() if rollback_analysis is not None else None,
        "rollback_analysis_path": rollback_path,
        "review_item": review_item.to_dict() if review_item is not None else None,
        "review_item_path": review_path,
        "integrity": integrity.to_dict(),
    }


def _shell_snapshot(service: OperatorWebService) -> dict[str, Any]:
    return service.current_shell_state_payload()


def _summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# rc85 Review Hold and Rollback Integration Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Proof id: {summary.get('proof_id', '<none>')}",
            f"- Adapter status: {summary.get('adapter_status', '<none>')}",
            f"- Review item count: {summary.get('review_item_count', 0)}",
            f"- Replay packet count: {summary.get('replay_packet_count', 0)}",
            f"- Rollback analysis count: {summary.get('rollback_analysis_count', 0)}",
            f"- Last review item id: {summary.get('last_review_item_id', '<none>')}",
            f"- Last replay packet id: {summary.get('last_replay_packet_id', '<none>')}",
            f"- Last rollback analysis id: {summary.get('last_rollback_analysis_id', '<none>')}",
            f"- Redaction proof passed: {summary.get('redaction_proof_passed', False)}",
            f"- No secrets captured: {summary.get('no_secrets_captured', False)}",
        ]
    )


def run_review_rollback_integration_proof(
    *,
    package_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root = (package_root or ROOT).resolve()
    env = dict(env or os.environ)
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    artifact_root.mkdir(parents=True, exist_ok=True)
    _clear_existing_artifacts(package_root=package_root, env=env)
    fake_seed_values = _fake_seeds()
    proof_id = _proof_id()
    checkpoint_ref = f"mock-checkpoint-rc85-{uuid.uuid4().hex[:8]}"
    prior_stable_state_ref = f"mock-stable-state-rc85-{uuid.uuid4().hex[:8]}"

    disabled_env = {**env, "NOVALI_OTEL_ENABLED": "false"}
    enabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or "novalioperatorshell"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": str(
            env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"
        ),
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict"),
        "RC85_PROOF_ARTIFACT_ROOT": str(artifact_root),
    }

    disabled_status = initialize_observability(load_observability_config(disabled_env))
    shutdown_observability()
    enabled_status_before = initialize_observability(load_observability_config(enabled_env))

    adapter = MockExternalWorldAdapter(proof_kind="review_rollback_integration_proof")
    context = AdapterContext(
        source_controller="novali_controller",
        governing_directive_ref="mock.directive.rc85",
        proof_kind="review_rollback_integration_proof",
        telemetry_trace_hint=proof_id,
    )

    integrity_results: list[dict[str, Any]] = []
    flow_records: dict[str, Any] = {}

    with adapter_span(
        "novali.external_adapter.rc85_proof.run",
        adapter_name=adapter.adapter_name,
        adapter_kind=adapter.adapter_kind,
        result="success",
        proof_kind="review_rollback_integration_proof",
    ):
        success_snapshot = adapter.get_world_snapshot(context)
        success_proposal = adapter.propose_action(
            success_snapshot,
            {
                "action_type": "noop.simulate_success",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Demonstrate the rc85 review/rollback success path.",
                "arguments": {
                    "authorization": fake_seed_values["authorization"],
                    "novali.secret": fake_seed_values["novali.secret"],
                    "api_key": fake_seed_values["api_key"],
                    "cookie": fake_seed_values["cookie"],
                    "external_payload": fake_seed_values["external_payload"],
                    "rollback_context": fake_seed_values["rollback_context"],
                    "OTEL_EXPORTER_OTLP_HEADERS": fake_seed_values["OTEL_EXPORTER_OTLP_HEADERS"],
                },
            },
        )
        success_validation = adapter.validate_preconditions(success_proposal, success_snapshot)
        success_result = adapter.execute_bounded_action(success_proposal)
        success_ack = adapter.acknowledge_result(success_proposal.action_id, success_result)
        flow_records["success"] = _persist_flow(
            adapter=adapter,
            snapshot=success_snapshot,
            proposal=success_proposal,
            result=success_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=list(success_validation.review_requirement.review_reasons),
            evidence_integrity_status="clean",
            fake_seed_values=fake_seed_values,
        )
        flow_records["success"]["validation"] = success_validation.to_dict()
        flow_records["success"]["acknowledgement"] = success_ack
        integrity_results.append(flow_records["success"]["integrity"])

        unknown_snapshot = adapter.get_world_snapshot(context)
        unknown_proposal = adapter.propose_action(
            unknown_snapshot,
            {
                "action_type": "noop.unknown_future_action",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Trigger a mock review hold for an unknown action.",
            },
        )
        unknown_validation = adapter.validate_preconditions(unknown_proposal, unknown_snapshot)
        unknown_result = _review_only_result(
            proposal=unknown_proposal,
            status="review_required",
            summary="Unknown action type requires explicit rc85 review.",
            review_reasons=list(unknown_validation.review_requirement.review_reasons),
        )
        flow_records["unknown_action"] = _persist_flow(
            adapter=adapter,
            snapshot=unknown_snapshot,
            proposal=unknown_proposal,
            result=unknown_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=list(unknown_validation.review_requirement.review_reasons),
            evidence_integrity_status="clean",
            create_review_item_flag=True,
            fake_seed_values=fake_seed_values,
        )
        flow_records["unknown_action"]["validation"] = unknown_validation.to_dict()
        integrity_results.append(flow_records["unknown_action"]["integrity"])

        precondition_snapshot = adapter.get_world_snapshot(context)
        precondition_proposal = adapter.propose_action(
            precondition_snapshot,
            {
                "action_type": "noop.annotate",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Trigger a failed precondition review path.",
            },
        )
        precondition_validation = adapter.validate_preconditions(precondition_proposal, precondition_snapshot)
        precondition_result = _review_only_result(
            proposal=precondition_proposal,
            status="precondition_failed",
            summary="Failed preconditions require explicit rc85 review.",
            review_reasons=list(precondition_validation.review_requirement.review_reasons),
        )
        flow_records["failed_precondition"] = _persist_flow(
            adapter=adapter,
            snapshot=precondition_snapshot,
            proposal=precondition_proposal,
            result=precondition_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=list(precondition_validation.review_requirement.review_reasons),
            evidence_integrity_status="clean",
            create_review_item_flag=True,
            fake_seed_values=fake_seed_values,
        )
        flow_records["failed_precondition"]["validation"] = precondition_validation.to_dict()
        integrity_results.append(flow_records["failed_precondition"]["integrity"])

        uncertain_records: list[dict[str, Any]] = []
        for index in range(2):
            uncertain_snapshot = adapter.get_world_snapshot(context)
            uncertain_proposal = adapter.propose_action(
                uncertain_snapshot,
                {
                    "action_type": "noop.simulate_uncertain",
                    "source_controller": context.source_controller,
                    "governing_directive_ref": context.governing_directive_ref,
                    "intended_effect": f"Simulate uncertain outcome {index + 1}.",
                },
            )
            uncertain_validation = adapter.validate_preconditions(uncertain_proposal, uncertain_snapshot)
            uncertain_result = adapter.execute_bounded_action(uncertain_proposal)
            review_reasons = ["repeated uncertain outcomes"] if index == 1 else list(
                uncertain_validation.review_requirement.review_reasons or uncertain_result.review_reasons
            )
            uncertain_record = _persist_flow(
                adapter=adapter,
                snapshot=uncertain_snapshot,
                proposal=uncertain_proposal,
                result=uncertain_result,
                package_root=package_root,
                env=env,
                checkpoint_ref=checkpoint_ref,
                prior_stable_state_ref=prior_stable_state_ref,
                review_reasons=review_reasons,
                evidence_integrity_status="clean",
                create_review_item_flag=index == 1,
                fake_seed_values=fake_seed_values,
            )
            uncertain_record["validation"] = uncertain_validation.to_dict()
            uncertain_records.append(uncertain_record)
            integrity_results.append(uncertain_record["integrity"])
        flow_records["repeated_uncertainty"] = uncertain_records

        missing_replay_requirement = classify_action_request(
            "noop.observe",
            missing_replay_packet=True,
        )
        missing_replay_review = build_review_item(
            action_id=f"action-missing-replay-{uuid.uuid4().hex[:6]}",
            action_type="noop.observe",
            action_status="review_required",
            review_reasons=list(missing_replay_requirement.review_reasons),
            governing_directive_ref=context.governing_directive_ref,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            evidence_integrity_status="failed",
            evidence_missing=True,
        )
        missing_replay_path = write_review_item(
            missing_replay_review,
            package_root=package_root,
            env=env,
        )
        emit_review_item_created(
            adapter.adapter_name,
            adapter.adapter_kind,
            action_type=missing_replay_review.action_type,
            review_status=missing_replay_review.review_status,
            review_severity=missing_replay_review.severity,
            proof_kind=adapter.proof_kind,
        )
        missing_replay_integrity = evaluate_evidence_integrity(
            replay_packet=None,
            rollback_analysis=None,
            review_item=missing_replay_review.to_dict(),
            required_paths=[missing_replay_path],
            fake_seeds=fake_seed_values.values(),
        )
        emit_evidence_integrity(
            adapter.adapter_name,
            adapter.adapter_kind,
            action_type=missing_replay_review.action_type,
            integrity_status=missing_replay_integrity.evidence_integrity_status,
            proof_kind=adapter.proof_kind,
        )
        emit_review_hold_summary(
            adapter.adapter_name,
            adapter.adapter_kind,
            review_status=missing_replay_review.review_status,
            proof_kind=adapter.proof_kind,
        )
        flow_records["missing_replay_packet"] = {
            "review_item": missing_replay_review.to_dict(),
            "review_item_path": missing_replay_path,
            "integrity": missing_replay_integrity.to_dict(),
        }
        integrity_results.append(flow_records["missing_replay_packet"]["integrity"])

        ambiguity_snapshot = adapter.get_world_snapshot(context)
        ambiguity_proposal = adapter.propose_action(
            ambiguity_snapshot,
            {
                "action_type": "noop.simulate_failure",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Exercise rollback ambiguity evidence.",
            },
        )
        ambiguity_validation = adapter.validate_preconditions(ambiguity_proposal, ambiguity_snapshot)
        ambiguity_result = adapter.execute_bounded_action(ambiguity_proposal)
        flow_records["rollback_ambiguity"] = _persist_flow(
            adapter=adapter,
            snapshot=ambiguity_snapshot,
            proposal=ambiguity_proposal,
            result=ambiguity_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=["rollback ambiguity"],
            evidence_integrity_status="clean",
            create_review_item_flag=True,
            rollback_ambiguity=True,
            fake_seed_values=fake_seed_values,
        )
        flow_records["rollback_ambiguity"]["validation"] = ambiguity_validation.to_dict()
        integrity_results.append(flow_records["rollback_ambiguity"]["integrity"])

        live_mutation_snapshot = adapter.get_world_snapshot(context)
        live_mutation_proposal = adapter.propose_action(
            live_mutation_snapshot,
            {
                "action_type": "real.network_action",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Attempt a forbidden live external mutation.",
            },
        )
        live_mutation_validation = adapter.validate_preconditions(
            live_mutation_proposal,
            live_mutation_snapshot,
        )
        live_mutation_result = _review_only_result(
            proposal=live_mutation_proposal,
            status="review_required",
            summary="Live external mutation requests are refused in rc85.",
            review_reasons=list(live_mutation_validation.review_requirement.review_reasons),
            failure_reason="mock-only membrane refused live mutation",
        )
        flow_records["live_mutation_refused"] = _persist_flow(
            adapter=adapter,
            snapshot=live_mutation_snapshot,
            proposal=live_mutation_proposal,
            result=live_mutation_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=list(live_mutation_validation.review_requirement.review_reasons),
            evidence_integrity_status="clean",
            create_review_item_flag=True,
            fake_seed_values=fake_seed_values,
        )
        flow_records["live_mutation_refused"]["validation"] = live_mutation_validation.to_dict()
        integrity_results.append(flow_records["live_mutation_refused"]["integrity"])

        kill_snapshot = adapter.get_world_snapshot(context)
        kill_proposal = adapter.propose_action(
            kill_snapshot,
            {
                "action_type": "noop.kill_switch_test",
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": "Trigger the rc85 mock-only kill switch.",
            },
        )
        kill_validation = adapter.validate_preconditions(kill_proposal, kill_snapshot)
        kill_result = adapter.execute_bounded_action(kill_proposal)
        kill_ack = adapter.acknowledge_result(kill_proposal.action_id, kill_result)
        flow_records["kill_switch"] = _persist_flow(
            adapter=adapter,
            snapshot=kill_snapshot,
            proposal=kill_proposal,
            result=kill_result,
            package_root=package_root,
            env=env,
            checkpoint_ref=checkpoint_ref,
            prior_stable_state_ref=prior_stable_state_ref,
            review_reasons=list(kill_validation.review_requirement.review_reasons or kill_result.review_reasons),
            evidence_integrity_status="clean",
            create_review_item_flag=True,
            fake_seed_values=fake_seed_values,
        )
        flow_records["kill_switch"]["validation"] = kill_validation.to_dict()
        flow_records["kill_switch"]["acknowledgement"] = kill_ack
        integrity_results.append(flow_records["kill_switch"]["integrity"])

        flush_result = flush_observability()
        enabled_status_after = get_observability_status()
    shutdown_observability()

    review_summary = summarize_review_items(package_root=package_root, env=env)
    replay_summary = summarize_replay_ledger(package_root=package_root, env=env, version="rc85")
    rollback_summary = summarize_rollback_analyses(package_root=package_root, env=env)
    evidence_summary = write_evidence_integrity_summary(
        integrity_results,
        package_root=package_root,
        env=env,
    )

    summary: dict[str, Any] = {
        "schema_name": "novali_rc85_review_rollback_integration_summary_v1",
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "schema_version": "rc85.v1",
        "result": "success",
        "adapter_enabled": True,
        "adapter_mode": "mock_only",
        "adapter_status": load_external_adapter_review_status(package_root=package_root, env=env).get("status", "pending_review"),
        "adapter_name": adapter.adapter_name,
        "adapter_kind": adapter.adapter_kind,
        "checkpoint_ref": checkpoint_ref,
        "prior_stable_state_ref": prior_stable_state_ref,
        "telemetry_disabled_status": disabled_status,
        "telemetry_enabled_status_before": enabled_status_before,
        "telemetry_enabled_status_after": enabled_status_after,
        "telemetry_flush_result": flush_result,
        "last_action_status": str(flow_records["kill_switch"]["result"]["status"]),
        "last_review_required": True,
        "review_reasons": list(flow_records["kill_switch"]["result"]["review_reasons"]),
        "last_review_item_id": review_summary.get("last_review_item_id"),
        "last_replay_packet_id": replay_summary.get("last_replay_packet_id"),
        "last_rollback_analysis_id": rollback_summary.get("last_rollback_analysis_id"),
        "review_item_count": review_summary.get("review_item_count", 0),
        "replay_packet_count": replay_summary.get("packet_count", 0),
        "rollback_analysis_count": rollback_summary.get("rollback_analysis_count", 0),
        "success_flow": flow_records["success"],
        "unknown_action_flow": flow_records["unknown_action"],
        "failed_precondition_flow": flow_records["failed_precondition"],
        "repeated_uncertainty_flow": flow_records["repeated_uncertainty"],
        "missing_replay_flow": flow_records["missing_replay_packet"],
        "rollback_ambiguity_flow": flow_records["rollback_ambiguity"],
        "live_mutation_flow": flow_records["live_mutation_refused"],
        "kill_switch_flow": flow_records["kill_switch"],
        "review_summary": review_summary,
        "replay_summary": replay_summary,
        "rollback_summary": rollback_summary,
        "evidence_integrity_summary": evidence_summary,
        "restore_allowed": False,
        "restore_performed": False,
    }

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=SUMMARY_JSON_NAME,
        markdown_name=SUMMARY_MD_NAME,
        summary=summary,
        markdown=_summary_markdown(summary),
    )

    service = OperatorWebService(
        package_root=package_root,
        operator_root=package_root / "operator_state",
        state_root=package_root / "runtime_data" / "state",
    )
    shell_payload = _shell_snapshot(service)
    summary["shell_status_checked"] = True
    summary["external_adapter_status"] = shell_payload.get("external_adapter", {})
    summary["external_adapter_review"] = shell_payload.get("external_adapter_review", {})

    replay_packet_paths = sorted((artifact_root / "replay_packets").glob("*.json"))
    review_item_paths = sorted((artifact_root / "review_items").glob("*.json"))
    rollback_paths = sorted((artifact_root / "rollback_analysis").glob("*.json"))
    replay_payloads = [Path(path).read_text(encoding="utf-8") for path in replay_packet_paths]
    review_payloads = [Path(path).read_text(encoding="utf-8") for path in review_item_paths]
    rollback_payloads = [Path(path).read_text(encoding="utf-8") for path in rollback_paths]
    replay_ledger_path = Path(str(replay_summary.get("replay_ledger_path", "")))
    replay_ledger_text = (
        replay_ledger_path.read_text(encoding="utf-8")
        if replay_ledger_path.exists()
        else ""
    )
    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(summary, sort_keys=True, default=str),
            replay_ledger_text,
            *replay_payloads,
            *review_payloads,
            *rollback_payloads,
            json.dumps(shell_payload, sort_keys=True, default=str),
        ],
        tuple(fake_seed_values.values()),
    )
    summary["redaction_proof_passed"] = not forbidden_hits
    summary["no_secrets_captured"] = not forbidden_hits
    if forbidden_hits:
        emit_redaction_failure(
            adapter.adapter_name,
            adapter.adapter_kind,
            proof_kind="review_rollback_integration_proof",
        )
        summary["result"] = "failure"
        summary["adapter_status"] = "failed"
        summary["forbidden_hits"] = forbidden_hits
        summary["review_reasons"] = ["redaction failure"]
        summary["last_review_required"] = True

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=SUMMARY_JSON_NAME,
        markdown_name=SUMMARY_MD_NAME,
        summary=summary,
        markdown=_summary_markdown(summary),
    )
    return summary


def main() -> int:
    summary = run_review_rollback_integration_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
