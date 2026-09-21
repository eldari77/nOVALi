from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.controller_isolation import (
    append_lane_intervention_entry,
    append_lane_replay_review_binding,
    build_default_lane_registry,
    ensure_lane_namespace,
    evaluate_cross_lane_message,
    write_lane_registry,
)
from operator_shell.external_adapter import (
    StaticFixtureReadOnlyAdapter,
    build_read_only_review_ticket,
    build_review_context,
    emit_conflict_detected,
    emit_integrity_result,
    emit_lane_attribution_result,
    emit_mutation_refused,
    emit_read_only_proof_completed,
    emit_read_only_replay_written,
    emit_read_only_review_ticket_created,
    emit_rollback_analysis_created,
    emit_schema_validated,
    emit_snapshot_loaded,
    emit_stale_snapshot_detected,
    hash_file,
    read_only_span,
    resolve_mutation_refusals_root,
    resolve_observation_replay_ledger_path,
    resolve_observation_replay_packets_root,
    resolve_rc87_artifact_root,
    resolve_read_only_review_tickets_root,
    resolve_rollback_analyses_root,
    snapshot_from_payload,
    summarize_mutation_refusals,
    summarize_observation_replay,
    summarize_read_only_rollback_analyses,
    summarize_read_only_review_tickets,
    write_mutation_refusal,
    write_observation_replay_packet,
    write_read_only_review_ticket,
    write_read_only_rollback_analysis,
)
from operator_shell.observability import (
    flush_observability,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    shutdown_observability,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts
from operator_shell.web_operator import OperatorWebService

SUMMARY_JSON_NAME = "read_only_adapter_sandbox_summary.json"
SUMMARY_MD_NAME = "read_only_adapter_sandbox_summary.md"
VALIDATION_JSON_NAME = "observation_validation_summary.json"
VALIDATION_MD_NAME = "observation_validation_summary.md"
LANE_JSON_NAME = "lane_attribution_summary.json"
LANE_MD_NAME = "lane_attribution_summary.md"
IMMUTABILITY_JSON_NAME = "source_immutability_summary.json"
IMMUTABILITY_MD_NAME = "source_immutability_summary.md"
TELEMETRY_JSON_NAME = "telemetry_identity_summary.json"
TELEMETRY_MD_NAME = "telemetry_identity_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"rc87-read-only-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "RC87", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "observation_note": _fake_seed("observation", "secret"),
        "fixture_payload": _fake_seed("fixture", "payload", "secret"),
        "rollback_note": _fake_seed("rollback", "secret"),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _clear_existing_artifacts(*, package_root: Path, env: dict[str, str]) -> None:
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    for root in (
        resolve_observation_replay_packets_root(package_root, env=env),
        resolve_read_only_review_tickets_root(package_root, env=env),
        resolve_rollback_analyses_root(package_root, env=env),
        resolve_mutation_refusals_root(package_root, env=env),
    ):
        if root.exists():
            shutil.rmtree(root)
    replay_ledger_path = resolve_observation_replay_ledger_path(package_root, env=env)
    if replay_ledger_path.exists():
        replay_ledger_path.unlink()


def _lane_map(package_root: Path) -> dict[str, Any]:
    registry = build_default_lane_registry(package_root)
    write_lane_registry(package_root, registry)
    for lane in registry.lanes:
        ensure_lane_namespace(package_root, lane)
    return {lane.lane_id: lane for lane in registry.lanes}


def _shell_snapshot(package_root: Path) -> dict[str, Any]:
    (package_root / "operator_state").mkdir(parents=True, exist_ok=True)
    (package_root / "runtime_data" / "state").mkdir(parents=True, exist_ok=True)
    service = OperatorWebService(
        package_root=package_root,
        operator_root=package_root / "operator_state",
        state_root=package_root / "runtime_data" / "state",
    )
    service.current_frontend_state_snapshot = lambda: {  # type: ignore[method-assign]
        "schema_name": "test_shell_state_v1",
        "operator_state": {"review_required": False, "intervention_required": False},
        "intervention": {
            "required": False,
            "queue_items": [],
            "pending_review_count": 0,
            "blocking_review_count": 0,
        },
        "shell_runtime_signals": {
            "queue_items": 0,
            "deferred_items": 0,
            "pressure_band": "low",
            "review_status": "clear",
        },
    }
    return service.current_shell_state_payload()


def _flow_action_id(snapshot_id: str, review_trigger: str) -> str:
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"{snapshot_id}|{review_trigger}").hex[:12]
    return f"read-only-action-{digest}"


def _flow_action_type(review_trigger: str, mutation_requested: bool) -> str:
    if mutation_requested:
        return "read_only.mutation_refusal"
    if review_trigger == "read_only_conflicting_observation":
        return "read_only.observe"
    if review_trigger.startswith("read_only_schema"):
        return "read_only.validate"
    return "read_only.observe"


def _build_review_ticket_if_needed(
    *,
    snapshot: Any,
    validation: Any,
    integrity: Any,
    replay_packet: Any,
    rollback_analysis: Any | None,
    review_trigger: str,
    adapter_context: Any,
) -> tuple[Any | None, str | None]:
    if not replay_packet.review_required:
        return None, None
    action_id = _flow_action_id(replay_packet.snapshot_id, review_trigger)
    action_type = _flow_action_type(review_trigger, bool(integrity.mutation_request_detected))
    action_status = "review_blocked" if review_trigger in {
        "read_only_mutation_requested",
        "read_only_forbidden_domain_term",
        "read_only_secret_detected",
    } else "review_required"
    context = build_review_context(
        review_trigger=review_trigger,
        review_reasons=list(dict.fromkeys(list(validation.review_reasons) + list(integrity.review_reasons))),
        lane_id=snapshot.lane_id or "lane_director",
        action_id=action_id,
        action_type=action_type,
        action_status=action_status,
        source_ref_hint=replay_packet.source_ref_hint,
        telemetry_trace_hint=adapter_context.telemetry_trace_hint,
    )
    review_ticket = build_read_only_review_ticket(
        context,
        governing_directive_ref=adapter_context.governing_directive_ref,
        replay_packet_id=replay_packet.replay_packet_id,
        replay_packet_path_hint=f"observation_replay_packets/{replay_packet.replay_packet_id}.json",
        rollback_analysis_id=(
            rollback_analysis.rollback_analysis_id if rollback_analysis is not None else None
        ),
        rollback_analysis_path_hint=(
            f"rollback_analyses/{rollback_analysis.rollback_analysis_id}.json"
            if rollback_analysis is not None
            else None
        ),
        checkpoint_ref=replay_packet.checkpoint_ref,
        prior_stable_state_ref=replay_packet.prior_snapshot_ref,
        evidence_integrity_status="clean",
        package_version="rc87",
    )
    return review_ticket, review_trigger


def _persist_observation_flow(
    *,
    adapter: StaticFixtureReadOnlyAdapter,
    package_root: Path,
    env: dict[str, str],
    lane_by_id: dict[str, Any],
    snapshot: Any,
    validation: Any,
    integrity: Any,
    review_trigger: str,
    prior_good_snapshot_ref: str | None,
    checkpoint_ref: str,
    telemetry_records: list[dict[str, Any]],
    mutation_refusal: Any | None = None,
    create_rollback: bool = False,
) -> dict[str, Any]:
    lane_id = snapshot.lane_id or "lane_director"
    lane = lane_by_id.get(lane_id) or lane_by_id["lane_director"]
    with read_only_span(
        "novali.read_only_adapter.observation.summarize",
        lane_id=lane.lane_id,
        lane_role=lane.lane_role,
        result="success",
        proof_kind=adapter.context.proof_kind,
    ) as summary_trace:
        telemetry_records.append(dict(summary_trace["attributes"]))
        observation_summary = adapter.summarize_observation(snapshot)

    replay_packet = adapter.emit_observation_replay(
        snapshot,
        validation,
        integrity,
        prior_snapshot_ref=prior_good_snapshot_ref,
        checkpoint_ref=checkpoint_ref,
        mutation_refusal=mutation_refusal,
    )

    rollback_analysis = None
    rollback_path = None
    if create_rollback:
        rollback_analysis = adapter.request_observation_rollback_analysis(
            replay_packet,
            prior_good_snapshot_ref,
        )
        rollback_path = write_read_only_rollback_analysis(
            rollback_analysis,
            package_root=package_root,
            env=env,
        )
        replay_packet.rollback_analysis_id = rollback_analysis.rollback_analysis_id
        emit_rollback_analysis_created(
            lane_id=lane.lane_id,
            result="success" if rollback_analysis.recovery_possible else "warning",
            proof_kind=adapter.context.proof_kind,
        )

    review_ticket = None
    review_path = None
    review_ticket, review_trigger_written = _build_review_ticket_if_needed(
        snapshot=snapshot,
        validation=validation,
        integrity=integrity,
        replay_packet=replay_packet,
        rollback_analysis=rollback_analysis,
        review_trigger=review_trigger,
        adapter_context=adapter.context,
    )
    if review_ticket is not None:
        review_path = write_read_only_review_ticket(
            review_ticket,
            package_root=package_root,
            env=env,
        )
        replay_packet.review_ticket_id = review_ticket.review_item_id
        emit_read_only_review_ticket_created(
            lane_id=lane.lane_id,
            review_trigger=review_trigger_written or review_trigger,
            review_status=review_ticket.review_status,
            proof_kind=adapter.context.proof_kind,
        )

    if mutation_refusal is not None:
        mutation_refusal.review_ticket_id = review_ticket.review_item_id if review_ticket is not None else None
        mutation_refusal.replay_packet_id = replay_packet.replay_packet_id
        write_mutation_refusal(
            mutation_refusal,
            package_root=package_root,
            env=env,
        )

    replay_paths = write_observation_replay_packet(
        replay_packet,
        package_root=package_root,
        env=env,
    )
    emit_read_only_replay_written(
        lane_id=lane.lane_id,
        validation_status=validation.validation_status,
        integrity_status=integrity.integrity_status,
        proof_kind=adapter.context.proof_kind,
    )

    append_lane_intervention_entry(
        package_root,
        lane,
        event_type=review_trigger,
        review_status=(review_ticket.review_status if review_ticket is not None else "clear"),
        summary=observation_summary,
    )
    append_lane_replay_review_binding(
        package_root,
        lane,
        binding_kind="read_only_observation_replay",
        artifact_id=replay_packet.replay_packet_id,
        artifact_path_hint=str(Path(replay_paths["packet_path"]).relative_to(package_root)),
        summary=observation_summary,
    )
    if review_ticket is not None:
        append_lane_replay_review_binding(
            package_root,
            lane,
            binding_kind="read_only_review_ticket",
            artifact_id=review_ticket.review_item_id,
            artifact_path_hint=str(Path(review_path).relative_to(package_root)),
            summary="Read-only adapter review ticket",
            review_binding=True,
        )

    snapshot_summary = {
        "snapshot_id": snapshot.snapshot_id,
        "lane_id": snapshot.lane_id or None,
        "source_kind": snapshot.source_kind,
        "source_name": snapshot.source_name,
        "source_ref_hint": replay_packet.source_ref_hint,
        "environment_kind": snapshot.environment_kind,
        "read_only": bool(snapshot.read_only),
        "mutation_allowed": bool(snapshot.mutation_allowed),
        "entity_count": len(list(snapshot.observed_entities or [])),
        "relationship_count": len(list(snapshot.observed_relationships or [])),
        "metric_count": len(list(snapshot.observed_metrics or [])),
    }
    return {
        "snapshot": snapshot_summary,
        "validation": validation.to_dict(),
        "integrity": integrity.to_dict(),
        "observation_summary": observation_summary,
        "replay_packet": replay_packet.to_dict(),
        "replay_packet_path": replay_paths["packet_path"],
        "rollback_analysis": rollback_analysis.to_dict() if rollback_analysis is not None else None,
        "rollback_analysis_path": rollback_path,
        "review_ticket": review_ticket.to_dict() if review_ticket is not None else None,
        "review_ticket_path": review_path,
        "mutation_refusal": mutation_refusal.to_dict() if mutation_refusal is not None else None,
    }


def _validation_summary(flows: dict[str, dict[str, Any]], artifact_root: Path) -> dict[str, Any]:
    validation_cases: list[dict[str, Any]] = []
    latest_validation_status = "unknown"
    latest_integrity_status = "unknown"
    latest_review_reasons: list[str] = []
    bad_snapshot_count = 0
    stale_snapshot_count = 0
    conflicting_observation_count = 0
    for name, flow in flows.items():
        validation = dict(flow.get("validation", {}))
        integrity = dict(flow.get("integrity", {}))
        review_reasons = list(dict.fromkeys(list(validation.get("review_reasons", [])) + list(integrity.get("review_reasons", []))))
        validation_cases.append(
            {
                "case_name": name,
                "snapshot_id": dict(flow.get("snapshot", {})).get("snapshot_id"),
                "validation_status": validation.get("validation_status", "unknown"),
                "integrity_status": integrity.get("integrity_status", "unknown"),
                "review_required": bool(validation.get("review_required", False) or integrity.get("review_required", False)),
                "review_reasons": review_reasons,
            }
        )
        latest_validation_status = str(validation.get("validation_status", latest_validation_status))
        latest_integrity_status = str(integrity.get("integrity_status", latest_integrity_status))
        latest_review_reasons = review_reasons or latest_review_reasons
        if str(validation.get("validation_status", "")) in {"failed", "review_required"} or str(integrity.get("integrity_status", "")) in {"failed", "review_required"}:
            bad_snapshot_count += 1
        if bool(validation.get("stale_snapshot", False)) or bool(integrity.get("stale_snapshot", False)):
            stale_snapshot_count += 1
        if bool(integrity.get("conflicting_observations", False)):
            conflicting_observation_count += 1
    summary = {
        "schema_name": "novali_rc87_observation_validation_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "case_count": len(validation_cases),
        "latest_validation_status": latest_validation_status,
        "latest_integrity_status": latest_integrity_status,
        "latest_review_reasons": latest_review_reasons,
        "bad_snapshot_count": bad_snapshot_count,
        "stale_snapshot_count": stale_snapshot_count,
        "conflicting_observation_count": conflicting_observation_count,
        "cases": validation_cases,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=VALIDATION_JSON_NAME,
        markdown_name=VALIDATION_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc87 Observation Validation Summary",
            [
                f"- Case count: {summary['case_count']}",
                f"- Bad snapshot count: {summary['bad_snapshot_count']}",
                f"- Stale snapshot count: {summary['stale_snapshot_count']}",
                f"- Conflicting observation count: {summary['conflicting_observation_count']}",
                f"- Latest validation status: {summary['latest_validation_status']}",
                f"- Latest integrity status: {summary['latest_integrity_status']}",
            ],
        ),
    )
    return summary


def _lane_summary(
    *,
    package_root: Path,
    artifact_root: Path,
    lane_flows: list[dict[str, Any]],
    direct_share_result: dict[str, Any],
) -> dict[str, Any]:
    unique_lanes = sorted(
        {
            str(dict(flow.get("snapshot", {})).get("lane_id", "")).strip()
            for flow in lane_flows
            if str(dict(flow.get("snapshot", {})).get("lane_id", "")).strip()
        }
    )
    latest = lane_flows[-1] if lane_flows else {}
    latest_snapshot = dict(latest.get("snapshot", {}))
    latest_integrity = dict(latest.get("integrity", {}))
    summary = {
        "schema_name": "novali_rc87_lane_attribution_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "lane_count": len(unique_lanes),
        "lanes_touched": unique_lanes,
        "latest_lane_id": str(latest_snapshot.get("lane_id", "")).strip() or None,
        "latest_lane_attribution_status": str(latest_integrity.get("lane_attribution_status", "unknown")).strip() or "unknown",
        "wrong_lane_count": sum(
            1
            for flow in lane_flows
            if str(dict(flow.get("integrity", {})).get("lane_attribution_status", "")).strip() == "wrong_lane"
        ),
        "direct_share_blocked": bool(direct_share_result.get("blocked", False)),
        "direct_share_status": str(direct_share_result.get("approval_status", "")).strip() or "unknown",
        "controller_isolation_data_root": str((package_root / "data" / "controller_isolation").resolve()),
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=LANE_JSON_NAME,
        markdown_name=LANE_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc87 Lane Attribution Summary",
            [
                f"- Lanes touched: {', '.join(summary['lanes_touched']) or '<none>'}",
                f"- Latest lane id: {summary['latest_lane_id'] or '<none>'}",
                f"- Latest lane attribution status: {summary['latest_lane_attribution_status']}",
                f"- Wrong-lane count: {summary['wrong_lane_count']}",
                f"- Direct sovereign share blocked: {'yes' if summary['direct_share_blocked'] else 'no'}",
            ],
        ),
    )
    return summary


def _source_immutability_summary(
    *,
    artifact_root: Path,
    fixture_hashes_before: dict[str, str],
    fixture_hashes_after: dict[str, str],
) -> dict[str, Any]:
    comparisons = []
    changed_paths: list[str] = []
    for path, before_hash in fixture_hashes_before.items():
        after_hash = fixture_hashes_after.get(path)
        unchanged = before_hash == after_hash
        comparisons.append(
            {
                "path_hint": Path(path).name,
                "before_sha256": before_hash,
                "after_sha256": after_hash,
                "unchanged": unchanged,
            }
        )
        if not unchanged:
            changed_paths.append(path)
    summary = {
        "schema_name": "novali_rc87_source_immutability_summary_v1",
        "generated_at": _now_iso(),
        "result": "success" if not changed_paths else "failure",
        "checked_fixture_count": len(comparisons),
        "changed_fixture_count": len(changed_paths),
        "changed_paths": [Path(path).name for path in changed_paths],
        "comparisons": comparisons,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=IMMUTABILITY_JSON_NAME,
        markdown_name=IMMUTABILITY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc87 Source Immutability Summary",
            [
                f"- Checked fixtures: {summary['checked_fixture_count']}",
                f"- Changed fixtures: {summary['changed_fixture_count']}",
            ],
        ),
    )
    return summary


def _telemetry_summary(artifact_root: Path, telemetry_records: list[dict[str, Any]]) -> dict[str, Any]:
    roleful_records = [
        record for record in telemetry_records if record.get("novali.controller.role")
    ]
    missing_lane_identity = [
        record
        for record in roleful_records
        if not record.get("novali.controller.lane")
    ]
    roleful_lane_ids = sorted(
        {
            str(record.get("novali.controller.lane", "")).strip()
            for record in roleful_records
            if str(record.get("novali.controller.lane", "")).strip()
        }
    )
    required_roleful_lanes = {"lane_director", "lane_sovereign_good"}
    summary = {
        "schema_name": "novali_rc87_telemetry_identity_summary_v1",
        "generated_at": _now_iso(),
        "result": (
            "success"
            if roleful_records
            and not missing_lane_identity
            and required_roleful_lanes.issubset(set(roleful_lane_ids))
            else "failure"
        ),
        "record_count": len(telemetry_records),
        "lane_identity_record_count": len(roleful_records),
        "missing_lane_identity_count": len(missing_lane_identity),
        "roleful_lane_ids": roleful_lane_ids,
        "records": telemetry_records,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=TELEMETRY_JSON_NAME,
        markdown_name=TELEMETRY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc87 Telemetry Identity Summary",
            [
                f"- Record count: {summary['record_count']}",
                f"- Lane identity record count: {summary['lane_identity_record_count']}",
                f"- Missing lane identity count: {summary['missing_lane_identity_count']}",
                f"- Roleful lane ids: {', '.join(summary['roleful_lane_ids']) or '<none>'}",
            ],
        ),
    )
    return summary


def run_read_only_adapter_sandbox_proof(
    *,
    package_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root = (package_root or ROOT).resolve()
    env = dict(env or os.environ)
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    _clear_existing_artifacts(package_root=package_root, env=env)
    artifact_root.mkdir(parents=True, exist_ok=True)
    fake_seed_values = _fake_seeds()
    proof_id = _proof_id()
    checkpoint_ref = f"mock-checkpoint-rc87-{uuid.uuid4().hex[:8]}"
    proof_kind = "read_only_adapter_sandbox_proof"

    disabled_env = {**env, "NOVALI_OTEL_ENABLED": "false"}
    enabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or "novalioperatorshell"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": str(env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"),
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict"),
        "RC87_PROOF_ARTIFACT_ROOT": str(artifact_root),
    }

    disabled_status = initialize_observability(load_observability_config(disabled_env))
    shutdown_observability()
    enabled_status_before = initialize_observability(load_observability_config(enabled_env))

    lane_by_id = _lane_map(package_root)
    adapter = StaticFixtureReadOnlyAdapter(package_root=package_root)
    telemetry_records: list[dict[str, Any]] = []
    flows: dict[str, dict[str, Any]] = {}
    fixture_root = package_root / "fixtures" / "read_only_world"

    fixture_hashes_before = {
        str(path.resolve()): hash_file(path)
        for path in (
            fixture_root / "generic_world_snapshot_valid.json",
            fixture_root / "generic_world_snapshot_mutation_request.json",
        )
    }

    prior_good_snapshot_ref: str | None = None
    direct_share_summary: dict[str, Any] = {"blocked": False, "approval_status": "not_attempted"}

    with read_only_span(
        "novali.read_only_adapter.rc87_proof.run",
        result="success",
        proof_kind=proof_kind,
    ):
        valid_path = fixture_root / "generic_world_snapshot_valid.json"
        valid_snapshot = adapter.load_snapshot(valid_path)
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=valid_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        valid_validation = adapter.validate_snapshot_schema(valid_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=valid_snapshot.lane_id or "lane_director",
                validation_status=valid_validation.validation_status,
                review_status="clear",
                proof_kind=proof_kind,
            )
        )
        valid_integrity = adapter.validate_observation_integrity(valid_snapshot, valid_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=valid_snapshot.lane_id or "lane_director",
                integrity_status=valid_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id=valid_snapshot.lane_id or "lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["valid_snapshot"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=valid_snapshot,
            validation=valid_validation,
            integrity=valid_integrity,
            review_trigger="read_only.observe",
            prior_good_snapshot_ref=None,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=False,
        )
        prior_good_snapshot_ref = valid_snapshot.snapshot_id

        missing_path = fixture_root / "generic_world_snapshot_missing_fields.json"
        missing_snapshot = adapter.load_snapshot(missing_path)
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=missing_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        missing_validation = adapter.validate_snapshot_schema(missing_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=missing_snapshot.lane_id or "lane_director",
                validation_status=missing_validation.validation_status,
                review_status="pending_review",
                proof_kind=proof_kind,
            )
        )
        missing_integrity = adapter.validate_observation_integrity(missing_snapshot, missing_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=missing_snapshot.lane_id or "lane_director",
                integrity_status=missing_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="failure",
                proof_kind=proof_kind,
            )
        )
        flows["missing_fields"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=missing_snapshot,
            validation=missing_validation,
            integrity=missing_integrity,
            review_trigger="read_only_schema_missing_field",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )

        conflict_path = fixture_root / "generic_world_snapshot_conflict.json"
        conflict_snapshot = adapter.load_snapshot(conflict_path)
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=conflict_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        conflict_validation = adapter.validate_snapshot_schema(conflict_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=conflict_snapshot.lane_id or "lane_director",
                validation_status=conflict_validation.validation_status,
                review_status="clear",
                proof_kind=proof_kind,
            )
        )
        conflict_integrity = adapter.validate_observation_integrity(conflict_snapshot, conflict_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=conflict_snapshot.lane_id or "lane_director",
                integrity_status=conflict_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(emit_conflict_detected(lane_id="lane_director", proof_kind=proof_kind))
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["conflicting_observations"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=conflict_snapshot,
            validation=conflict_validation,
            integrity=conflict_integrity,
            review_trigger="read_only_conflicting_observation",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )

        stale_path = fixture_root / "generic_world_snapshot_stale.json"
        stale_snapshot = adapter.load_snapshot(stale_path)
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=stale_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        stale_validation = adapter.validate_snapshot_schema(stale_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=stale_snapshot.lane_id or "lane_director",
                validation_status=stale_validation.validation_status,
                review_status="pending_review" if stale_validation.review_required else "clear",
                proof_kind=proof_kind,
            )
        )
        stale_integrity = adapter.validate_observation_integrity(stale_snapshot, stale_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=stale_snapshot.lane_id or "lane_director",
                integrity_status=stale_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(emit_stale_snapshot_detected(lane_id="lane_director", proof_kind=proof_kind))
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["stale_snapshot"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=stale_snapshot,
            validation=stale_validation,
            integrity=stale_integrity,
            review_trigger="read_only_stale_snapshot",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )

        mutation_path = fixture_root / "generic_world_snapshot_mutation_request.json"
        mutation_snapshot = adapter.load_snapshot(mutation_path)
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=mutation_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        mutation_validation = adapter.validate_snapshot_schema(mutation_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=mutation_snapshot.lane_id or "lane_director",
                validation_status=mutation_validation.validation_status,
                review_status="blocked",
                proof_kind=proof_kind,
            )
        )
        mutation_integrity = adapter.validate_observation_integrity(mutation_snapshot, mutation_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=mutation_snapshot.lane_id or "lane_director",
                integrity_status=mutation_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        mutation_refusal = adapter.refuse_mutation_request(
            {
                "request_id": f"mutation-request-{uuid.uuid4().hex[:8]}",
                "lane_id": mutation_snapshot.lane_id,
                "requested_operation": "write.update_entity_state",
            },
            "rc87 read-only adapter refused a mutation-bearing request from the static fixture path.",
        )
        telemetry_records.append(emit_mutation_refused(lane_id="lane_director", proof_kind=proof_kind))
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["mutation_refusal"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=mutation_snapshot,
            validation=mutation_validation,
            integrity=mutation_integrity,
            review_trigger="read_only_mutation_requested",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            mutation_refusal=mutation_refusal,
            create_rollback=True,
        )

        wrong_lane_payload = json.loads(valid_path.read_text(encoding="utf-8"))
        wrong_lane_payload["snapshot_id"] = "snapshot_wrong_lane"
        wrong_lane_payload["lane_id"] = "lane_sovereign_good"
        wrong_lane_payload["source_name"] = "warehouse_sandbox_wrong_lane"
        wrong_lane_payload["source_ref"] = "in_memory_wrong_lane"
        wrong_lane_snapshot = snapshot_from_payload(wrong_lane_payload, source_ref="in_memory_wrong_lane.json")
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=wrong_lane_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        wrong_lane_validation = adapter.validate_snapshot_schema(wrong_lane_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=wrong_lane_snapshot.lane_id or "lane_director",
                validation_status=wrong_lane_validation.validation_status,
                review_status="pending_review",
                proof_kind=proof_kind,
            )
        )
        wrong_lane_integrity = adapter.validate_observation_integrity(wrong_lane_snapshot, wrong_lane_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=wrong_lane_snapshot.lane_id or "lane_director",
                integrity_status=wrong_lane_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id=wrong_lane_snapshot.lane_id or "lane_director",
                lane_role=lane_by_id["lane_sovereign_good"].lane_role,
                result="failure",
                proof_kind=proof_kind,
            )
        )
        flows["wrong_lane_attribution"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=wrong_lane_snapshot,
            validation=wrong_lane_validation,
            integrity=wrong_lane_integrity,
            review_trigger="read_only_wrong_lane_attribution",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )
        blocked_envelope, _blocked_approval = evaluate_cross_lane_message(
            source_lane_id="lane_sovereign_good",
            target_lane_id="lane_sovereign_dark",
            message_type="status_summary",
            payload_summary="Attempted direct sovereign observation share without Director mediation.",
            allowed_scope="read_only_observation_reference",
            mediated_by_lane_id="lane_sovereign_good",
        )
        direct_share_summary = {
            "blocked": blocked_envelope.approval_status == "blocked",
            "approval_status": blocked_envelope.approval_status,
            "message_id": blocked_envelope.message_id,
            "review_reasons": blocked_envelope.review_reasons,
        }

        forbidden_payload = json.loads(valid_path.read_text(encoding="utf-8"))
        forbidden_payload["snapshot_id"] = "snapshot_forbidden_domain_term"
        forbidden_payload["notes_redacted"] = "Injected proof-only forbidden term: space engineers."
        forbidden_payload["source_name"] = "warehouse_sandbox_forbidden_term"
        forbidden_payload["source_ref"] = "in_memory_forbidden_term"
        forbidden_snapshot = snapshot_from_payload(forbidden_payload, source_ref="in_memory_forbidden_term.json")
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=forbidden_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        forbidden_validation = adapter.validate_snapshot_schema(forbidden_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=forbidden_snapshot.lane_id or "lane_director",
                validation_status=forbidden_validation.validation_status,
                review_status="blocked",
                proof_kind=proof_kind,
            )
        )
        forbidden_integrity = adapter.validate_observation_integrity(forbidden_snapshot, forbidden_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=forbidden_snapshot.lane_id or "lane_director",
                integrity_status=forbidden_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["forbidden_domain_term"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=forbidden_snapshot,
            validation=forbidden_validation,
            integrity=forbidden_integrity,
            review_trigger="read_only_forbidden_domain_term",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )

        secret_payload = json.loads(valid_path.read_text(encoding="utf-8"))
        secret_payload["snapshot_id"] = "snapshot_secret_detected"
        secret_payload["notes_redacted"] = fake_seed_values["observation_note"]
        secret_payload["observed_entities"][0]["attributes_redacted"]["fixture_payload"] = fake_seed_values["fixture_payload"]
        secret_payload["source_name"] = "warehouse_sandbox_secret_detected"
        secret_payload["source_ref"] = "in_memory_secret_detected"
        secret_snapshot = snapshot_from_payload(secret_payload, source_ref="in_memory_secret_detected.json")
        telemetry_records.append(
            emit_snapshot_loaded(
                lane_id=secret_snapshot.lane_id or "lane_director",
                result="success",
                proof_kind=proof_kind,
            )
        )
        secret_validation = adapter.validate_snapshot_schema(secret_snapshot)
        telemetry_records.append(
            emit_schema_validated(
                lane_id=secret_snapshot.lane_id or "lane_director",
                validation_status=secret_validation.validation_status,
                review_status="blocked",
                proof_kind=proof_kind,
            )
        )
        secret_integrity = adapter.validate_observation_integrity(secret_snapshot, secret_validation)
        telemetry_records.append(
            emit_integrity_result(
                lane_id=secret_snapshot.lane_id or "lane_director",
                integrity_status=secret_integrity.integrity_status,
                proof_kind=proof_kind,
            )
        )
        telemetry_records.append(
            emit_lane_attribution_result(
                lane_id="lane_director",
                lane_role=lane_by_id["lane_director"].lane_role,
                result="success",
                proof_kind=proof_kind,
            )
        )
        flows["secret_detected"] = _persist_observation_flow(
            adapter=adapter,
            package_root=package_root,
            env=env,
            lane_by_id=lane_by_id,
            snapshot=secret_snapshot,
            validation=secret_validation,
            integrity=secret_integrity,
            review_trigger="read_only_secret_detected",
            prior_good_snapshot_ref=prior_good_snapshot_ref,
            checkpoint_ref=checkpoint_ref,
            telemetry_records=telemetry_records,
            create_rollback=True,
        )

        flush_result = flush_observability()
        enabled_status_after = get_observability_status()
        telemetry_records.append(emit_read_only_proof_completed(result="success", proof_kind=proof_kind))
    shutdown_observability()

    fixture_hashes_after = {
        str(path.resolve()): hash_file(path)
        for path in (
            fixture_root / "generic_world_snapshot_valid.json",
            fixture_root / "generic_world_snapshot_mutation_request.json",
        )
    }

    replay_summary = summarize_observation_replay(package_root=package_root, env=env)
    review_summary = summarize_read_only_review_tickets(package_root=package_root, env=env)
    rollback_summary = summarize_read_only_rollback_analyses(package_root=package_root, env=env)
    mutation_summary = summarize_mutation_refusals(package_root=package_root, env=env)
    validation_summary = _validation_summary(flows, artifact_root)
    lane_summary = _lane_summary(
        package_root=package_root,
        artifact_root=artifact_root,
        lane_flows=[flows["valid_snapshot"], flows["wrong_lane_attribution"]],
        direct_share_result=direct_share_summary,
    )
    immutability_summary = _source_immutability_summary(
        artifact_root=artifact_root,
        fixture_hashes_before=fixture_hashes_before,
        fixture_hashes_after=fixture_hashes_after,
    )
    telemetry_summary = _telemetry_summary(artifact_root, telemetry_records)

    with tempfile.TemporaryDirectory() as tmp:
        blank_root = Path(tmp)
        blank_payload = _shell_snapshot(blank_root)

    shell_payload = _shell_snapshot(package_root)
    summary = {
        "schema_name": "novali_rc87_read_only_adapter_sandbox_summary_v1",
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "schema_version": "rc87.v1",
        "result": "success",
        "adapter_name": adapter.adapter_name,
        "adapter_kind": adapter.adapter_kind,
        "adapter_mode": "fixture_read_only",
        "adapter_status": "review_blocked",
        "review_required": True,
        "review_reasons": ["read_only_secret_detected", "read_only_mutation_requested"],
        "checkpoint_ref": checkpoint_ref,
        "prior_good_snapshot_ref": prior_good_snapshot_ref,
        "telemetry_disabled_status": disabled_status,
        "telemetry_enabled_status_before": enabled_status_before,
        "telemetry_enabled_status_after": enabled_status_after,
        "telemetry_flush_result": flush_result,
        "valid_snapshot_flow": flows["valid_snapshot"],
        "missing_fields_flow": flows["missing_fields"],
        "conflicting_observations_flow": flows["conflicting_observations"],
        "stale_snapshot_flow": flows["stale_snapshot"],
        "mutation_refusal_flow": flows["mutation_refusal"],
        "wrong_lane_attribution_flow": flows["wrong_lane_attribution"],
        "forbidden_domain_term_flow": flows["forbidden_domain_term"],
        "secret_detected_flow": flows["secret_detected"],
        "observation_replay_summary": replay_summary,
        "review_ticket_summary": review_summary,
        "rollback_analysis_summary": rollback_summary,
        "mutation_refusal_summary": mutation_summary,
        "observation_validation_summary": validation_summary,
        "lane_attribution_summary": lane_summary,
        "source_immutability_summary": immutability_summary,
        "telemetry_identity_summary": telemetry_summary,
        "shell_status_checked": True,
        "read_only_adapter_status": shell_payload.get("read_only_adapter", {}),
        "intervention_status": shell_payload.get("intervention", {}),
        "blank_state_checked": True,
        "blank_read_only_adapter_status": blank_payload.get("read_only_adapter", {}),
        "blank_intervention_status": blank_payload.get("intervention", {}),
        "redaction_proof_passed": True,
        "no_secrets_captured": True,
        "source_immutability_passed": immutability_summary["result"] == "success",
    }

    replay_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_observation_replay_packets_root(package_root, env=env).glob("*.json"))
    ]
    review_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_read_only_review_tickets_root(package_root, env=env).glob("*.json"))
    ]
    rollback_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_rollback_analyses_root(package_root, env=env).glob("*.json"))
    ]
    refusal_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_mutation_refusals_root(package_root, env=env).glob("*.json"))
    ]
    replay_ledger_path = resolve_observation_replay_ledger_path(package_root, env=env)
    replay_ledger_text = replay_ledger_path.read_text(encoding="utf-8") if replay_ledger_path.exists() else ""
    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(summary, sort_keys=True, default=str),
            json.dumps(shell_payload, sort_keys=True, default=str),
            json.dumps(blank_payload, sort_keys=True, default=str),
            replay_ledger_text,
            *replay_texts,
            *review_texts,
            *rollback_texts,
            *refusal_texts,
        ],
        tuple(fake_seed_values.values()),
    )
    if forbidden_hits or immutability_summary["result"] != "success" or telemetry_summary["result"] != "success":
        summary["result"] = "failure"
        summary["redaction_proof_passed"] = False if forbidden_hits else summary["redaction_proof_passed"]
        summary["no_secrets_captured"] = False if forbidden_hits else summary["no_secrets_captured"]
        summary["forbidden_hits"] = forbidden_hits

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=SUMMARY_JSON_NAME,
        markdown_name=SUMMARY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc87 Read-Only Adapter Sandbox Summary",
            [
                f"- Result: {summary['result']}",
                f"- Proof id: {summary['proof_id']}",
                f"- Observation replay packets: {replay_summary['packet_count']}",
                f"- Review ticket count: {review_summary['review_ticket_count']}",
                f"- Rollback analysis count: {rollback_summary['rollback_analysis_count']}",
                f"- Mutation refusal count: {mutation_summary['mutation_refusal_count']}",
                f"- Source immutability passed: {summary['source_immutability_passed']}",
                f"- Redaction proof passed: {summary['redaction_proof_passed']}",
                f"- No secrets captured: {summary['no_secrets_captured']}",
            ],
        ),
    )
    return summary


def main() -> int:
    summary = run_read_only_adapter_sandbox_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
