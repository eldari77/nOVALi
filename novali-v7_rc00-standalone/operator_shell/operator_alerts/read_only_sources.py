from __future__ import annotations

import hashlib
from typing import Any, Mapping

from operator_shell.observability.redaction import redact_value

from .schemas import OperatorAlertCandidate

ALERT_TITLES = {
    "read_only_schema_missing_field": "Read-only snapshot missing required field",
    "read_only_schema_invalid": "Read-only snapshot schema invalid",
    "read_only_conflicting_observation": "Conflicting read-only observation detected",
    "read_only_stale_snapshot": "Read-only snapshot is stale",
    "read_only_wrong_lane_attribution": "Read-only observation attributed to the wrong lane",
    "read_only_mutation_requested": "Read-only adapter mutation request refused",
    "read_only_forbidden_domain_term": "Forbidden domain term detected in read-only snapshot",
    "read_only_secret_detected": "Secret-like content detected in read-only snapshot",
    "read_only_replay_missing": "Read-only observation replay evidence missing",
    "read_only_rollback_ambiguity": "Read-only rollback evidence is ambiguous",
    "read_only_source_immutability_failed": "Read-only source immutability check failed",
    "read_only_integrity_failed": "Read-only evidence integrity failed",
    "controller_identity_bleed": "Controller isolation identity bleed detected",
    "telemetry_shutdown_timeout": "Telemetry shutdown timed out",
    "telemetry_export_degraded": "Telemetry export appears degraded",
    "telemetry_export_unavailable": "Telemetry exporter unavailable",
    "telemetry_unexpected_shutdown_exception": "Telemetry shutdown exception captured",
    "no_telemetry_seen": "No telemetry has been observed",
    "collector_down_candidate": "Collector-down candidate detected",
    "review_hold_active": "Review Hold is active",
    "repeated_review_hold": "Repeated Review Hold activity detected",
    "checkpoint_failure": "Checkpoint failure candidate detected",
    "rollback_loop_candidate": "Rollback-loop candidate detected",
    "redaction_failure": "Redaction failure candidate detected",
    "scope_expansion_pressure": "Scope expansion pressure detected",
    "se_transition_blocked": "Space Engineers transition remains blocked",
}

WARNING_TYPES = {
    "read_only_stale_snapshot",
    "telemetry_shutdown_timeout",
    "telemetry_export_degraded",
    "telemetry_export_unavailable",
    "no_telemetry_seen",
    "collector_down_candidate",
    "review_hold_active",
    "repeated_review_hold",
    "checkpoint_failure",
    "rollback_loop_candidate",
    "scope_expansion_pressure",
}
HIGH_TYPES = {
    "read_only_schema_missing_field",
    "read_only_schema_invalid",
    "read_only_conflicting_observation",
    "read_only_wrong_lane_attribution",
    "read_only_replay_missing",
    "read_only_rollback_ambiguity",
    "read_only_integrity_failed",
    "controller_identity_bleed",
    "telemetry_unexpected_shutdown_exception",
}
CRITICAL_TYPES = {
    "read_only_mutation_requested",
    "read_only_forbidden_domain_term",
    "read_only_secret_detected",
    "read_only_source_immutability_failed",
    "redaction_failure",
    "se_transition_blocked",
}


def severity_for_alert_type(alert_type: str) -> str:
    normalized = str(alert_type or "").strip()
    if normalized in CRITICAL_TYPES:
        return "critical"
    if normalized in HIGH_TYPES:
        return "high"
    if normalized in WARNING_TYPES:
        return "warning"
    return "info"


def status_for_alert_type(alert_type: str) -> str:
    return "blocked_waiting_operator" if severity_for_alert_type(alert_type) == "critical" else "raised"


def operator_action_for_alert_type(alert_type: str) -> str:
    normalized = str(alert_type or "").strip()
    if normalized == "read_only_mutation_requested":
        return "Acknowledge the refusal, keep the adapter read-only, and review the linked replay and review evidence."
    if normalized == "read_only_forbidden_domain_term":
        return "Inspect the bounded evidence, keep the fixture path non-SE, and preserve the failed evidence for review."
    if normalized == "read_only_secret_detected":
        return "Treat the evidence as contaminated, preserve the artifact, and clear the secret-like content before any further proof run."
    if normalized == "read_only_source_immutability_failed":
        return "Inspect the immutability evidence immediately; source mutation remains blocked."
    if normalized == "controller_identity_bleed":
        return "Inspect the linked controller-isolation findings and keep lane activity inactive until the bleed evidence is reviewed."
    if normalized == "telemetry_export_degraded":
        return "Inspect local observability evidence and verify export degradation without treating telemetry as authority."
    if normalized == "telemetry_shutdown_timeout":
        return "Review the bounded shutdown evidence and keep telemetry timeout handling evidence-only; timeout alone does not authorize or block work."
    if normalized == "telemetry_export_unavailable":
        return "Verify exporter availability through local evidence only; unavailable telemetry does not change controller authority."
    if normalized == "telemetry_unexpected_shutdown_exception":
        return "Inspect the redacted shutdown exception evidence and preserve the degraded path for operator review."
    if normalized == "review_hold_active":
        return "Review the linked Review Hold evidence; acknowledgement does not approve any action."
    if normalized == "se_transition_blocked":
        return "Keep Space Engineers implementation blocked; planning eligibility requires explicit later operator approval."
    return "Inspect the linked evidence bundle and record operator acknowledgement or review without approving mutation."


def build_alert_candidate(
    *,
    alert_type: str,
    source: str,
    source_milestone: str,
    summary_redacted: str,
    evidence_bundle_id: str,
    replay_packet_ids: list[str] | None = None,
    review_ticket_ids: list[str] | None = None,
    rollback_analysis_ids: list[str] | None = None,
    mutation_refusal_ids: list[str] | None = None,
    source_immutability_ref: str | None = None,
    lane_id: str | None = None,
    controller_isolation_finding_ids: list[str] | None = None,
    telemetry_trace_hint: str | None = None,
    lm_dimension_hints: list[str] | None = None,
    acknowledgement_required: bool = True,
    created_at: str,
    updated_at: str,
) -> OperatorAlertCandidate:
    digest = hashlib.sha1(
        "|".join(
            [
                alert_type,
                source,
                source_milestone,
                evidence_bundle_id,
                str(lane_id or ""),
                summary_redacted,
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return OperatorAlertCandidate(
        alert_id=f"operator-alert-{digest}",
        alert_type=alert_type,
        source=source,
        source_milestone=source_milestone,
        severity=severity_for_alert_type(alert_type),
        status=status_for_alert_type(alert_type),
        title=ALERT_TITLES.get(alert_type, "Operator alert candidate"),
        summary_redacted=str(redact_value(summary_redacted, key="summary_redacted") or ""),
        operator_action_required=operator_action_for_alert_type(alert_type),
        created_at=created_at,
        updated_at=updated_at,
        evidence_bundle_id=evidence_bundle_id,
        replay_packet_ids=list(replay_packet_ids or []),
        review_ticket_ids=list(review_ticket_ids or []),
        rollback_analysis_ids=list(rollback_analysis_ids or []),
        mutation_refusal_ids=list(mutation_refusal_ids or []),
        source_immutability_ref=str(source_immutability_ref or "").strip() or None,
        lane_id=str(lane_id or "").strip() or None,
        controller_isolation_finding_ids=list(controller_isolation_finding_ids or []),
        telemetry_trace_hint=str(telemetry_trace_hint or "").strip() or None,
        lm_dimension_hints=list(lm_dimension_hints or []),
        acknowledgement_required=bool(acknowledgement_required),
    )


def build_runtime_candidate_descriptors(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    observability = dict(snapshot.get("observability", {}))
    intervention = dict(snapshot.get("intervention", {}))
    controller_isolation = dict(snapshot.get("controller_isolation", {}))
    if str(observability.get("status", "")).strip() == "degraded" or str(
        observability.get("last_export_result", "")
    ).strip() == "failure":
        descriptors.append(
            {
                "alert_type": "telemetry_export_degraded",
                "source": "observability",
                "source_case": "local_observability_status",
                "summary": "Observability export degraded in the local shell status.",
                "lane_id": None,
            }
        )
    for candidate in list(observability.get("alert_candidates", []) or []):
        key = str(dict(candidate).get("alert_key", "")).strip()
        if key == "telemetry_export_failure":
            descriptors.append(
                {
                    "alert_type": "telemetry_export_degraded",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(dict(candidate).get("detail", "") or "Telemetry export degradation candidate detected."),
                    "lane_id": None,
                }
            )
        elif key == "telemetry_shutdown_timeout":
            descriptors.append(
                {
                    "alert_type": "telemetry_shutdown_timeout",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(
                        dict(candidate).get("detail", "")
                        or "Telemetry shutdown timeout candidate detected."
                    ),
                    "lane_id": None,
                }
            )
        elif key == "telemetry_export_unavailable":
            descriptors.append(
                {
                    "alert_type": "telemetry_export_unavailable",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(
                        dict(candidate).get("detail", "")
                        or "Telemetry exporter unavailable candidate detected."
                    ),
                    "lane_id": None,
                }
            )
        elif key == "telemetry_unexpected_shutdown_exception":
            descriptors.append(
                {
                    "alert_type": "telemetry_unexpected_shutdown_exception",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(
                        dict(candidate).get("detail", "")
                        or "Telemetry shutdown exception candidate detected."
                    ),
                    "lane_id": None,
                }
            )
        elif key == "collector_down":
            descriptors.append(
                {
                    "alert_type": "collector_down_candidate",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(dict(candidate).get("detail", "") or "Collector-down candidate detected."),
                    "lane_id": None,
                }
            )
        elif key == "no_telemetry_seen":
            descriptors.append(
                {
                    "alert_type": "no_telemetry_seen",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(dict(candidate).get("detail", "") or "No telemetry seen candidate detected."),
                    "lane_id": None,
                }
            )
        elif key == "redaction_failure":
            descriptors.append(
                {
                    "alert_type": "redaction_failure",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(dict(candidate).get("detail", "") or "Redaction failure candidate detected."),
                    "lane_id": None,
                }
            )
        elif key in {"deferred_pressure_high", "deferred_pressure_worsening"}:
            descriptors.append(
                {
                    "alert_type": "scope_expansion_pressure",
                    "source": "runtime_candidate",
                    "source_case": "observability_alert_candidate",
                    "summary": str(dict(candidate).get("detail", "") or "Scope expansion pressure candidate detected."),
                    "lane_id": None,
                }
            )
    if bool(intervention.get("required", False)):
        descriptors.append(
            {
                "alert_type": "review_hold_active",
                "source": "runtime_candidate",
                "source_case": "intervention_summary",
                "summary": str(
                    intervention.get("summary", "")
                    or "Review Hold is active in the current operator snapshot."
                ),
                "lane_id": None,
            }
        )
        if int(intervention.get("pending_review_count", 0) or 0) > 1:
            descriptors.append(
                {
                    "alert_type": "repeated_review_hold",
                    "source": "runtime_candidate",
                    "source_case": "intervention_summary",
                    "summary": "Repeated Review Hold pressure is present in the local review queue.",
                "lane_id": None,
            }
        )
    external_adapter_review = dict(snapshot.get("external_adapter_review", {}))
    if bool(external_adapter_review.get("rollback_candidate", False)) and not bool(
        external_adapter_review.get("checkpoint_available", True)
    ):
        descriptors.append(
            {
                "alert_type": "checkpoint_failure",
                "source": "external_adapter_review",
                "source_case": "rollback_checkpoint_status",
                "summary": "Rollback or replay evidence is present without a checkpoint being available.",
                "lane_id": None,
            }
        )
    if str(external_adapter_review.get("ambiguity_level", "")).strip().lower() in {"high", "critical"}:
        descriptors.append(
            {
                "alert_type": "rollback_loop_candidate",
                "source": "external_adapter_review",
                "source_case": "rollback_ambiguity_status",
                "summary": "Rollback ambiguity remains elevated and needs operator review before the evidence loop is considered stable.",
                "lane_id": None,
            }
        )
    review_items = list(external_adapter_review.get("review_items", []) or [])
    if any(
        "scope expansion pressure" in str(reason or "").strip().lower()
        or "scope_expansion_pressure" in str(reason or "").strip().lower()
        for item in review_items
        for reason in list(dict(item or {}).get("review_reasons", []) or [])
    ):
        descriptors.append(
            {
                "alert_type": "scope_expansion_pressure",
                "source": "external_adapter_review",
                "source_case": "review_reasons",
                "summary": "Scope expansion pressure is visible in bounded review evidence.",
                "lane_id": None,
            }
        )
    bleed = dict(controller_isolation.get("identity_bleed", {}))
    if int(bleed.get("finding_count", 0) or 0) > 0:
        descriptors.append(
            {
                "alert_type": "controller_identity_bleed",
                "source": "controller_isolation",
                "source_case": "identity_bleed_summary",
                "summary": "Controller isolation findings remain present in the operator snapshot.",
                "lane_id": None,
            }
        )
    return descriptors
