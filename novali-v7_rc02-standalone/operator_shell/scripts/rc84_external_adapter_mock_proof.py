from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.external_adapter import (
    AdapterContext,
    MockExternalWorldAdapter,
    load_external_adapter_status,
    resolve_rc84_artifact_root,
    resolve_replay_ledger_path,
    resolve_replay_packets_root,
    summarize_replay_ledger,
    write_replay_packet,
    write_rollback_analysis,
)
from operator_shell.external_adapter.schemas import ExternalActionResult
from operator_shell.external_adapter.status import EXTERNAL_ADAPTER_SUMMARY_NAME
from operator_shell.external_adapter.telemetry import adapter_span, emit_redaction_failure
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

def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC84_SHOULD_NOT_EXPORT"


FAKE_SEEDS = (
    _fake_seed("SECRET_TOKEN"),
    _fake_seed("NOVALI_SECRET"),
    _fake_seed("API_KEY"),
    _fake_seed("COOKIE"),
    _fake_seed("EXTERNAL_PAYLOAD_SECRET"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _review_only_result(
    *,
    proposal: Any,
    status: str,
    summary: str,
    review_reasons: list[str],
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
        review_required=True,
        review_reasons=list(review_reasons),
        mock_mutation_performed=False,
    )


def _shell_snapshot(service: OperatorWebService) -> dict[str, Any]:
    service.current_frontend_state_snapshot = lambda: {  # type: ignore[method-assign]
        "schema_name": "test_shell_state_v1",
        "intervention": {"required": False},
        "shell_runtime_signals": {
            "queue_items": 0,
            "deferred_items": 0,
            "pressure_band": "low",
            "review_status": "clear",
        },
    }
    return service.current_shell_state_payload()


def _exercise_success_flow(
    *,
    adapter: MockExternalWorldAdapter,
    context: AdapterContext,
    package_root: Path,
) -> dict[str, Any]:
    snapshot = adapter.get_world_snapshot(context)
    proposal = adapter.propose_action(
        snapshot,
        {
            "action_type": "noop.simulate_success",
            "source_controller": context.source_controller,
            "governing_directive_ref": context.governing_directive_ref,
            "intended_effect": "Demonstrate the rc84 mock adapter success path.",
            "arguments": {
                "authorization": f"Bearer {_fake_seed('SECRET_TOKEN')}",
                "novali.secret": _fake_seed("NOVALI_SECRET"),
                "api_key": _fake_seed("API_KEY"),
                "cookie": _fake_seed("COOKIE"),
                "external_payload": _fake_seed("EXTERNAL_PAYLOAD_SECRET"),
            },
        },
    )
    validation = adapter.validate_preconditions(proposal, snapshot)
    result = adapter.execute_bounded_action(proposal)
    acknowledgement = adapter.acknowledge_result(proposal.action_id, result)
    replay_packet = adapter.emit_replay_packet(
        proposal,
        result,
        snapshot,
        {
            "review_required": validation.review_requirement.review_required,
            "review_reasons": validation.review_requirement.review_reasons,
        },
    )
    replay_paths = write_replay_packet(replay_packet, package_root=package_root)
    rollback_analysis = adapter.request_rollback_analysis(replay_packet)
    rollback_path = write_rollback_analysis(rollback_analysis, package_root=package_root)
    return {
        "snapshot": snapshot.to_dict(),
        "proposal": proposal.to_dict(),
        "validation": validation.to_dict(),
        "result": result.to_dict(),
        "acknowledgement": acknowledgement,
        "replay_packet": replay_packet.to_dict(),
        "replay_packet_path": replay_paths["packet_path"],
        "replay_ledger_path": replay_paths["ledger_path"],
        "rollback_analysis": rollback_analysis.to_dict(),
        "rollback_analysis_path": rollback_path,
    }


def _exercise_review_and_failure_flows(
    *,
    adapter: MockExternalWorldAdapter,
    context: AdapterContext,
    package_root: Path,
) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []

    def record_flow(snapshot: Any, proposal: Any, result: ExternalActionResult, review_reasons: list[str]) -> None:
        replay_packet = adapter.emit_replay_packet(
            proposal,
            result,
            snapshot,
            {
                "review_required": result.review_required,
                "review_reasons": review_reasons,
            },
        )
        replay_paths = write_replay_packet(replay_packet, package_root=package_root)
        rollback_analysis = adapter.request_rollback_analysis(replay_packet)
        rollback_path = write_rollback_analysis(rollback_analysis, package_root=package_root)
        flows.append(
            {
                "proposal": proposal.to_dict(),
                "result": result.to_dict(),
                "replay_packet": replay_packet.to_dict(),
                "replay_packet_path": replay_paths["packet_path"],
                "rollback_analysis": rollback_analysis.to_dict(),
                "rollback_analysis_path": rollback_path,
            }
        )

    snapshot = adapter.get_world_snapshot(context)
    unknown_proposal = adapter.propose_action(
        snapshot,
        {
            "action_type": "noop.unknown_future_action",
            "source_controller": context.source_controller,
            "governing_directive_ref": context.governing_directive_ref,
            "intended_effect": "Trigger review for an unknown action type.",
        },
    )
    unknown_validation = adapter.validate_preconditions(unknown_proposal, snapshot)
    unknown_result = _review_only_result(
        proposal=unknown_proposal,
        status="review_required",
        summary="Unknown action type requires explicit review in rc84.",
        review_reasons=list(unknown_validation.review_requirement.review_reasons),
    )
    record_flow(snapshot, unknown_proposal, unknown_result, list(unknown_validation.review_requirement.review_reasons))

    precondition_snapshot = adapter.get_world_snapshot(context)
    precondition_proposal = adapter.propose_action(
        precondition_snapshot,
        {
            "action_type": "noop.annotate",
            "source_controller": context.source_controller,
            "governing_directive_ref": context.governing_directive_ref,
            "intended_effect": "Trigger a failed-precondition review path.",
        },
    )
    precondition_validation = adapter.validate_preconditions(precondition_proposal, precondition_snapshot)
    precondition_result = _review_only_result(
        proposal=precondition_proposal,
        status="precondition_failed",
        summary="Failed preconditions require explicit review before mock execution.",
        review_reasons=list(precondition_validation.review_requirement.review_reasons),
    )
    record_flow(
        precondition_snapshot,
        precondition_proposal,
        precondition_result,
        list(precondition_validation.review_requirement.review_reasons),
    )

    for action_type in ("noop.simulate_failure", "noop.simulate_uncertain", "noop.simulate_uncertain"):
        action_snapshot = adapter.get_world_snapshot(context)
        proposal = adapter.propose_action(
            action_snapshot,
            {
                "action_type": action_type,
                "source_controller": context.source_controller,
                "governing_directive_ref": context.governing_directive_ref,
                "intended_effect": f"Exercise the {action_type} mock outcome path.",
            },
        )
        validation = adapter.validate_preconditions(proposal, action_snapshot)
        if validation.valid:
            result = adapter.execute_bounded_action(proposal)
        else:
            result = _review_only_result(
                proposal=proposal,
                status="review_required",
                summary="Repeated uncertain outcomes now require explicit review.",
                review_reasons=list(validation.review_requirement.review_reasons),
            )
        record_flow(
            action_snapshot,
            proposal,
            result,
            list(validation.review_requirement.review_reasons or result.review_reasons),
        )

    kill_snapshot = adapter.get_world_snapshot(context)
    kill_proposal = adapter.propose_action(
        kill_snapshot,
        {
            "action_type": "noop.kill_switch_test",
            "source_controller": context.source_controller,
            "governing_directive_ref": context.governing_directive_ref,
            "intended_effect": "Trigger the rc84 mock-only kill switch.",
        },
    )
    kill_validation = adapter.validate_preconditions(kill_proposal, kill_snapshot)
    kill_result = adapter.execute_bounded_action(kill_proposal)
    adapter.acknowledge_result(kill_proposal.action_id, kill_result)
    record_flow(
        kill_snapshot,
        kill_proposal,
        kill_result,
        list(kill_validation.review_requirement.review_reasons or kill_result.review_reasons),
    )

    return flows


def run_external_adapter_mock_proof(
    *,
    package_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root = (package_root or ROOT).resolve()
    env = dict(env or os.environ)
    artifact_root = resolve_rc84_artifact_root(package_root, env=env)
    artifact_root.mkdir(parents=True, exist_ok=True)
    replay_packets_root = resolve_replay_packets_root(package_root, env=env)
    if replay_packets_root.exists():
        for path in replay_packets_root.glob("*"):
            if path.is_file():
                path.unlink()
    replay_ledger_path = resolve_replay_ledger_path(package_root, env=env)
    if replay_ledger_path.exists():
        replay_ledger_path.unlink()

    disabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "false",
    }
    enabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or "novalioperatorshell"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": str(env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"),
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict"),
    }

    disabled_status = initialize_observability(load_observability_config(disabled_env))
    shutdown_observability()

    enabled_status_before = initialize_observability(load_observability_config(enabled_env))
    adapter = MockExternalWorldAdapter(proof_kind="external_adapter_mock_proof")
    context = AdapterContext(
        source_controller="novali_controller",
        governing_directive_ref="mock.directive.rc84",
        proof_kind="external_adapter_mock_proof",
        telemetry_trace_hint="rc84.mock_adapter.proof",
    )

    with adapter_span(
        "novali.external_adapter.proof.run",
        adapter_name=adapter.adapter_name,
        adapter_kind=adapter.adapter_kind,
        result="success",
        proof_kind="external_adapter_mock_proof",
    ):
        success_flow = _exercise_success_flow(
            adapter=adapter,
            context=context,
            package_root=package_root,
        )
        additional_flows = _exercise_review_and_failure_flows(
            adapter=adapter,
            context=context,
            package_root=package_root,
        )
        flush_result = flush_observability()
        enabled_status_after = get_observability_status()
    shutdown_observability()

    replay_summary = summarize_replay_ledger(package_root=package_root, env=env)

    summary: dict[str, Any] = {
        "schema_name": "novali_rc84_external_adapter_mock_proof_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "schema_version": "rc84.v1",
        "adapter_enabled": True,
        "adapter_mode": "mock_only",
        "adapter_status": "kill_switch_triggered" if adapter.kill_switch_state == "triggered" else "ready",
        "adapter_name": adapter.adapter_name,
        "adapter_kind": adapter.adapter_kind,
        "telemetry_disabled_status": disabled_status,
        "telemetry_enabled_status_before": enabled_status_before,
        "telemetry_enabled_status_after": enabled_status_after,
        "telemetry_flush_result": flush_result,
        "last_action_status": str(additional_flows[-1]["result"]["status"] if additional_flows else success_flow["result"]["status"]),
        "last_review_required": bool(additional_flows[-1]["result"]["review_required"] if additional_flows else False),
        "review_reasons": list(additional_flows[-1]["result"]["review_reasons"] if additional_flows else []),
        "last_replay_packet_id": replay_summary.get("last_replay_packet_id"),
        "replay_packet_count": replay_summary.get("packet_count", 0),
        "kill_switch_state": adapter.kill_switch_state,
        "success_flow": success_flow,
        "additional_flows": additional_flows,
        "replay_summary": replay_summary,
    }

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=EXTERNAL_ADAPTER_SUMMARY_NAME,
        markdown_name="external_adapter_mock_proof_summary.md",
        summary=summary,
        markdown="\n".join(
            [
                "# rc84 External Adapter Mock Proof Summary",
                "",
                f"- Result: {summary['result']}",
                f"- Adapter: {summary['adapter_name']} ({summary['adapter_kind']})",
                f"- Mode: {summary['adapter_mode']}",
                f"- Adapter status: {summary['adapter_status']}",
                f"- Last action status: {summary['last_action_status']}",
                f"- Last review required: {summary['last_review_required']}",
                f"- Replay packet count: {summary['replay_packet_count']}",
                f"- Last replay packet id: {summary['last_replay_packet_id'] or '<none>'}",
                f"- Kill switch state: {summary['kill_switch_state']}",
            ]
        ),
    )

    service = OperatorWebService(
        package_root=package_root,
        operator_root=package_root / "operator_state",
        state_root=package_root / "runtime_data" / "state",
    )
    shell_payload = _shell_snapshot(service)
    external_adapter_status = shell_payload.get("external_adapter", {})
    summary["shell_status_checked"] = True
    summary["external_adapter_status"] = external_adapter_status

    replay_packet_paths = sorted((artifact_root / "replay_packets").glob("*.json"))
    replay_payloads = [
        Path(path).read_text(encoding="utf-8")
        for path in replay_packet_paths
    ]
    ledger_path = Path(str(replay_summary.get("replay_ledger_path", "")))
    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(summary, sort_keys=True, default=str),
            ledger_text,
            *replay_payloads,
            json.dumps(shell_payload, sort_keys=True, default=str),
        ],
        FAKE_SEEDS,
    )
    summary["redaction_proof_passed"] = not forbidden_hits
    summary["no_secrets_captured"] = not forbidden_hits
    if forbidden_hits:
        emit_redaction_failure(adapter.adapter_name, adapter.adapter_kind, proof_kind="external_adapter_mock_proof")
        summary["result"] = "failure"
        summary["adapter_status"] = "failed"
        summary["forbidden_hits"] = forbidden_hits
        summary["review_reasons"] = ["redaction failure"]
        summary["last_review_required"] = True

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=EXTERNAL_ADAPTER_SUMMARY_NAME,
        markdown_name="external_adapter_mock_proof_summary.md",
        summary=summary,
        markdown="\n".join(
            [
                "# rc84 External Adapter Mock Proof Summary",
                "",
                f"- Result: {summary['result']}",
                f"- Adapter: {summary['adapter_name']} ({summary['adapter_kind']})",
                f"- Mode: {summary['adapter_mode']}",
                f"- Adapter status: {summary['adapter_status']}",
                f"- Last action status: {summary['last_action_status']}",
                f"- Last review required: {summary['last_review_required']}",
                f"- Replay packet count: {summary['replay_packet_count']}",
                f"- Last replay packet id: {summary['last_replay_packet_id'] or '<none>'}",
                f"- Kill switch state: {summary['kill_switch_state']}",
                f"- Redaction proof passed: {summary['redaction_proof_passed']}",
                f"- No secrets captured: {summary['no_secrets_captured']}",
            ]
        ),
    )
    return summary


def main() -> int:
    summary = run_external_adapter_mock_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
