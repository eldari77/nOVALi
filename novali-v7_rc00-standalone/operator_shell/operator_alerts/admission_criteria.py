from __future__ import annotations

from datetime import datetime, timezone

from operator_shell.observability.redaction import redact_value

from .schemas import (
    ReadOnlyAdapterAdmissionAssessment,
    ReadOnlyAdapterAdmissionCriteria,
    SpaceEngineersTransitionDecisionMemo,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def default_read_only_admission_criteria() -> ReadOnlyAdapterAdmissionCriteria:
    checks = {
        "adapter_is_read_only_by_construction": True,
        "mutation_methods_fail_closed": True,
        "no_outbound_network_without_approval": True,
        "credential_handling_plan_required": True,
        "no_credentials_in_artifacts": True,
        "schema_validation_required": True,
        "observation_integrity_validation_required": True,
        "source_auditability_or_immutability_required": True,
        "replay_packets_required": True,
        "review_tickets_required": True,
        "rollback_recovery_evidence_required": True,
        "lane_attribution_required": True,
        "wrong_lane_detection_required": True,
        "identity_bleed_check_required": True,
        "telemetry_dimensions_defined": True,
        "redaction_proof_required": True,
        "package_hygiene_required": True,
        "fresh_unpack_proof_required": True,
        "operator_alert_loop_integration_required": True,
        "logicmonitor_mapping_optional_evidence_only": True,
        "space_engineers_behavior_requires_separate_approval": True,
    }
    notes = [
        "Admission criteria are gates, not implementation approval.",
        "LogicMonitor mapping is optional and remains evidence-only.",
        "Space Engineers behavior remains blocked unless explicitly approved later.",
    ]
    return ReadOnlyAdapterAdmissionCriteria(
        criteria_id="read_only_adapter_admission_criteria_rc88",
        criteria_label="Read-only external adapter admission criteria",
        checks=checks,
        notes=notes,
    )


def assess_rc87_fixture_adapter() -> ReadOnlyAdapterAdmissionAssessment:
    criteria = default_read_only_admission_criteria()
    satisfied = [key for key, value in criteria.checks.items() if value]
    summary = "The rc87 static fixture adapter is read-only by construction and remains admissible only for read-only sandbox proof work."
    rationale = (
        "It reads local static fixtures only, refuses mutation, writes replay/review/rollback evidence, "
        "supports lane attribution, passes redaction and package hygiene, and integrates with the local operator alert loop."
    )
    return ReadOnlyAdapterAdmissionAssessment(
        assessment_id="admission-assessment-rc87-fixture-adapter",
        target_name="static_fixture_read_only",
        target_kind="read_only_fixture",
        assessment_scope="current_rc87_fixture_adapter",
        admission_status="admissible_for_read_only_sandbox",
        summary_redacted=str(redact_value(summary, key="summary_redacted") or ""),
        rationale_redacted=str(redact_value(rationale, key="rationale_redacted") or ""),
        satisfied_checks=satisfied,
        blocked_checks=[],
        planning_only=False,
        operator_action_required=(
            "Keep the adapter local/static/read-only; any future connector still requires separate admission review."
        ),
        created_at=_now_iso(),
    )


def assess_space_engineers_read_only_bridge() -> ReadOnlyAdapterAdmissionAssessment:
    blocked_checks = [
        "space_engineers_behavior_requires_separate_approval",
        "no_outbound_network_without_approval",
        "credential_handling_plan_required",
        "operator_alert_loop_integration_required",
    ]
    summary = "A hypothetical Space Engineers read-only bridge remains blocked for implementation in rc88."
    rationale = (
        "rc88 only establishes planning gates. No Space Engineers code, bridge, server connector, or active implementation is authorized here."
    )
    return ReadOnlyAdapterAdmissionAssessment(
        assessment_id="admission-assessment-space-engineers-read-only-bridge",
        target_name="space_engineers_read_only_bridge",
        target_kind="hypothetical_future_connector",
        assessment_scope="planning_only_transition_gate",
        admission_status="blocked",
        summary_redacted=str(redact_value(summary, key="summary_redacted") or ""),
        rationale_redacted=str(redact_value(rationale, key="rationale_redacted") or ""),
        satisfied_checks=[],
        blocked_checks=blocked_checks,
        planning_only=True,
        operator_action_required=(
            "Keep implementation blocked; only later operator-approved planning may reopen this gate."
        ),
        created_at=_now_iso(),
    )


def build_space_engineers_transition_decision_memo() -> SpaceEngineersTransitionDecisionMemo:
    return SpaceEngineersTransitionDecisionMemo(
        memo_id="rc88-space-engineers-transition-decision",
        recommendation="Planning eligibility only; implementation remains blocked pending separate explicit operator approval.",
        implementation_blocked=True,
        planning_only=True,
        completed_gates=[
            "OTEL and LogicMonitor proof path established",
            "Processor and redaction policy coverage in place",
            "Replay ledger and rollback review evidence in place",
            "Dual-controller isolation primitives complete",
            "Generic non-SE read-only adapter proof complete",
            "Local operator alert loop proof complete after rc88",
        ],
        blocked_work=[
            "No Space Engineers code or bridge implementation",
            "No dedicated server bridge or mod/plugin",
            "No game-world mutation",
            "No sovereign behavior activation",
            "No Season Director activation",
        ],
        decision_options=[
            "Option A: continue generic adapter hardening",
            "Option B: begin Space Engineers read-only bridge planning only",
            "Option C: begin Space Engineers read-only bridge implementation later after separate operator approval",
        ],
        created_at=_now_iso(),
    )


def render_space_engineers_transition_decision_memo() -> str:
    memo = build_space_engineers_transition_decision_memo()
    lines = [
        "# rc88 Space Engineers Transition Decision Memo",
        "",
        "This memo does not activate Space Engineers implementation.",
        "",
        "## Completed Readiness Gates",
        *[f"- {item}" for item in memo.completed_gates],
        "",
        "## Remaining Blocked Work",
        *[f"- {item}" for item in memo.blocked_work],
        "",
        "## Decision Options",
        *[f"- {item}" for item in memo.decision_options],
        "",
        "## Recommendation",
        memo.recommendation,
        "",
        "## Admission Reminder",
        "Any later Space Engineers read-only bridge implementation prompt must separately satisfy read-only admission criteria and explicit operator approval. rc88 keeps implementation blocked.",
    ]
    return "\n".join(lines) + "\n"
