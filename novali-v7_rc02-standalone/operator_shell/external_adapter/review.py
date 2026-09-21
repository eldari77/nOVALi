from __future__ import annotations

from typing import Iterable

from .schemas import AdapterReviewRequirement, ReviewHoldEscalation

ALLOWED_ACTION_TYPES = {
    "noop.observe",
    "noop.annotate",
    "noop.simulate_success",
    "noop.simulate_failure",
    "noop.simulate_uncertain",
    "noop.trigger_review",
    "noop.kill_switch_test",
}

FORBIDDEN_ACTION_TYPES = {
    "real.network_action",
    "game.server_action",
    "filesystem.mutation",
    "outbound.message",
    "account.create",
    "spaceengineers.action",
}

WARNING_REASONS = {
    "uncertain outcome",
    "non-critical review reason",
    "scope expansion pressure",
}
HIGH_REASONS = {
    "failed preconditions",
    "unknown action type",
    "forbidden action type",
    "rollback ambiguity",
    "missing replay packet",
    "replay packet write failure",
    "rollback analysis missing",
    "repeated uncertain outcomes",
    "policy conflict",
}
CRITICAL_REASONS = {
    "unsafe payload",
    "external mutation requested in rc85",
    "live external mutation requested in rc85",
    "redaction failure",
    "kill switch triggered",
    "adapter exception",
    "telemetry proof redaction mismatch",
}


def _dedupe_reasons(reasons: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        normalized = str(reason or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def build_review_requirement(
    reasons: Iterable[str] | None = None,
    *,
    default_summary: str = "No review is required for this mock adapter action.",
) -> AdapterReviewRequirement:
    deduped = _dedupe_reasons(reasons or [])
    review_required = bool(deduped)
    if review_required:
        summary = (
            "Review is required before this external-adapter action can proceed: "
            + ", ".join(deduped)
        )
        status = "review_required"
    else:
        summary = default_summary
        status = "clear"
    return AdapterReviewRequirement(
        review_required=review_required,
        review_reasons=deduped,
        review_status=status,
        summary=summary,
    )


def classify_action_request(
    action_type: str,
    *,
    preconditions_missing: Iterable[str] | None = None,
    payload_safe: bool = True,
    repeated_uncertain: bool = False,
    rollback_ambiguity: bool = False,
    missing_replay_packet: bool = False,
    replay_packet_write_failure: bool = False,
    rollback_analysis_missing: bool = False,
    kill_switch_triggered: bool = False,
    redaction_failure: bool = False,
    adapter_exception: bool = False,
    scope_expansion_pressure: bool = False,
    policy_conflict: bool = False,
    telemetry_redaction_mismatch: bool = False,
) -> AdapterReviewRequirement:
    normalized_action_type = str(action_type or "").strip()
    reasons: list[str] = []
    missing = _dedupe_reasons(preconditions_missing or [])
    if not normalized_action_type:
        reasons.append("unknown action type")
    elif normalized_action_type in FORBIDDEN_ACTION_TYPES:
        reasons.append("forbidden action type")
    elif normalized_action_type not in ALLOWED_ACTION_TYPES:
        reasons.append("unknown action type")
    if missing:
        reasons.append("missing required preconditions")
        reasons.append("failed preconditions")
    if not payload_safe:
        reasons.append("unsafe payload")
    if repeated_uncertain:
        reasons.append("repeated uncertain outcomes")
    if rollback_ambiguity:
        reasons.append("rollback ambiguity")
    if missing_replay_packet:
        reasons.append("missing replay packet")
    if replay_packet_write_failure:
        reasons.append("replay packet write failure")
    if rollback_analysis_missing:
        reasons.append("rollback analysis missing")
    if kill_switch_triggered:
        reasons.append("kill switch triggered")
    if redaction_failure:
        reasons.append("redaction failure")
    if adapter_exception:
        reasons.append("adapter exception")
    if scope_expansion_pressure:
        reasons.append("scope expansion pressure")
    if policy_conflict:
        reasons.append("policy conflict")
    if telemetry_redaction_mismatch:
        reasons.append("telemetry proof redaction mismatch")
    if normalized_action_type.startswith("real.") or normalized_action_type.startswith(
        "spaceengineers."
    ):
        reasons.append("live external mutation requested in rc85")
    return build_review_requirement(reasons)


def review_severity(review_reasons: Iterable[str] | None) -> str:
    reasons = _dedupe_reasons(review_reasons or [])
    if any(reason in CRITICAL_REASONS for reason in reasons):
        return "critical"
    if any(reason in HIGH_REASONS for reason in reasons):
        return "high"
    if reasons:
        return "warning"
    return "info"


def review_status_for_reasons(
    review_reasons: Iterable[str] | None,
    *,
    evidence_missing: bool = False,
) -> str:
    reasons = _dedupe_reasons(review_reasons or [])
    if evidence_missing or "missing replay packet" in reasons or "rollback analysis missing" in reasons:
        return "evidence_missing"
    if review_severity(reasons) in {"high", "critical"}:
        return "escalated"
    if reasons:
        return "pending_review"
    return "resolved_mock_only"


def escalation_for_review(
    review_reasons: Iterable[str] | None,
    *,
    evidence_missing: bool = False,
) -> ReviewHoldEscalation:
    reasons = _dedupe_reasons(review_reasons or [])
    severity = review_severity(reasons)
    review_status = review_status_for_reasons(reasons, evidence_missing=evidence_missing)
    operator_action_required = review_operator_action(reasons, review_status=review_status)
    return ReviewHoldEscalation(
        severity=severity,
        escalation_status=review_status,
        escalation_reasons=reasons,
        operator_action_required=operator_action_required,
    )


def review_operator_action(
    review_reasons: Iterable[str] | None,
    *,
    review_status: str = "pending_review",
) -> str:
    reasons = _dedupe_reasons(review_reasons or [])
    if review_status == "evidence_missing":
        return (
            "Inspect the replay and rollback evidence set, regenerate the missing artifact, "
            "and keep mock adapter execution paused until evidence integrity is restored."
        )
    if "live external mutation requested in rc85" in reasons:
        return (
            "Refuse the live-mutation request, keep the adapter in mock-only mode, and review "
            "the governing directive before any future adapter expansion."
        )
    if "kill switch triggered" in reasons:
        return (
            "Inspect the mock kill-switch evidence, keep adapter activity paused, and verify "
            "that no real external action was attempted."
        )
    if "rollback ambiguity" in reasons:
        return (
            "Review rollback evidence, confirm the checkpoint linkage, and resolve the ambiguity "
            "before marking the mock action understood."
        )
    if "repeated uncertain outcomes" in reasons:
        return (
            "Stop retrying uncertain mock actions, inspect the replay sequence, and record an "
            "explicit operator review outcome."
        )
    return (
        "Review the replay packet and rollback evidence before continuing; no real external-world "
        "action may proceed from this rc85 review item."
    )
