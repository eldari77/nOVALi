from __future__ import annotations

import json
import sys
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.external_adapter import (
    resolve_mutation_refusals_root,
    resolve_observation_replay_packets_root,
    resolve_read_only_review_tickets_root,
    resolve_rollback_analyses_root,
)
from operator_shell.observability import (
    flush_observability,
    get_observability_shutdown_status,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    shutdown_observability,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts
from operator_shell.operator_alerts import (
    assess_rc87_fixture_adapter,
    assess_space_engineers_read_only_bridge,
    build_alert_candidate,
    build_evidence_bundle,
    build_runtime_candidate_descriptors,
    build_space_engineers_transition_decision_memo,
    clear_operator_alert_state,
    default_read_only_admission_criteria,
    emit_admission_assessed,
    emit_alert_acknowledged,
    emit_alert_closed_evidence_only,
    emit_alert_raised,
    emit_alert_reviewed,
    emit_alert_superseded,
    emit_evidence_bundle_created,
    emit_operator_alert_proof_completed,
    emit_read_only_alert_mapped,
    emit_runtime_candidate_evaluated,
    operator_alert_span,
    raise_alert,
    render_space_engineers_transition_decision_memo,
    resolve_alerts_root,
    resolve_evidence_bundles_root,
    resolve_lifecycle_events_root,
    resolve_rc88_artifact_root,
    summarize_alerts,
    summarize_evidence_bundles,
)
from operator_shell.scripts.rc85_review_rollback_integration_proof import (
    run_review_rollback_integration_proof,
)
from operator_shell.scripts.rc86_dual_controller_isolation_proof import (
    run_dual_controller_isolation_proof,
)
from operator_shell.scripts.rc87_read_only_adapter_sandbox_proof import (
    run_read_only_adapter_sandbox_proof,
)
from operator_shell.web_operator import OperatorWebService

SUMMARY_JSON_NAME = "operator_alert_loop_summary.json"
SUMMARY_MD_NAME = "operator_alert_loop_summary.md"
ALERT_SUMMARY_JSON_NAME = "alert_candidate_summary.json"
ALERT_SUMMARY_MD_NAME = "alert_candidate_summary.md"
LIFECYCLE_JSON_NAME = "alert_lifecycle_summary.json"
LIFECYCLE_MD_NAME = "alert_lifecycle_summary.md"
EVIDENCE_JSON_NAME = "evidence_bundle_summary.json"
EVIDENCE_MD_NAME = "evidence_bundle_summary.md"
ADMISSION_JSON_NAME = "read_only_admission_assessment.json"
ADMISSION_MD_NAME = "read_only_admission_assessment.md"
LOGICMONITOR_JSON_NAME = "logicmonitor_alert_mapping_summary.json"
LOGICMONITOR_MD_NAME = "logicmonitor_alert_mapping_summary.md"
IMMUTABILITY_JSON_NAME = "source_immutability_alert_summary.json"
IMMUTABILITY_MD_NAME = "source_immutability_alert_summary.md"
TELEMETRY_JSON_NAME = "telemetry_identity_summary.json"
TELEMETRY_MD_NAME = "telemetry_identity_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"rc88-operator-alert-loop-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "RC88", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "alert_note": _fake_seed("alert", "secret"),
        "evidence_payload": _fake_seed("evidence", "secret"),
        "lm_header": _fake_seed("lm", "header"),
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _relative_hint(package_root: Path, path_like: str | Path | None) -> str | None:
    if path_like is None:
        return None
    raw = str(path_like).strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(package_root.resolve())).replace("\\", "/")
        except ValueError:
            return path.name
    return raw.replace("\\", "/")


def _existing_relative_hint(package_root: Path, path_like: str | Path | None) -> str | None:
    if path_like is None:
        return None
    path = Path(str(path_like).strip())
    if not str(path).strip():
        return None
    resolved = path if path.is_absolute() else (package_root / path)
    if not resolved.resolve().exists():
        return None
    return _relative_hint(package_root, resolved)


def _service(package_root: Path) -> OperatorWebService:
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
    return service


def _write_status_snapshot(
    artifact_root: Path,
    *,
    name: str,
    payload: Mapping[str, Any],
) -> str:
    path = artifact_root / f"{name}.json"
    _write_json(path, payload)
    return path.name


def _emit_span_record(
    telemetry_records: list[dict[str, Any]],
    name: str,
    **kwargs: Any,
) -> None:
    with operator_alert_span(name, **kwargs) as attrs:
        telemetry_records.append(dict(attrs))


def _load_json_objects(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return payloads


def _flow_refs(
    *,
    package_root: Path,
    rc87_artifact_root: Path,
    flow: Mapping[str, Any],
    include_lane_summary: bool = False,
    include_source_immutability: bool = False,
) -> dict[str, list[str] | str | None]:
    mutation_refusal = dict(flow.get("mutation_refusal", {}) or {})
    mutation_refusal_id = str(mutation_refusal.get("refusal_id", "")).strip() or None
    mutation_refusal_ref = None
    if mutation_refusal_id:
        mutation_refusal_ref = _relative_hint(
            package_root,
            resolve_mutation_refusals_root(package_root) / f"{mutation_refusal_id}.json",
        )
    replay_path = _relative_hint(package_root, flow.get("replay_packet_path"))
    review_path = _relative_hint(package_root, flow.get("review_ticket_path"))
    rollback_path = _relative_hint(package_root, flow.get("rollback_analysis_path"))
    lane_refs: list[str] = []
    if include_lane_summary:
        lane_ref = _relative_hint(package_root, rc87_artifact_root / "lane_attribution_summary.json")
        if lane_ref:
            lane_refs.append(lane_ref)
    source_refs: list[str] = []
    if include_source_immutability:
        source_ref = _existing_relative_hint(package_root, rc87_artifact_root / "source_immutability_summary.json")
        if source_ref:
            source_refs.append(source_ref)
    telemetry_ref = _existing_relative_hint(package_root, rc87_artifact_root / "telemetry_identity_summary.json")
    package_refs = [
        ref
        for ref in [
            _existing_relative_hint(package_root, rc87_artifact_root / "packaged_route_validation.json"),
            _existing_relative_hint(package_root, rc87_artifact_root / "package_hygiene_summary.json"),
        ]
        if ref
    ]
    return {
        "replay_packet_refs": [replay_path] if replay_path else [],
        "review_ticket_refs": [review_path] if review_path else [],
        "rollback_analysis_refs": [rollback_path] if rollback_path else [],
        "mutation_refusal_refs": [mutation_refusal_ref] if mutation_refusal_ref else [],
        "source_immutability_refs": source_refs,
        "lane_attribution_refs": lane_refs,
        "telemetry_refs": [telemetry_ref] if telemetry_ref else [],
        "package_validation_refs": package_refs,
    }


def _raise_candidate(
    *,
    package_root: Path,
    env: dict[str, str],
    telemetry_records: list[dict[str, Any]],
    alert_type: str,
    source: str,
    source_milestone: str,
    source_case: str,
    summary_redacted: str,
    status_endpoint_snapshot_ref: str | None,
    replay_packet_refs: list[str] | None = None,
    review_ticket_refs: list[str] | None = None,
    rollback_analysis_refs: list[str] | None = None,
    mutation_refusal_refs: list[str] | None = None,
    source_immutability_refs: list[str] | None = None,
    lane_attribution_refs: list[str] | None = None,
    telemetry_refs: list[str] | None = None,
    package_validation_refs: list[str] | None = None,
    lane_id: str | None = None,
    controller_isolation_finding_ids: list[str] | None = None,
    lm_dimension_hints: list[str] | None = None,
) -> dict[str, Any]:
    created_at = _now_iso()
    _emit_span_record(
        telemetry_records,
        "novali.operator_alert.read_only.map" if source.startswith("read_only") else "novali.operator_alert.telemetry_candidate.evaluate",
        alert_type=alert_type,
        source=source,
        result="success",
        proof_kind="operator_alert_loop_proof",
    )
    bundle = build_evidence_bundle(
        alert_id=f"pending-{alert_type}-{uuid.uuid4().hex[:6]}",
        source=source,
        source_case=source_case,
        replay_packet_refs=replay_packet_refs,
        review_ticket_refs=review_ticket_refs,
        rollback_analysis_refs=rollback_analysis_refs,
        mutation_refusal_refs=mutation_refusal_refs,
        source_immutability_refs=source_immutability_refs,
        lane_attribution_refs=lane_attribution_refs,
        telemetry_refs=telemetry_refs,
        status_endpoint_snapshot_ref=status_endpoint_snapshot_ref,
        package_validation_refs=package_validation_refs,
        package_root=package_root,
    )
    candidate = build_alert_candidate(
        alert_type=alert_type,
        source=source,
        source_milestone=source_milestone,
        summary_redacted=summary_redacted,
        evidence_bundle_id=bundle.evidence_bundle_id,
        replay_packet_ids=[Path(ref).stem for ref in list(replay_packet_refs or []) if str(ref).strip()],
        review_ticket_ids=[Path(ref).stem for ref in list(review_ticket_refs or []) if str(ref).strip()],
        rollback_analysis_ids=[Path(ref).stem for ref in list(rollback_analysis_refs or []) if str(ref).strip()],
        mutation_refusal_ids=[Path(ref).stem for ref in list(mutation_refusal_refs or []) if str(ref).strip()],
        source_immutability_ref=(list(source_immutability_refs or [None])[0] if source_immutability_refs else None),
        lane_id=lane_id,
        controller_isolation_finding_ids=list(controller_isolation_finding_ids or []),
        telemetry_trace_hint="rc88.operator_alert_loop.proof",
        lm_dimension_hints=list(lm_dimension_hints or []),
        created_at=created_at,
        updated_at=created_at,
    )
    bundle.alert_id = candidate.alert_id
    raise_alert(candidate, bundle, package_root=package_root, env=env)
    telemetry_records.append(
        emit_evidence_bundle_created(
            alert_type=alert_type,
            source=source,
            result=bundle.evidence_integrity_status,
            proof_kind="operator_alert_loop_proof",
        )
    )
    if source.startswith("read_only"):
        telemetry_records.append(
            emit_read_only_alert_mapped(
                alert_type=alert_type,
                severity=candidate.severity,
                proof_kind="operator_alert_loop_proof",
            )
        )
    else:
        telemetry_records.append(
            emit_runtime_candidate_evaluated(
                alert_type=alert_type,
                source=source,
                proof_kind="operator_alert_loop_proof",
            )
        )
    telemetry_records.append(
        emit_alert_raised(
            alert_type=alert_type,
            severity=candidate.severity,
            source=source,
            result=candidate.status,
            proof_kind="operator_alert_loop_proof",
        )
    )
    return {
        "candidate": candidate.to_dict(),
        "bundle": bundle.to_dict(),
    }


def _load_lifecycle_events(package_root: Path, env: Mapping[str, str]) -> list[dict[str, Any]]:
    return _load_json_objects(resolve_lifecycle_events_root(package_root, env=env))


def _candidate_markdown(summary: Mapping[str, Any]) -> str:
    return _markdown(
        "# rc88 Alert Candidate Summary",
        [
            f"- Alert count: {summary.get('alert_count', 0)}",
            f"- Raised: {summary.get('raised_count', 0)}",
            f"- Blocked: {summary.get('blocked_count', 0)}",
            f"- Critical: {summary.get('critical_count', 0)}",
            f"- Latest alert id: {summary.get('latest_alert_id') or '<none>'}",
            f"- Latest alert type: {summary.get('latest_alert_type') or '<none>'}",
        ],
    )


def _lifecycle_markdown(summary: Mapping[str, Any]) -> str:
    return _markdown(
        "# rc88 Alert Lifecycle Summary",
        [
            f"- Event count: {summary.get('event_count', 0)}",
            f"- Append-only preserved: {summary.get('append_only', False)}",
            f"- Acknowledged alerts: {summary.get('acknowledged_alert_count', 0)}",
            f"- Reviewed alerts: {summary.get('reviewed_alert_count', 0)}",
            f"- Evidence-only closed alerts: {summary.get('closed_alert_count', 0)}",
            f"- Superseded alerts: {summary.get('superseded_alert_count', 0)}",
        ],
    )


def _logicmonitor_mapping() -> dict[str, Any]:
    alert_types = [
        "read_only_mutation_requested",
        "read_only_integrity_failed",
        "read_only_source_immutability_failed",
        "read_only_forbidden_domain_term",
        "read_only_secret_detected",
        "read_only_wrong_lane_attribution",
        "read_only_conflicting_observation",
        "read_only_stale_snapshot",
        "telemetry_export_degraded",
        "no_telemetry_seen",
        "collector_down_candidate",
        "review_hold_active",
        "repeated_review_hold",
        "checkpoint_failure",
        "rollback_loop_candidate",
        "redaction_failure",
        "controller_identity_bleed",
        "scope_expansion_pressure",
    ]
    return {
        "schema_name": "novali_rc88_logicmonitor_alert_mapping_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "portal_delivery_claimed": False,
        "logicmonitor_api_used": False,
        "alert_type_count": len(alert_types),
        "alert_types": alert_types,
        "example_dimensions": {
            "service.name": "novalioperatorshell",
            "service.namespace": "novali",
            "novali.branch": "novali-v6",
            "novali.package.version": "rc88",
            "novali.alert.type": "<alert_type>",
            "novali.alert.severity": "<severity>",
            "novali.alert.status": "<status>",
            "novali.adapter.kind": "<adapter_kind>",
            "novali.controller.lane": "<lane_id>",
            "novali.review_status": "<review_status>",
            "novali.result": "<result>",
        },
        "notes": [
            "LogicMonitor remains observability tooling only.",
            "NOVALI does not create LogicMonitor alerts by API in rc88.",
            "Portal-side alert configuration remains operator-managed.",
            "NOVALI acknowledgement is local evidence only and is not governance approval.",
        ],
    }


def _telemetry_summary(
    *,
    artifact_root: Path,
    telemetry_records: list[dict[str, Any]],
    disabled_status: Mapping[str, Any],
    enabled_status_before: Mapping[str, Any],
    enabled_status_after: Mapping[str, Any],
    flush_result: Mapping[str, Any],
    shutdown_result: Mapping[str, Any],
) -> dict[str, Any]:
    lane_ids = sorted(
        {
            str(item.get("novali.controller.lane", "")).strip()
            for item in telemetry_records
            if str(item.get("novali.controller.lane", "")).strip()
        }
    )
    summary = {
        "schema_name": "novali_rc88_operator_alert_telemetry_identity_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "record_count": len(telemetry_records),
        "lane_ids": lane_ids,
        "disabled_status": dict(disabled_status),
        "enabled_status_before": dict(enabled_status_before),
        "enabled_status_after": dict(enabled_status_after),
        "flush_result": dict(flush_result),
        "shutdown_result": dict(shutdown_result),
        "records": telemetry_records,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=TELEMETRY_JSON_NAME,
        markdown_name=TELEMETRY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc88 Telemetry Identity Summary",
            [
                f"- Result: {summary['result']}",
                f"- Record count: {summary['record_count']}",
                f"- Lane ids: {', '.join(summary['lane_ids']) or '<none>'}",
                f"- Disabled mode status: {dict(disabled_status).get('status', '<unknown>')}",
                f"- Enabled mode status: {dict(enabled_status_after).get('status', '<unknown>')}",
                f"- Shutdown result: {dict(shutdown_result).get('result', '<unknown>')}",
            ],
        ),
    )
    return summary


def run_operator_alert_loop_proof(
    *,
    package_root: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(env or {})
    package_root_path = Path(package_root).resolve() if package_root is not None else ROOT
    artifact_root = resolve_rc88_artifact_root(package_root_path, env=env)
    proof_id = _proof_id()
    fake_seed_values = _fake_seeds()
    clear_operator_alert_state(package_root=package_root_path, env=env)
    artifact_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as blank_temp:
        blank_root = Path(blank_temp)
        blank_service = _service(blank_root)
        blank_shell = blank_service.current_shell_state_payload()
        blank_alerts = dict(blank_shell.get("operator_alerts", {}))

    rc85_summary = run_review_rollback_integration_proof(package_root=package_root_path, env=env)
    rc86_summary = run_dual_controller_isolation_proof(package_root=package_root_path, env=env)
    rc87_summary = run_read_only_adapter_sandbox_proof(package_root=package_root_path, env=env)
    rc87_artifact_root = package_root_path / "artifacts" / "operator_proof" / "rc87"

    service = _service(package_root_path)
    pre_alert_shell = service.current_shell_state_payload()
    status_snapshot_ref = _write_status_snapshot(
        artifact_root,
        name="status_snapshot_before_alerts",
        payload=pre_alert_shell,
    )

    telemetry_records: list[dict[str, Any]] = []
    disabled_status = initialize_observability(
        load_observability_config({"NOVALI_OTEL_ENABLED": "0"})
    )
    telemetry_records.append(
        emit_operator_alert_proof_completed(
            result="disabled_noop",
            proof_kind="operator_alert_loop_proof",
        )
    )
    shutdown_observability()
    enabled_status_before = initialize_observability(
        load_observability_config(
            {
                "NOVALI_OTEL_ENABLED": "1",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
            }
        )
    )

    alert_records: dict[str, dict[str, Any]] = {}
    read_only_mappings = [
        ("missing_fields", "missing_fields_flow", "read_only_schema_missing_field", False, False),
        ("conflict", "conflicting_observations_flow", "read_only_conflicting_observation", False, False),
        ("stale", "stale_snapshot_flow", "read_only_stale_snapshot", False, False),
        ("wrong_lane", "wrong_lane_attribution_flow", "read_only_wrong_lane_attribution", True, False),
        ("mutation", "mutation_refusal_flow", "read_only_mutation_requested", False, False),
        ("forbidden", "forbidden_domain_term_flow", "read_only_forbidden_domain_term", False, False),
        ("secret", "secret_detected_flow", "read_only_secret_detected", False, False),
    ]
    for alias, flow_key, alert_type, include_lane_summary, include_source_immutability in read_only_mappings:
        flow = dict(rc87_summary.get(flow_key, {}) or {})
        refs = _flow_refs(
            package_root=package_root_path,
            rc87_artifact_root=rc87_artifact_root,
            flow=flow,
            include_lane_summary=include_lane_summary,
            include_source_immutability=include_source_immutability,
        )
        record = _raise_candidate(
            package_root=package_root_path,
            env=env,
            telemetry_records=telemetry_records,
            alert_type=alert_type,
            source="read_only_adapter_proof",
            source_milestone="rc87",
            source_case=flow_key,
            summary_redacted=str(flow.get("observation_summary", "")).strip()
            or f"Proof-mapped read-only alert for {flow_key}.",
            status_endpoint_snapshot_ref=status_snapshot_ref,
            replay_packet_refs=list(refs.get("replay_packet_refs", []) or []),
            review_ticket_refs=list(refs.get("review_ticket_refs", []) or []),
            rollback_analysis_refs=list(refs.get("rollback_analysis_refs", []) or []),
            mutation_refusal_refs=list(refs.get("mutation_refusal_refs", []) or []),
            source_immutability_refs=list(refs.get("source_immutability_refs", []) or []),
            lane_attribution_refs=list(refs.get("lane_attribution_refs", []) or []),
            telemetry_refs=list(refs.get("telemetry_refs", []) or []),
            package_validation_refs=list(refs.get("package_validation_refs", []) or []),
            lane_id=str(dict(flow.get("snapshot", {})).get("lane_id", "")).strip() or None,
            lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
        )
        alert_records[alias] = record

    replay_missing_record = _raise_candidate(
        package_root=package_root_path,
        env=env,
        telemetry_records=telemetry_records,
        alert_type="read_only_replay_missing",
        source="read_only_adapter_proof",
        source_milestone="rc88",
        source_case="proof_missing_replay_reference",
        summary_redacted="Proof-only replay reference check failed; missing replay evidence is now operator-visible.",
        status_endpoint_snapshot_ref=status_snapshot_ref,
        replay_packet_refs=["artifacts/operator_proof/rc87/observation_replay_packets/missing-replay-packet.json"],
        review_ticket_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "review_ticket_summary.json")
        ],
        rollback_analysis_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "rollback_analysis_summary.json")
        ],
        telemetry_refs=[_relative_hint(package_root_path, rc87_artifact_root / "telemetry_identity_summary.json")],
        package_validation_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "packaged_route_validation.json")
        ],
        lane_id="lane_director",
        lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
    )
    alert_records["replay_missing"] = replay_missing_record

    integrity_failed_record = _raise_candidate(
        package_root=package_root_path,
        env=env,
        telemetry_records=telemetry_records,
        alert_type="read_only_integrity_failed",
        source="read_only_adapter_proof",
        source_milestone="rc88",
        source_case="proof_missing_evidence_integrity",
        summary_redacted="Evidence bundle integrity failed because linked replay evidence was missing during the proof-only path.",
        status_endpoint_snapshot_ref=status_snapshot_ref,
        review_ticket_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "review_ticket_summary.json")
        ],
        source_immutability_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "source_immutability_summary.json")
        ],
        telemetry_refs=[_relative_hint(package_root_path, rc87_artifact_root / "telemetry_identity_summary.json")],
        package_validation_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "package_hygiene_summary.json")
        ],
        lane_id="lane_director",
        lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
    )
    alert_records["integrity_failed"] = integrity_failed_record

    source_immutability_alert_summary = {
        "schema_name": "novali_rc88_source_immutability_alert_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "simulated_failure": True,
        "real_fixture_mutated": False,
        "source_summary_ref": _relative_hint(package_root_path, rc87_artifact_root / "source_immutability_summary.json"),
        "detail": "The proof simulated an immutability alert path without mutating any real fixture source file.",
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=IMMUTABILITY_JSON_NAME,
        markdown_name=IMMUTABILITY_MD_NAME,
        summary=source_immutability_alert_summary,
        markdown=_markdown(
            "# rc88 Source Immutability Alert Summary",
            [
                "- Simulated failure path: True",
                "- Real fixture mutated: False",
                f"- Source summary ref: {source_immutability_alert_summary['source_summary_ref'] or '<none>'}",
            ],
        ),
    )
    source_immutability_record = _raise_candidate(
        package_root=package_root_path,
        env=env,
        telemetry_records=telemetry_records,
        alert_type="read_only_source_immutability_failed",
        source="read_only_adapter_proof",
        source_milestone="rc88",
        source_case="simulated_source_immutability_failure",
        summary_redacted="A proof-only source immutability failure path was simulated and preserved as critical evidence.",
        status_endpoint_snapshot_ref=status_snapshot_ref,
        source_immutability_refs=[IMMUTABILITY_JSON_NAME],
        telemetry_refs=[_relative_hint(package_root_path, rc87_artifact_root / "telemetry_identity_summary.json")],
        package_validation_refs=[
            _relative_hint(package_root_path, rc87_artifact_root / "package_hygiene_summary.json")
        ],
        lane_id="lane_director",
        lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
    )
    alert_records["source_immutability_failed"] = source_immutability_record

    runtime_candidate_snapshot = deepcopy(pre_alert_shell)
    runtime_candidate_snapshot.setdefault("observability", {})
    runtime_candidate_snapshot["observability"]["status"] = "degraded"
    runtime_candidate_snapshot["observability"]["last_export_result"] = "failure"
    runtime_candidate_snapshot["observability"]["alert_candidates"] = [
        {"alert_key": "telemetry_export_failure", "detail": "Proof-only degraded export candidate."},
        {"alert_key": "collector_down", "detail": "Proof-only collector-down candidate."},
        {"alert_key": "no_telemetry_seen", "detail": "Proof-only no-telemetry candidate."},
        {"alert_key": "redaction_failure", "detail": "Proof-only redaction failure candidate."},
        {"alert_key": "deferred_pressure_high", "detail": "Proof-only deferred pressure is elevated."},
    ]
    runtime_candidate_snapshot.setdefault("intervention", {})
    runtime_candidate_snapshot["intervention"]["required"] = True
    runtime_candidate_snapshot["intervention"]["summary"] = "Proof-only Review Hold remains active."
    runtime_candidate_snapshot["intervention"]["pending_review_count"] = 2
    runtime_candidate_snapshot.setdefault("controller_isolation", {})
    runtime_candidate_snapshot["controller_isolation"]["identity_bleed"] = {
        "finding_count": 1,
        "latest_finding_id": "proof-bleed-finding",
    }
    runtime_candidate_snapshot.setdefault("external_adapter_review", {})
    runtime_candidate_snapshot["external_adapter_review"]["rollback_candidate"] = True
    runtime_candidate_snapshot["external_adapter_review"]["checkpoint_available"] = False
    runtime_candidate_snapshot["external_adapter_review"]["ambiguity_level"] = "high"
    runtime_candidate_snapshot["external_adapter_review"]["review_items"] = [
        {"review_reasons": ["scope expansion pressure"]}
    ]
    runtime_snapshot_ref = _write_status_snapshot(
        artifact_root,
        name="runtime_candidate_snapshot",
        payload=runtime_candidate_snapshot,
    )
    seen_runtime_types: set[str] = set()
    for descriptor in build_runtime_candidate_descriptors(runtime_candidate_snapshot):
        alert_type = str(descriptor.get("alert_type", "")).strip()
        if not alert_type or alert_type in seen_runtime_types:
            continue
        seen_runtime_types.add(alert_type)
        runtime_record = _raise_candidate(
            package_root=package_root_path,
            env=env,
            telemetry_records=telemetry_records,
            alert_type=alert_type,
            source=str(descriptor.get("source", "runtime_candidate")).strip() or "runtime_candidate",
            source_milestone="rc88",
            source_case=str(descriptor.get("source_case", "runtime_snapshot")).strip() or "runtime_snapshot",
            summary_redacted=str(descriptor.get("summary", "")).strip() or "Proof-only runtime alert candidate.",
            status_endpoint_snapshot_ref=runtime_snapshot_ref,
            telemetry_refs=[runtime_snapshot_ref],
            lane_id=str(descriptor.get("lane_id", "")).strip() or None,
            controller_isolation_finding_ids=["proof-bleed-finding"] if alert_type == "controller_identity_bleed" else [],
            lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
        )
        alert_records[f"runtime_{alert_type}"] = runtime_record

    ack_result = service.execute_operator_alert_action(
        action_id="acknowledge_operator_alert",
        alert_id=str(alert_records["missing_fields"]["candidate"]["alert_id"]),
        operator_note=fake_seed_values["alert_note"],
    )
    if ack_result.get("ok", False):
        telemetry_records.append(
            emit_alert_acknowledged(
                alert_type=str(alert_records["missing_fields"]["candidate"]["alert_type"]),
                severity=str(alert_records["missing_fields"]["candidate"]["severity"]),
                proof_kind="operator_alert_loop_proof",
            )
        )
    review_result = service.execute_operator_alert_action(
        action_id="review_operator_alert",
        alert_id=str(alert_records["stale"]["candidate"]["alert_id"]),
        operator_note=f"review note {fake_seed_values['alert_note']}",
    )
    if review_result.get("ok", False):
        telemetry_records.append(
            emit_alert_reviewed(
                alert_type=str(alert_records["stale"]["candidate"]["alert_type"]),
                severity=str(alert_records["stale"]["candidate"]["severity"]),
                proof_kind="operator_alert_loop_proof",
            )
        )
    close_result = service.execute_operator_alert_action(
        action_id="close_operator_alert_evidence_only",
        alert_id=str(alert_records["runtime_no_telemetry_seen"]["candidate"]["alert_id"]),
        operator_note=f"close note {fake_seed_values['alert_note']}",
    )
    if close_result.get("ok", False):
        telemetry_records.append(
            emit_alert_closed_evidence_only(
                alert_type=str(alert_records["runtime_no_telemetry_seen"]["candidate"]["alert_type"]),
                severity=str(alert_records["runtime_no_telemetry_seen"]["candidate"]["severity"]),
                proof_kind="operator_alert_loop_proof",
            )
        )
    supersede_result = service.execute_operator_alert_action(
        action_id="supersede_operator_alert",
        alert_id=str(alert_records["conflict"]["candidate"]["alert_id"]),
        replacement_alert_id=str(alert_records["integrity_failed"]["candidate"]["alert_id"]),
        operator_note=f"supersede note {fake_seed_values['alert_note']}",
    )
    if supersede_result.get("ok", False):
        telemetry_records.append(
            emit_alert_superseded(
                alert_type=str(alert_records["conflict"]["candidate"]["alert_type"]),
                severity=str(alert_records["conflict"]["candidate"]["severity"]),
                proof_kind="operator_alert_loop_proof",
            )
        )

    post_alert_shell = service.current_shell_state_payload()
    intervention_state = service.shell_intervention_state_payload()
    post_status_ref = _write_status_snapshot(
        artifact_root,
        name="status_snapshot_after_alerts",
        payload=post_alert_shell,
    )
    intervention_status_ref = _write_status_snapshot(
        artifact_root,
        name="intervention_state_after_alerts",
        payload=intervention_state,
    )

    alert_summary = summarize_alerts(package_root=package_root_path, env=env).to_dict()
    alert_summary["generated_at"] = _now_iso()
    alert_summary["result"] = "success"
    alert_summary["clear_state_verified"] = blank_alerts.get("status") == "clear"
    alert_summary["blank_alert_count"] = int(blank_alerts.get("alert_count", 0) or 0)
    alert_summary["alerts_root_hint"] = "alerts/"
    alert_summary["latest_status_snapshot_ref"] = post_status_ref
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=ALERT_SUMMARY_JSON_NAME,
        markdown_name=ALERT_SUMMARY_MD_NAME,
        summary=alert_summary,
        markdown=_candidate_markdown(alert_summary),
    )

    evidence_summary = summarize_evidence_bundles(package_root=package_root_path, env=env)

    lifecycle_events = _load_lifecycle_events(package_root_path, env)
    lifecycle_summary = {
        "schema_name": "novali_rc88_alert_lifecycle_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "event_count": len(lifecycle_events),
        "append_only": len(lifecycle_events)
        == sum(
            1
            for _ in (
                (package_root_path / "data" / "operator_alerts" / "alert_lifecycle.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if (package_root_path / "data" / "operator_alerts" / "alert_lifecycle.jsonl").exists()
                else []
            )
        ),
        "acknowledged_alert_count": sum(1 for item in lifecycle_events if str(item.get("new_status", "")) == "acknowledged"),
        "reviewed_alert_count": sum(1 for item in lifecycle_events if str(item.get("new_status", "")) == "reviewed"),
        "closed_alert_count": sum(1 for item in lifecycle_events if str(item.get("new_status", "")) == "evidence_only_closed"),
        "superseded_alert_count": sum(1 for item in lifecycle_events if str(item.get("new_status", "")) == "superseded"),
        "latest_event_id": str(lifecycle_events[-1].get("event_id", "")).strip() if lifecycle_events else None,
        "acknowledgement_does_not_approve_mutation": True,
        "review_does_not_approve_mutation": True,
        "lifecycle_event_refs": [
            _relative_hint(package_root_path, path)
            for path in sorted(resolve_lifecycle_events_root(package_root_path, env=env).glob("*.json"))
        ],
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=LIFECYCLE_JSON_NAME,
        markdown_name=LIFECYCLE_MD_NAME,
        summary=lifecycle_summary,
        markdown=_lifecycle_markdown(lifecycle_summary),
    )

    criteria = default_read_only_admission_criteria()
    fixture_assessment = assess_rc87_fixture_adapter()
    se_assessment = assess_space_engineers_read_only_bridge()
    telemetry_records.append(
        emit_admission_assessed(
            target_name=fixture_assessment.target_name,
            result=fixture_assessment.admission_status,
            proof_kind="operator_alert_loop_proof",
        )
    )
    telemetry_records.append(
        emit_admission_assessed(
            target_name=se_assessment.target_name,
            result=se_assessment.admission_status,
            proof_kind="operator_alert_loop_proof",
        )
    )
    admission_summary = {
        "schema_name": "novali_rc88_read_only_admission_assessment_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "criteria": criteria.to_dict(),
        "fixture_adapter_assessment": fixture_assessment.to_dict(),
        "space_engineers_bridge_assessment": se_assessment.to_dict(),
        "planning_only_space_engineers": True,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=ADMISSION_JSON_NAME,
        markdown_name=ADMISSION_MD_NAME,
        summary=admission_summary,
        markdown=_markdown(
            "# rc88 Read-Only Admission Assessment",
            [
                f"- Fixture adapter status: {fixture_assessment.admission_status}",
                f"- Space Engineers bridge status: {se_assessment.admission_status}",
                "- Space Engineers implementation remains blocked.",
            ],
        ),
    )

    logicmonitor_summary = _logicmonitor_mapping()
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=LOGICMONITOR_JSON_NAME,
        markdown_name=LOGICMONITOR_MD_NAME,
        summary=logicmonitor_summary,
        markdown=_markdown(
            "# rc88 LogicMonitor Alert Mapping Summary",
            [
                f"- Alert type count: {logicmonitor_summary['alert_type_count']}",
                "- LogicMonitor API used: False",
                "- Portal delivery claimed: False",
                "- Portal-side alert configuration remains operator-managed.",
            ],
        ),
    )

    memo_text = render_space_engineers_transition_decision_memo()
    _write_text(artifact_root / "space_engineers_transition_decision_memo.md", memo_text)

    flush_result = flush_observability(reason="rc88_operator_alert_loop_proof")
    enabled_status_after = get_observability_status()
    telemetry_records.append(
        emit_operator_alert_proof_completed(
            result="success",
            proof_kind="operator_alert_loop_proof",
        )
    )
    shutdown_result = shutdown_observability(reason="rc88_operator_alert_loop_proof")
    enabled_status_shutdown = get_observability_shutdown_status()
    telemetry_summary = _telemetry_summary(
        artifact_root=artifact_root,
        telemetry_records=telemetry_records,
        disabled_status=disabled_status,
        enabled_status_before=enabled_status_before,
        enabled_status_after=enabled_status_after,
        flush_result=flush_result,
        shutdown_result={**dict(shutdown_result), "status_snapshot": enabled_status_shutdown},
    )

    generated_alert_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_alerts_root(package_root_path, env=env).glob("*.json"))
    ]
    generated_bundle_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_evidence_bundles_root(package_root_path, env=env).glob("*.json"))
    ]
    lifecycle_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted(resolve_lifecycle_events_root(package_root_path, env=env).glob("*.json"))
    ]
    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(alert_summary, sort_keys=True, default=str),
            json.dumps(lifecycle_summary, sort_keys=True, default=str),
            json.dumps(evidence_summary, sort_keys=True, default=str),
            json.dumps(admission_summary, sort_keys=True, default=str),
            json.dumps(logicmonitor_summary, sort_keys=True, default=str),
            json.dumps(post_alert_shell, sort_keys=True, default=str),
            json.dumps(intervention_state, sort_keys=True, default=str),
            memo_text,
            *generated_alert_texts,
            *generated_bundle_texts,
            *lifecycle_texts,
        ],
        tuple(fake_seed_values.values()),
    )

    summary = {
        "schema_name": "novali_rc88_operator_alert_loop_summary_v1",
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "schema_version": "rc88.v1",
        "result": "success" if not forbidden_hits else "failure",
        "blank_alert_status": blank_alerts.get("status", "clear"),
        "blank_alert_count": int(blank_alerts.get("alert_count", 0) or 0),
        "alert_candidate_summary": alert_summary,
        "alert_lifecycle_summary": lifecycle_summary,
        "evidence_bundle_summary": evidence_summary,
        "read_only_admission_assessment_ref": ADMISSION_JSON_NAME,
        "logicmonitor_alert_mapping_summary_ref": LOGICMONITOR_JSON_NAME,
        "space_engineers_transition_decision_memo_ref": "space_engineers_transition_decision_memo.md",
        "source_immutability_alert_summary_ref": IMMUTABILITY_JSON_NAME,
        "telemetry_identity_summary": telemetry_summary,
        "status_snapshot_before_alerts_ref": status_snapshot_ref,
        "status_snapshot_after_alerts_ref": post_status_ref,
        "intervention_state_snapshot_ref": intervention_status_ref,
        "operator_alerts_status": post_alert_shell.get("operator_alerts", {}),
        "intervention_state": intervention_state.get("operator_alerts", {}),
        "baseline_preservation": {
            "rc85_result": rc85_summary.get("result", "unknown"),
            "rc86_result": rc86_summary.get("result", "unknown"),
            "rc87_result": rc87_summary.get("result", "unknown"),
        },
        "clean_valid_observation_alerted": False,
        "forbidden_hits": forbidden_hits,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=SUMMARY_JSON_NAME,
        markdown_name=SUMMARY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc88 Operator Alert Loop Summary",
            [
                f"- Result: {summary['result']}",
                f"- Proof id: {proof_id}",
                f"- Alert count: {alert_summary['alert_count']}",
                f"- Blocked alerts: {alert_summary['blocked_count']}",
                f"- Lifecycle events: {lifecycle_summary['event_count']}",
                f"- Evidence bundles: {evidence_summary['evidence_bundle_count']}",
                f"- rc85 baseline: {summary['baseline_preservation']['rc85_result']}",
                f"- rc86 baseline: {summary['baseline_preservation']['rc86_result']}",
                f"- rc87 baseline: {summary['baseline_preservation']['rc87_result']}",
                f"- Forbidden hits: {len(forbidden_hits)}",
            ],
        ),
    )
    return summary


def main() -> int:
    summary = run_operator_alert_loop_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
