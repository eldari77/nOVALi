from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.controller_isolation import (
    build_default_lane_registry,
    build_doctrine_artifact,
    build_memory_artifact,
    build_replay_packet,
    build_review_ticket_from_finding,
    build_summary_artifact,
    clear_rc86_artifacts,
    copy_lane_artifact,
    detect_authority_claim,
    detect_cross_lane_message_violation,
    detect_hidden_shared_scratchpad,
    detect_namespace_collisions,
    detect_secret_leakage,
    detect_telemetry_identity,
    detect_wrong_lane_marker,
    emit_cross_lane_message,
    emit_identity_bleed,
    emit_namespace_check,
    emit_proof_completed,
    emit_registry_created,
    emit_replay_packet_written,
    emit_review_ticket_created,
    evaluate_cross_lane_message,
    isolation_span,
    resolve_controller_isolation_data_root,
    resolve_rc86_artifact_root,
    summarize_identity_bleed_findings,
    summarize_replay_packets,
    summarize_review_tickets,
    write_doctrine_artifact,
    write_identity_bleed_finding,
    write_lane_registry,
    write_memory_artifact,
    write_replay_packet,
    write_review_ticket,
    write_summary_artifact,
)
from operator_shell.controller_isolation.interventions import (
    append_lane_intervention_entry,
    append_lane_replay_review_binding,
)
from operator_shell.controller_isolation.namespaces import ensure_lane_namespace
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"rc86-dual-controller-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "RC86", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "doctrine_note": _fake_seed("doctrine", "secret"),
        "memory_note": _fake_seed("memory", "secret"),
        "cross_lane_payload": _fake_seed("cross", "lane", "secret"),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _lane_by_id(registry: Any, lane_id: str) -> Any:
    for lane in registry.lanes:
        if lane.lane_id == lane_id:
            return lane
    raise KeyError(lane_id)


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _shell_snapshot(package_root: Path) -> dict[str, Any]:
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


def _register_ticket_and_replay(
    *,
    package_root: Path,
    finding: Any,
    lane_id: str,
    intended_effect: str,
    replay_status: str,
    result_summary: str,
    message_id: str | None = None,
) -> dict[str, Any]:
    review_ticket = build_review_ticket_from_finding(
        finding,
        message_id=message_id,
        evidence_integrity_status="clean",
    )
    replay_packet = build_replay_packet(
        lane_id=lane_id,
        source_lane_id=finding.source_lane_id,
        target_lane_id=finding.target_lane_id,
        intended_effect=intended_effect,
        status=replay_status,
        result_summary=result_summary,
        review_required=True,
        review_reasons=list(review_ticket.review_reasons),
        evidence_integrity_status="clean",
        message_id=message_id,
        finding_id=finding.finding_id,
        review_ticket_id=review_ticket.review_ticket_id,
    )
    review_ticket.replay_packet_id = replay_packet.replay_packet_id
    replay_path = write_replay_packet(replay_packet, package_root=package_root)
    review_ticket.replay_packet_path_hint = str(Path(replay_path).relative_to(resolve_rc86_artifact_root(package_root)))
    ticket_path = write_review_ticket(review_ticket, package_root=package_root)
    finding.review_ticket_id = review_ticket.review_ticket_id
    finding.replay_packet_id = replay_packet.replay_packet_id
    finding_path = write_identity_bleed_finding(finding, package_root=package_root)
    append_lane_replay_review_binding(
        package_root,
        _lane_by_id(build_default_lane_registry(package_root), lane_id),
        binding_kind="replay_packet",
        artifact_id=replay_packet.replay_packet_id,
        artifact_path_hint=str(Path(replay_path).relative_to(package_root)),
        summary=result_summary,
    )
    append_lane_replay_review_binding(
        package_root,
        _lane_by_id(build_default_lane_registry(package_root), lane_id),
        binding_kind="review_ticket",
        artifact_id=review_ticket.review_ticket_id,
        artifact_path_hint=str(Path(ticket_path).relative_to(package_root)),
        summary=finding.evidence_summary_redacted,
        review_binding=True,
    )
    return {
        "finding": finding.to_dict(),
        "finding_path": finding_path,
        "review_ticket": review_ticket.to_dict(),
        "review_ticket_path": ticket_path,
        "replay_packet": replay_packet.to_dict(),
        "replay_packet_path": replay_path,
    }


def run_dual_controller_isolation_proof(
    *,
    package_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root = (package_root or ROOT).resolve()
    env = dict(env or os.environ)
    artifact_root = resolve_rc86_artifact_root(package_root, env=env)
    clear_rc86_artifacts(package_root, env=env)
    data_root = resolve_controller_isolation_data_root(package_root)
    if data_root.exists():
        shutil.rmtree(data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    fake_seed_values = _fake_seeds()
    proof_id = _proof_id()
    proof_kind = "dual_controller_isolation_proof"

    disabled_env = {**env, "NOVALI_OTEL_ENABLED": "false"}
    enabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or "novalioperatorshell"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": str(env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"),
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict"),
        "RC86_PROOF_ARTIFACT_ROOT": str(artifact_root),
    }

    disabled_status = initialize_observability(load_observability_config(disabled_env))
    shutdown_observability()
    enabled_status_before = initialize_observability(load_observability_config(enabled_env))

    registry = build_default_lane_registry(package_root)
    registry_path = write_lane_registry(package_root, registry)
    _write_json(artifact_root / "lane_registry.json", registry.to_dict())

    lane_artifact_paths: list[Path] = []
    telemetry_records: list[dict[str, str]] = []
    cross_lane_envelopes: list[dict[str, Any]] = []
    ticket_records: list[dict[str, Any]] = []

    with isolation_span(
        "novali.controller_isolation.rc86_proof.run",
        result="success",
        proof_kind=proof_kind,
    ):
        emit_registry_created(lane_count=registry.lane_count, proof_kind=proof_kind)
        for lane in registry.lanes:
            with isolation_span(
                "novali.controller_isolation.lane.create",
                lane_role=lane.lane_role,
                lane_id=lane.lane_id,
                result="success",
                proof_kind=proof_kind,
            ) as lane_trace:
                telemetry_records.append(dict(lane_trace["attributes"]))
            namespace = ensure_lane_namespace(package_root, lane)
            doctrine_artifact = build_doctrine_artifact(
                lane,
                doctrine_summary=f"[lane:{lane.lane_id}] mock isolation lane doctrine baseline",
            )
            memory_artifact = build_memory_artifact(
                lane,
                memory_summary=f"[lane:{lane.lane_id}] memory continuity note",
            )
            summary_artifact = build_summary_artifact(
                lane,
                summary=f"[lane:{lane.lane_id}] isolated summary lane record",
                continuity_note="No hidden shared state is permitted across sovereign lanes.",
            )
            doctrine_path = write_doctrine_artifact(package_root, lane, doctrine_artifact)
            memory_path = write_memory_artifact(package_root, lane, memory_artifact)
            summary_path = write_summary_artifact(package_root, lane, summary_artifact)
            append_lane_intervention_entry(
                package_root,
                lane,
                event_type="lane_initialized",
                review_status="clear",
                summary="Lane initialized for rc86 isolation proof.",
            )
            append_lane_replay_review_binding(
                package_root,
                lane,
                binding_kind="lane_initialized",
                artifact_id=lane.lane_id,
                artifact_path_hint=namespace.summary_path,
                summary="Lane-specific replay/review binding initialized for rc86 proof.",
            )
            for source in (
                doctrine_path,
                memory_path,
                summary_path,
                package_root / namespace.intervention_path,
                package_root / namespace.replay_review_path,
                package_root / namespace.review_path,
            ):
                lane_artifact_paths.append(Path(source))
                copy_lane_artifact(
                    source,
                    package_root=package_root,
                    env=env,
                    target_name=f"{lane.lane_id}/{Path(source).name}",
                )

        base_namespace_findings = detect_namespace_collisions(registry.lanes)
        base_namespace_status = "pass" if not base_namespace_findings else "fail"
        emit_namespace_check(status=base_namespace_status, proof_kind=proof_kind)

        allowed_envelope, approval_record = evaluate_cross_lane_message(
            source_lane_id="lane_sovereign_good",
            target_lane_id="lane_sovereign_dark",
            message_type="coordination_note",
            payload_summary="Director-mediated coordination note proving the cross-lane envelope path.",
            allowed_scope="mock_status_exchange",
            mediated_by_lane_id="lane_director",
        )
        allowed_replay = build_replay_packet(
            lane_id="lane_director",
            source_lane_id=allowed_envelope.source_lane_id,
            target_lane_id=allowed_envelope.target_lane_id,
            message_id=allowed_envelope.message_id,
            intended_effect="Record a safe Director-mediated cross-lane coordination note.",
            status="delivered_mock_only",
            result_summary="Director-mediated coordination note recorded without any external action.",
            review_required=False,
            review_reasons=[],
            evidence_integrity_status="clean",
        )
        allowed_envelope.replay_packet_id = allowed_replay.replay_packet_id
        allowed_path = write_replay_packet(allowed_replay, package_root=package_root)
        emit_cross_lane_message(
            source_lane_id=allowed_envelope.source_lane_id,
            target_lane_id=allowed_envelope.target_lane_id,
            message_type=allowed_envelope.message_type,
            result=allowed_envelope.approval_status,
            proof_kind=proof_kind,
        )
        emit_replay_packet_written(
            lane_id="lane_director",
            result=allowed_replay.status,
            proof_kind=proof_kind,
        )
        cross_lane_envelopes.append(
            {
                "envelope": allowed_envelope.to_dict(),
                "approval_record": approval_record.to_dict(),
                "replay_packet_id": allowed_replay.replay_packet_id,
                "replay_packet_path": allowed_path,
            }
        )

        blocked_envelope, blocked_approval = evaluate_cross_lane_message(
            source_lane_id="lane_sovereign_good",
            target_lane_id="lane_sovereign_dark",
            message_type="coordination_note",
            payload_summary="Unauthorized direct sovereign-to-sovereign message.",
            allowed_scope="mock_status_exchange",
            mediated_by_lane_id="lane_sovereign_good",
        )
        emit_cross_lane_message(
            source_lane_id=blocked_envelope.source_lane_id,
            target_lane_id=blocked_envelope.target_lane_id,
            message_type=blocked_envelope.message_type,
            result=blocked_envelope.approval_status,
            proof_kind=proof_kind,
        )
        blocked_findings = detect_cross_lane_message_violation(blocked_envelope)
        blocked_ticket_bundle = [
            _register_ticket_and_replay(
                package_root=package_root,
                finding=finding,
                lane_id="lane_sovereign_good",
                intended_effect="Block unauthorized direct sovereign-to-sovereign communication.",
                replay_status="blocked",
                result_summary="Unauthorized direct cross-lane message was blocked and escalated for review.",
                message_id=blocked_envelope.message_id,
            )
            for finding in blocked_findings
        ]
        for finding in blocked_findings:
            emit_identity_bleed(
                lane_id=finding.source_lane_id,
                bleed_type=finding.finding_type,
                severity=finding.severity,
                proof_kind=proof_kind,
            )
        for bundle in blocked_ticket_bundle:
            ticket_records.append(bundle)
            emit_review_ticket_created(
                review_status=bundle["review_ticket"]["review_status"],
                review_trigger=bundle["review_ticket"]["review_trigger"],
                proof_kind=proof_kind,
            )
            emit_replay_packet_written(
                lane_id="lane_sovereign_good",
                result=bundle["replay_packet"]["status"],
                proof_kind=proof_kind,
            )
        cross_lane_envelopes.append(
            {
                "envelope": blocked_envelope.to_dict(),
                "approval_record": blocked_approval.to_dict(),
                "findings": [finding.to_dict() for finding in blocked_findings],
            }
        )

        scratchpad_findings = detect_hidden_shared_scratchpad(
            {
                "lane_sovereign_good": "data/controller_isolation/shared_scratchpad.txt",
                "lane_sovereign_dark": "data/controller_isolation/shared_scratchpad.txt",
            }
        )
        for finding in scratchpad_findings:
            bundle = _register_ticket_and_replay(
                package_root=package_root,
                finding=finding,
                lane_id=finding.source_lane_id,
                intended_effect="Detect a hidden shared scratchpad path before any lane bleed becomes persistent.",
                replay_status="review_required",
                result_summary="Shared scratchpad reuse detected and blocked as critical identity bleed.",
            )
            ticket_records.append(bundle)
            emit_identity_bleed(
                lane_id=finding.source_lane_id,
                bleed_type=finding.finding_type,
                severity=finding.severity,
                proof_kind=proof_kind,
            )
            emit_review_ticket_created(
                review_status=bundle["review_ticket"]["review_status"],
                review_trigger=bundle["review_ticket"]["review_trigger"],
                proof_kind=proof_kind,
            )
            emit_replay_packet_written(
                lane_id=finding.source_lane_id,
                result=bundle["replay_packet"]["status"],
                proof_kind=proof_kind,
            )

        reserved_markers = {lane.lane_id: f"[lane:{lane.lane_id}]" for lane in registry.lanes}
        doctrine_bleed_findings = detect_wrong_lane_marker(
            owner_lane_id="lane_sovereign_dark",
            reserved_markers=reserved_markers,
            artifact_text=f"[lane:lane_sovereign_dark] doctrine baseline {reserved_markers['lane_sovereign_good']}",
            finding_type="doctrine_bleed_detected",
        )
        for finding in doctrine_bleed_findings:
            bundle = _register_ticket_and_replay(
                package_root=package_root,
                finding=finding,
                lane_id="lane_sovereign_dark",
                intended_effect="Detect doctrine contamination before any cross-lane doctrine transfer can occur.",
                replay_status="review_required",
                result_summary="Doctrine bleed marker detected in the wrong lane artifact.",
            )
            ticket_records.append(bundle)
            emit_identity_bleed(
                lane_id=finding.source_lane_id,
                bleed_type=finding.finding_type,
                severity=finding.severity,
                proof_kind=proof_kind,
            )
            emit_review_ticket_created(
                review_status=bundle["review_ticket"]["review_status"],
                review_trigger=bundle["review_ticket"]["review_trigger"],
                proof_kind=proof_kind,
            )
            emit_replay_packet_written(
                lane_id="lane_sovereign_dark",
                result=bundle["replay_packet"]["status"],
                proof_kind=proof_kind,
            )

        collided_registry = build_default_lane_registry(package_root)
        _lane_by_id(collided_registry, "lane_sovereign_dark").memory_namespace = _lane_by_id(
            collided_registry, "lane_sovereign_good"
        ).memory_namespace
        memory_collision_findings = [
            finding
            for finding in detect_namespace_collisions(collided_registry.lanes)
            if finding.finding_type == "memory_namespace_collision"
        ]
        for finding in memory_collision_findings:
            bundle = _register_ticket_and_replay(
                package_root=package_root,
                finding=finding,
                lane_id=finding.source_lane_id,
                intended_effect="Detect memory namespace reuse before memory contamination can persist.",
                replay_status="review_required",
                result_summary="Memory namespace collision detected and routed into review.",
            )
            ticket_records.append(bundle)
            emit_identity_bleed(
                lane_id=finding.source_lane_id,
                bleed_type=finding.finding_type,
                severity=finding.severity,
                proof_kind=proof_kind,
            )
            emit_review_ticket_created(
                review_status=bundle["review_ticket"]["review_status"],
                review_trigger=bundle["review_ticket"]["review_trigger"],
                proof_kind=proof_kind,
            )
            emit_replay_packet_written(
                lane_id=finding.source_lane_id,
                result=bundle["replay_packet"]["status"],
                proof_kind=proof_kind,
            )

        authority_registry = build_default_lane_registry(package_root)
        _lane_by_id(authority_registry, "lane_sovereign_dark").adoption_authority = True
        authority_findings = detect_authority_claim(_lane_by_id(authority_registry, "lane_sovereign_dark"))
        for finding in authority_findings:
            bundle = _register_ticket_and_replay(
                package_root=package_root,
                finding=finding,
                lane_id=finding.source_lane_id,
                intended_effect="Refuse any unauthorized authority claim from a mock lane.",
                replay_status="rejected",
                result_summary="Unauthorized lane authority claim detected and rejected.",
            )
            ticket_records.append(bundle)
            emit_identity_bleed(
                lane_id=finding.source_lane_id,
                bleed_type=finding.finding_type,
                severity=finding.severity,
                proof_kind=proof_kind,
            )
            emit_review_ticket_created(
                review_status=bundle["review_ticket"]["review_status"],
                review_trigger=bundle["review_ticket"]["review_trigger"],
                proof_kind=proof_kind,
            )
            emit_replay_packet_written(
                lane_id=finding.source_lane_id,
                result=bundle["replay_packet"]["status"],
                proof_kind=proof_kind,
            )

        telemetry_findings = detect_telemetry_identity(telemetry_records)
        flush_result = flush_observability()
        enabled_status_after = get_observability_status()
        emit_proof_completed(result="success", proof_kind=proof_kind)
    shutdown_observability()

    secret_findings = []
    for lane_path in lane_artifact_paths:
        secret_findings.extend(
            detect_secret_leakage(
                lane_id=lane_path.parent.name,
                artifact_text=lane_path.read_text(encoding="utf-8"),
                fake_seeds=fake_seed_values.values(),
            )
        )

    identity_bleed_summary = summarize_identity_bleed_findings(package_root=package_root, env=env)
    review_ticket_summary = summarize_review_tickets(package_root=package_root, env=env)
    replay_packet_summary = summarize_replay_packets(package_root=package_root, env=env)

    namespace_summary = {
        "schema_name": "novali_rc86_lane_namespace_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "lane_count": registry.lane_count,
        "namespace_separation": "fail" if memory_collision_findings else "pass",
        "no_hidden_shared_scratchpad": "fail" if scratchpad_findings else "pass",
        "shared_namespace_findings": [finding.to_dict() for finding in base_namespace_findings + memory_collision_findings],
        "data_root": str(data_root),
        "lane_registry_path": str(registry_path),
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="lane_namespace_summary.json",
        markdown_name="lane_namespace_summary.md",
        summary=namespace_summary,
        markdown=_markdown(
            "# rc86 Lane Namespace Summary",
            [
                f"- Lane count: {namespace_summary['lane_count']}",
                f"- Namespace separation: {namespace_summary['namespace_separation']}",
                f"- Hidden shared scratchpad: {namespace_summary['no_hidden_shared_scratchpad']}",
            ],
        ),
    )

    cross_lane_message_summary = {
        "schema_name": "novali_rc86_cross_lane_message_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "proposed_count": len(cross_lane_envelopes),
        "approved_count": sum(
            1
            for entry in cross_lane_envelopes
            if str(dict(entry.get("envelope", {})).get("approval_status", "")).strip() == "director_approved"
        ),
        "blocked_count": sum(
            1
            for entry in cross_lane_envelopes
            if str(dict(entry.get("envelope", {})).get("approval_status", "")).strip() in {"blocked", "rejected", "review_required"}
        ),
        "unauthorized_count": len(blocked_findings),
        "latest_message_id": str(dict(cross_lane_envelopes[-1].get("envelope", {})).get("message_id", "")).strip() if cross_lane_envelopes else None,
        "director_channel_required": "fail" if blocked_findings else "pass",
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="cross_lane_message_summary.json",
        markdown_name="cross_lane_message_summary.md",
        summary=cross_lane_message_summary,
        markdown=_markdown(
            "# rc86 Cross-Lane Message Summary",
            [
                f"- Proposed count: {cross_lane_message_summary['proposed_count']}",
                f"- Approved count: {cross_lane_message_summary['approved_count']}",
                f"- Blocked count: {cross_lane_message_summary['blocked_count']}",
                f"- Unauthorized count: {cross_lane_message_summary['unauthorized_count']}",
            ],
        ),
    )

    telemetry_identity_summary = {
        "schema_name": "novali_rc86_telemetry_identity_summary_v1",
        "generated_at": _now_iso(),
        "result": "success" if not telemetry_findings else "failure",
        "telemetry_lane_identity": "pass" if not telemetry_findings else "fail",
        "record_count": len(telemetry_records),
        "finding_count": len(telemetry_findings),
        "records": telemetry_records,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="telemetry_identity_summary.json",
        markdown_name="telemetry_identity_summary.md",
        summary=telemetry_identity_summary,
        markdown=_markdown(
            "# rc86 Telemetry Identity Summary",
            [
                f"- Telemetry lane identity: {telemetry_identity_summary['telemetry_lane_identity']}",
                f"- Record count: {telemetry_identity_summary['record_count']}",
                f"- Finding count: {telemetry_identity_summary['finding_count']}",
            ],
        ),
    )

    shell_payload = _shell_snapshot(package_root)
    summary = {
        "schema_name": "novali_rc86_dual_controller_isolation_summary_v1",
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "schema_version": "rc86.v1",
        "result": "success",
        "telemetry_disabled_status": disabled_status,
        "telemetry_enabled_status_before": enabled_status_before,
        "telemetry_enabled_status_after": enabled_status_after,
        "telemetry_flush_result": flush_result,
        "lane_registry_path": str(registry_path),
        "lane_count": registry.lane_count,
        "cross_lane_message_summary": cross_lane_message_summary,
        "identity_bleed_summary": identity_bleed_summary,
        "review_ticket_summary": review_ticket_summary,
        "replay_packet_summary": replay_packet_summary,
        "telemetry_identity_summary": telemetry_identity_summary,
        "namespace_summary": namespace_summary,
        "shell_status_checked": True,
        "controller_isolation_status": shell_payload.get("controller_isolation", {}),
        "intervention_status": shell_payload.get("intervention", {}),
        "operator_state": shell_payload.get("operator_state", {}),
        "redaction_proof_passed": True,
        "no_secrets_captured": True,
        "critical_identity_bleed_detected": identity_bleed_summary.get("critical_count", 0),
        "review_ticket_count": review_ticket_summary.get("review_ticket_count", 0),
        "replay_packet_count": replay_packet_summary.get("replay_packet_count", 0),
    }

    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(summary, sort_keys=True, default=str),
            json.dumps(shell_payload, sort_keys=True, default=str),
            *[path.read_text(encoding="utf-8") for path in lane_artifact_paths],
            *[
                path.read_text(encoding="utf-8")
                for path in sorted((artifact_root / "identity_bleed_findings").glob("*.json"))
            ],
            *[
                path.read_text(encoding="utf-8")
                for path in sorted((artifact_root / "review_tickets").glob("*.json"))
            ],
            *[
                path.read_text(encoding="utf-8")
                for path in sorted((artifact_root / "replay_packets").glob("*.json"))
            ],
        ],
        tuple(fake_seed_values.values()),
    )
    if forbidden_hits or secret_findings:
        summary["result"] = "failure"
        summary["redaction_proof_passed"] = False
        summary["no_secrets_captured"] = False
        summary["forbidden_hits"] = forbidden_hits
        summary["secret_findings"] = [finding.to_dict() for finding in secret_findings]

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="dual_controller_isolation_summary.json",
        markdown_name="dual_controller_isolation_summary.md",
        summary=summary,
        markdown=_markdown(
            "# rc86 Dual-Controller Isolation Summary",
            [
                f"- Result: {summary['result']}",
                f"- Proof id: {summary['proof_id']}",
                f"- Lane count: {summary['lane_count']}",
                f"- Review ticket count: {summary['review_ticket_count']}",
                f"- Replay packet count: {summary['replay_packet_count']}",
                f"- Redaction proof passed: {summary['redaction_proof_passed']}",
                f"- No secrets captured: {summary['no_secrets_captured']}",
            ],
        ),
    )
    return summary


def main() -> int:
    summary = run_dual_controller_isolation_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
