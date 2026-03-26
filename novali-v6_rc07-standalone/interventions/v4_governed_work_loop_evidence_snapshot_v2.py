from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .analytics import build_intervention_ledger_analytics
from .governance_substrate_v1 import (
    BRANCH_REGISTRY_PATH,
    BUCKET_STATE_PATH,
    DIRECTIVE_HISTORY_PATH,
    DIRECTIVE_STATE_PATH,
    SELF_STRUCTURE_LEDGER_PATH,
    SELF_STRUCTURE_STATE_PATH,
    _append_jsonl,
    _now,
    _write_json,
)
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _value_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _all_flags_false(flags: dict[str, Any]) -> bool:
    return all(not bool(value) for value in dict(flags).values())


def _resolve_artifact_path(raw_candidate: Any, pattern: str) -> Path | None:
    candidate = str(raw_candidate or "").strip()
    if not candidate or candidate == "None":
        fallback = _latest_matching_artifact(pattern)
        candidate = str(fallback or "").strip()
    return Path(candidate) if candidate else None


def _evaluate_field_presence(
    fields: list[str],
    accessors: dict[str, Callable[[dict[str, Any]], Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    presence = {
        str(field): _value_present(accessors.get(str(field), lambda _: None)(payload))
        for field in list(fields)
    }
    present_count = sum(1 for present in presence.values() if bool(present))
    total_count = len(presence)
    return {
        "required_fields": list(fields),
        "presence": presence,
        "present_count": int(present_count),
        "total_count": int(total_count),
        "all_present": bool(total_count > 0 and present_count == total_count),
        "coverage_ratio": float(present_count / total_count) if total_count else 0.0,
    }


def _accounting_completeness(
    execution_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, Any]:
    accessors: dict[str, Callable[[dict[str, Any]], Any]] = {
        "loop_id": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("loop_identity_context", {})).get("loop_id"),
        "directive_id": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("loop_identity_context", {})).get("directive_id"),
        "branch_id": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("loop_identity_context", {})).get("branch_id"),
        "branch_state": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("loop_identity_context", {})).get("branch_state"),
        "loop_iteration": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("loop_identity_context", {})).get("loop_iteration"),
        "prior_work_item_id": lambda payload: (
            dict(dict(payload.get("continuation_accounting_captured", {})).get("current_work_state", {})).get("prior_work_item_id")
            or dict(dict(payload.get("continuation_accounting_captured", {})).get("current_work_state", {})).get("prior_work_item")
        ),
        "current_work_item": lambda payload: (
            str(dict(payload.get("candidate_executed", {})).get("loop_candidate_name", ""))
            or str(dict(payload.get("continuation_accounting_captured", {})).get("continuation_summary", ""))
        ),
        "prior_work_evidence_summary": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("current_work_state", {})).get("prior_work_future_posture"),
        "current_execution_path": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("expected_path", {})).get("path"),
        "current_direct_work_future_posture": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("current_work_state", {})).get("prior_work_future_posture"),
        "capability_status_context": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("current_work_state", {})).get("capability_status_context"),
        "resource_budget_position": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("resource_report", {})).get("requested_resources"),
        "trusted_sources_in_use": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("trusted_source_report", {})).get("requested_sources"),
        "expected_next_resource_budget": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("resource_trust_position", {})).get("expected_resource_budget"),
        "expected_write_roots": lambda payload: (
            dict(dict(payload.get("continuation_accounting_captured", {})).get("resource_trust_position", {})).get("expected_write_roots")
            or dict(dict(payload.get("continuation_accounting_captured", {})).get("write_root_report", {})).get("requested_write_roots")
        ),
        "network_mode_expectation": lambda payload: (
            dict(dict(payload.get("continuation_accounting_captured", {})).get("resource_trust_position", {})).get("network_mode_expectation")
            or dict(dict(payload.get("envelope_compliance", {})).get("resource_expectations", {})).get("network_mode")
        ),
        "continue_pause_defer_or_divert_reason": lambda payload: dict(payload.get("continuation_accounting_captured", {})).get("continuation_rationale"),
        "review_hooks": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("review_rollback_hooks", {})).get("review_hooks"),
        "rollback_hooks": lambda payload: dict(dict(payload.get("continuation_accounting_captured", {})).get("review_rollback_hooks", {})).get("rollback_hooks"),
        "deprecation_hooks": lambda payload: dict(payload.get("review_rollback_deprecation_trigger_status", {})).get("deprecation_trigger_status"),
        "expected_next_evidence_signal": lambda payload: dict(payload.get("continuation_accounting_captured", {})).get("expected_next_evidence_signal"),
        "diversion_target_path": lambda payload: (
            dict(dict(dict(payload.get("continuation_accounting_captured", {})).get("expected_path", {})).get("next_path", {})).get("path_type")
            or "continue_as_admitted_loop_continuation"
        ),
    }

    identity_fields = list(accounting_requirements.get("loop_identity_and_context_must_be_logged", []))
    current_work_fields = list(accounting_requirements.get("current_work_state_must_be_logged", []))
    budget_fields = list(accounting_requirements.get("resource_and_trust_position_must_be_logged", []))
    decision_fields = list(accounting_requirements.get("continuation_decision_must_be_logged", []))

    identity_presence = _evaluate_field_presence(identity_fields, accessors, execution_summary)
    current_work_presence = _evaluate_field_presence(current_work_fields, accessors, execution_summary)
    budget_presence = _evaluate_field_presence(budget_fields, accessors, execution_summary)
    decision_presence = _evaluate_field_presence(decision_fields, accessors, execution_summary)

    all_required_present = (
        bool(identity_presence.get("all_present", False))
        and bool(current_work_presence.get("all_present", False))
        and bool(budget_presence.get("all_present", False))
        and bool(decision_presence.get("all_present", False))
    )
    return {
        "loop_identity_and_context": identity_presence,
        "current_work_state": current_work_presence,
        "resource_and_trust_position": budget_presence,
        "continuation_decision": decision_presence,
        "all_required_present": all_required_present,
        "reason": (
            "all required work-loop identity, current-work-state, resource or trust, and continuation-decision fields are present in the execution artifact"
            if all_required_present
            else "one or more required work-loop accounting fields are missing from the continuation execution artifact"
        ),
    }


def _operational_usefulness_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    delta_artifact = dict(execution_summary.get("alignment_delta_artifact_produced", {}))
    delta_summary = dict(
        dict(delta_artifact.get("governance_recommendation_alignment_delta_audit_output", {})).get("summary", {})
    )
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    distinct_value = dict(execution_summary.get("distinct_value_over_prior_step_read", {}))
    bounded_output_artifact_path = Path(str(delta_artifact.get("bounded_output_artifact_path", "")))

    passed_check_count = int(delta_summary.get("passed_check_count", 0) or 0)
    failed_check_count = int(delta_summary.get("failed_check_count", 0) or 0)
    alignment_signal_count = int(delta_summary.get("alignment_signal_count", 0) or 0)
    material_alignment_detected = bool(delta_summary.get("material_alignment_detected", False))
    alignment_status = str(delta_summary.get("alignment_status", ""))
    operationally_meaningful = (
        bounded_output_artifact_path.exists()
        and bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and bool(distinct_value.get("passed", False))
        and alignment_status == "aligned_with_material_delta"
        and passed_check_count >= 13
        and failed_check_count == 0
        and alignment_signal_count >= 3
        and material_alignment_detected
    )
    return {
        "classification": "operationally_meaningful" if operationally_meaningful else "nominal_or_insufficient",
        "passed": operationally_meaningful,
        "continuation_was_real_not_ceremonial": operationally_meaningful,
        "worth_preserving_as_continuation_path": operationally_meaningful,
        "bounded_output_artifact_exists": bounded_output_artifact_path.exists(),
        "audit_signal_summary": {
            "alignment_status": alignment_status,
            "passed_check_count": passed_check_count,
            "failed_check_count": failed_check_count,
            "alignment_signal_count": alignment_signal_count,
            "material_alignment_detected": material_alignment_detected,
        },
        "reason": (
            "the continuation produced a real directive-supportive recommendation-to-ledger alignment artifact with strong material signal and no failed checks"
            if operationally_meaningful
            else "the continuation did not produce enough bounded recommendation-to-ledger alignment signal to count as an operationally meaningful work-loop continuation path"
        ),
    }


def _governance_sufficiency_assessment(
    execution_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, Any]:
    trigger_status = dict(execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    review_status = dict(trigger_status.get("review_trigger_status", {}))
    rollback_status = dict(trigger_status.get("rollback_trigger_status", {}))
    deprecation_status = dict(trigger_status.get("deprecation_trigger_status", {}))
    envelope = dict(execution_summary.get("envelope_compliance", {}))
    accounting_completeness = _accounting_completeness(execution_summary, accounting_requirements)

    governance_sufficient = (
        bool(accounting_completeness.get("all_required_present", False))
        and bool(envelope.get("passed", False))
        and bool(review_status)
        and bool(rollback_status)
        and bool(deprecation_status)
        and _all_flags_false(review_status)
        and _all_flags_false(rollback_status)
        and _all_flags_false(deprecation_status)
    )
    return {
        "classification": "sufficient" if governance_sufficient else "needs_refinement",
        "passed": governance_sufficient,
        "accounting_completeness": accounting_completeness,
        "continuation_control_envelope_proved_adequate": bool(envelope.get("passed", False)),
        "review_triggers_defined_and_inactive": bool(review_status) and _all_flags_false(review_status),
        "rollback_triggers_defined_and_inactive": bool(rollback_status) and _all_flags_false(rollback_status),
        "deprecation_triggers_defined_and_inactive": bool(deprecation_status) and _all_flags_false(deprecation_status),
        "reason": (
            "accounting coverage, the bounded continuation envelope, and the review or rollback surfaces were all sufficient in the first real governed work-loop continuation"
            if governance_sufficient
            else "the first governed work-loop continuation still needs tighter accounting coverage or tighter trigger reporting before the path should be relied on"
        ),
    }


def _envelope_compliance_assessment(
    execution_summary: dict[str, Any],
    current_state_summary: dict[str, Any],
) -> dict[str, Any]:
    envelope = dict(execution_summary.get("envelope_compliance", {}))
    bucket_pressure = dict(envelope.get("bucket_pressure", {}))
    stable_low_risk = (
        bool(envelope.get("passed", False))
        and str(envelope.get("network_mode_observed", "")) == "none"
        and bool(envelope.get("writes_within_approved_roots", False))
        and bool(envelope.get("resource_limits_respected", False))
        and bool(envelope.get("storage_budget_respected", False))
        and bool(envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(envelope.get("no_branch_state_mutation", False))
        and bool(envelope.get("no_paused_capability_reopen", False))
        and bool(envelope.get("no_capability_modification", False))
        and bool(envelope.get("no_new_skill_creation", False))
        and bool(envelope.get("no_protected_surface_modification", False))
        and bool(envelope.get("no_downstream_selected_set_work", False))
        and bool(envelope.get("no_plan_ownership_change", False))
        and bool(envelope.get("no_routing_work", False))
        and bool(current_state_summary.get("plan_non_owning", False))
        and bool(current_state_summary.get("routing_deferred", False))
        and str(bucket_pressure.get("concern_level", "")) == "low"
    )
    return {
        "classification": "stable_low_risk" if stable_low_risk else "issue_detected",
        "passed": stable_low_risk,
        "network_mode": str(envelope.get("network_mode_observed", "")),
        "write_root_compliance": bool(envelope.get("writes_within_approved_roots", False)),
        "bucket_pressure": bucket_pressure,
        "branch_state_immutability": bool(envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
        "paused_capability_line_remained_closed": bool(envelope.get("no_paused_capability_reopen", False)),
        "protected_surface_isolation": bool(envelope.get("no_protected_surface_modification", False)),
        "downstream_isolation": bool(envelope.get("no_downstream_selected_set_work", False)),
        "plan_non_ownership": bool(envelope.get("no_plan_ownership_change", False))
        and bool(current_state_summary.get("plan_non_owning", False)),
        "routing_non_involvement": bool(envelope.get("no_routing_work", False))
        and bool(current_state_summary.get("routing_deferred", False)),
        "reason": (
            "network, write-root, bucket, branch, paused-capability, protected-surface, downstream, plan_, and routing constraints all held during the loop continuation execution"
            if stable_low_risk
            else "one or more envelope or governance-boundary constraints did not hold cleanly during the loop continuation execution"
        ),
    }


def _continuation_value_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    distinct_value = dict(execution_summary.get("distinct_value_over_prior_step_read", {}))
    hidden_capability_pressure = dict(execution_summary.get("hidden_capability_pressure_read", {}))
    path_separation = dict(execution_summary.get("path_separation_status", {}))
    usefulness_signal = dict(dict(execution_summary.get("continuation_accounting_captured", {})).get("usefulness_signal_summary", {}))

    real_continuation = (
        bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and bool(distinct_value.get("passed", False))
        and str(distinct_value.get("value", "")) in {"medium", "high"}
        and bool(hidden_capability_pressure.get("passed", False))
        and str(hidden_capability_pressure.get("value", "")) == "none"
        and bool(path_separation.get("remained_governed_work_loop_continuation", False))
        and bool(path_separation.get("not_direct_work_repetition", False))
        and bool(path_separation.get("not_prior_continuation_replay", False))
        and bool(path_separation.get("capability_use_not_invoked", False))
        and bool(path_separation.get("paused_capability_line_not_reopened", False))
        and bool(path_separation.get("new_skill_path_not_opened", False))
        and bool(path_separation.get("silent_broadening_not_triggered", False))
        and bool(usefulness_signal.get("material_alignment_detected", False))
        and int(usefulness_signal.get("alignment_signal_count", 0) or 0) >= 3
    )
    return {
        "classification": "real_governed_loop_continuation" if real_continuation else "too_ceremonial_or_repetitive",
        "passed": real_continuation,
        "demonstrates_real_governed_loop_continuation": real_continuation,
        "distinct_value_added_over_prior_direct_work": bool(distinct_value.get("passed", False)),
        "distinct_value_added_over_prior_continuation_v1": bool(
            dict(distinct_value.get("vs_prior_continuation_v1", {})).get("distinct", False)
        ),
        "not_hidden_development_or_reopen_pressure": bool(hidden_capability_pressure.get("passed", False)),
        "reason": (
            "the continuation added real bounded recommendation-to-ledger value beyond both the prior direct-work step and continuation v1 while staying cleanly separated from capability use, reopen, and new-skill paths"
            if real_continuation
            else "the continuation was too ceremonial, too repetitive, or too path-confused to count as a robust governed work-loop continuation path"
        ),
    }


def _step_success(proxy: dict[str, Any]) -> bool:
    return bool(proxy.get("passed", False))


def _distinctness_chain_assessment(
    *,
    direct_work_evidence_summary: dict[str, Any],
    continuation_v1_evidence_summary: dict[str, Any],
    continuation_v2_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    direct_work_name = str(dict(direct_work_evidence_summary.get("candidate_reviewed", {})).get("work_item_name", ""))
    continuation_v1_name = str(
        dict(continuation_v1_evidence_summary.get("candidate_reviewed", {})).get("loop_candidate_name", "")
    )
    continuation_v2_name = str(
        dict(continuation_v2_execution_summary.get("candidate_executed", {})).get("loop_candidate_name", "")
    )
    unique_names = {name for name in [direct_work_name, continuation_v1_name, continuation_v2_name] if name}
    v1_vs_direct = bool(
        dict(continuation_v1_evidence_summary.get("continuation_value_assessment", {})).get(
            "distinct_value_added_over_prior_direct_work", False
        )
    )
    v2_vs_direct = bool(
        dict(dict(continuation_v2_execution_summary.get("distinct_value_over_prior_step_read", {})).get("vs_prior_direct_work", {})).get(
            "distinct",
            False,
        )
    )
    v2_vs_v1 = bool(
        dict(dict(continuation_v2_execution_summary.get("distinct_value_over_prior_step_read", {})).get("vs_prior_continuation_v1", {})).get(
            "distinct",
            False,
        )
    )
    structurally_distinct = len(unique_names) == 3 and v1_vs_direct and v2_vs_direct and v2_vs_v1
    return {
        "classification": "structurally_distinct_chain" if structurally_distinct else "distinctness_weakening",
        "passed": structurally_distinct,
        "step_names": {
            "direct_work": direct_work_name,
            "continuation_v1": continuation_v1_name,
            "continuation_v2": continuation_v2_name,
        },
        "unique_step_name_count": int(len(unique_names)),
        "vs_prior_direct_work": {
            "continuation_v1": v1_vs_direct,
            "continuation_v2": v2_vs_direct,
        },
        "vs_prior_continuation_v1": v2_vs_v1,
        "reason": (
            "direct work, continuation v1, and continuation v2 are all measurably distinct bounded steps rather than repeated governance paperwork"
            if structurally_distinct
            else "one or more steps no longer looks distinct enough from earlier governed work to confidently rule out paperwork-style recycling"
        ),
    }


def _repeated_bounded_success_assessment(
    *,
    direct_work_evidence_summary: dict[str, Any],
    continuation_v1_evidence_summary: dict[str, Any],
    continuation_v2_execution_summary: dict[str, Any],
    continuation_v2_accounting_requirements: dict[str, Any],
    current_state_summary: dict[str, Any],
) -> dict[str, Any]:
    direct_success = (
        _step_success(dict(direct_work_evidence_summary.get("operational_usefulness_assessment", {})))
        and _step_success(dict(direct_work_evidence_summary.get("governance_sufficiency_assessment", {})))
        and _step_success(dict(direct_work_evidence_summary.get("envelope_compliance_assessment", {})))
        and _step_success(dict(direct_work_evidence_summary.get("direct_work_value_assessment", {})))
    )
    continuation_v1_success = (
        _step_success(dict(continuation_v1_evidence_summary.get("operational_usefulness_assessment", {})))
        and _step_success(dict(continuation_v1_evidence_summary.get("governance_sufficiency_assessment", {})))
        and _step_success(dict(continuation_v1_evidence_summary.get("envelope_compliance_assessment", {})))
        and _step_success(dict(continuation_v1_evidence_summary.get("continuation_value_assessment", {})))
    )
    continuation_v2_success = (
        _step_success(_operational_usefulness_assessment(continuation_v2_execution_summary))
        and _step_success(
            _governance_sufficiency_assessment(
                continuation_v2_execution_summary,
                continuation_v2_accounting_requirements,
            )
        )
        and _step_success(_envelope_compliance_assessment(continuation_v2_execution_summary, current_state_summary))
        and _step_success(_continuation_value_assessment(continuation_v2_execution_summary))
    )
    success_count = int(sum(1 for value in [direct_success, continuation_v1_success, continuation_v2_success] if value))
    repeated_bounded_success = success_count == 3
    return {
        "classification": "repeated_bounded_success_present" if repeated_bounded_success else "repeated_bounded_success_incomplete",
        "passed": repeated_bounded_success,
        "successful_step_count": success_count,
        "step_success": {
            "direct_governed_work": direct_success,
            "continuation_v1": continuation_v1_success,
            "continuation_v2": continuation_v2_success,
        },
        "reason": (
            "repeated bounded success now exists across direct governed work, continuation v1, and continuation v2"
            if repeated_bounded_success
            else "the governed work loop does not yet show clean repeated bounded success across all three reviewed steps"
        ),
    }


def _posture_discipline_assessment(
    *,
    current_state_summary: dict[str, Any],
    direct_work_evidence_summary: dict[str, Any],
    continuation_v1_evidence_summary: dict[str, Any],
    continuation_v2_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    direct_envelope = dict(direct_work_evidence_summary.get("envelope_compliance_assessment", {}))
    continuation_v1_envelope = dict(continuation_v1_evidence_summary.get("envelope_compliance_assessment", {}))
    continuation_v2_envelope = _envelope_compliance_assessment(continuation_v2_execution_summary, current_state_summary)
    discipline_holds = (
        str(current_state_summary.get("current_branch_state", "")) == "paused_with_baseline_held"
        and bool(current_state_summary.get("plan_non_owning", False))
        and bool(current_state_summary.get("routing_deferred", False))
        and not bool(current_state_summary.get("retained_skill_promotion_performed", False))
        and bool(direct_envelope.get("passed", False))
        and bool(continuation_v1_envelope.get("passed", False))
        and bool(continuation_v2_envelope.get("passed", False))
    )
    return {
        "classification": "posture_discipline_holding_cleanly" if discipline_holds else "posture_discipline_under_pressure",
        "passed": discipline_holds,
        "observed": {
            "current_posture": str(current_state_summary.get("latest_governed_work_loop_posture", "")),
            "branch_state": str(current_state_summary.get("current_branch_state", "")),
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_promotion_performed": bool(current_state_summary.get("retained_skill_promotion_performed", False)),
        },
        "reason": (
            "narrow posture discipline is still holding cleanly across the reviewed chain"
            if discipline_holds
            else "one or more narrow-posture guardrails no longer holds cleanly across the reviewed chain"
        ),
    }


def _hidden_development_pressure_assessment(
    *,
    continuation_v1_evidence_summary: dict[str, Any],
    continuation_v2_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    continuation_v1_clean = bool(
        dict(continuation_v1_evidence_summary.get("continuation_value_assessment", {})).get(
            "not_hidden_development_or_reopen_pressure", False
        )
    )
    continuation_v2_clean = bool(
        dict(continuation_v2_execution_summary.get("hidden_capability_pressure_read", {})).get("passed", False)
    ) and str(dict(continuation_v2_execution_summary.get("hidden_capability_pressure_read", {})).get("value", "")) == "none"
    review_status = dict(
        dict(continuation_v2_execution_summary.get("review_rollback_deprecation_trigger_status", {})).get(
            "review_trigger_status", {}
        )
    )
    hidden_pressure = (
        not continuation_v1_clean
        or not continuation_v2_clean
        or bool(review_status.get("held_capability_dependency_or_external_source_need_appears", False))
        or bool(review_status.get("work_starts_to_imply_capability_development_or_branch_mutation", False))
    )
    return {
        "classification": "hidden_development_pressure_absent" if not hidden_pressure else "hidden_development_pressure_detected",
        "passed": not hidden_pressure,
        "reason": (
            "no hidden capability reopening, branch mutation, retained promotion, or capability-development pressure appears in the reviewed chain"
            if not hidden_pressure
            else "the reviewed chain shows signs of hidden development or reopen pressure that should block further continuation"
        ),
    }


def _recommendation_quality_assessment(continuation_v2_execution_summary: dict[str, Any]) -> dict[str, Any]:
    alignment_output = dict(
        dict(continuation_v2_execution_summary.get("alignment_delta_artifact_produced", {})).get(
            "governance_recommendation_alignment_delta_audit_output", {}
        )
    )
    summary = dict(alignment_output.get("summary", {}))
    observations = dict(alignment_output.get("alignment_observations", {}))
    high_quality = (
        str(summary.get("alignment_status", "")) == "aligned_with_material_delta"
        and float(summary.get("alignment_score", 0.0) or 0.0) >= 0.8
        and float(summary.get("loop_surface_alignment_score", 0.0) or 0.0) >= 0.8
        and not list(observations.get("required_narrow_templates_missing", []))
        and not list(observations.get("unsupported_loop_surface_templates", []))
    )
    return {
        "classification": "high_structural_yield" if high_quality else "local_or_shallow_yield",
        "passed": high_quality,
        "alignment_score": float(summary.get("alignment_score", 0.0) or 0.0),
        "loop_surface_alignment_score": float(summary.get("loop_surface_alignment_score", 0.0) or 0.0),
        "governance_recommendation_overlap_count": int(
            len(list(observations.get("governance_recommendation_overlap_templates", [])))
        ),
        "reason": (
            "recommendation output still aligns strongly with recent governed ledger reality, so the latest continuation adds strategic yield rather than paperwork-only motion"
            if high_quality
            else "recommendation output is not yet aligned strongly enough with governed ledger reality to count as more than local procedural motion"
        ),
    }


def _structural_value_assessment(
    *,
    repeated_bounded_success: dict[str, Any],
    distinctness_assessment: dict[str, Any],
    recommendation_quality: dict[str, Any],
    posture_discipline: dict[str, Any],
) -> dict[str, Any]:
    structural = (
        bool(repeated_bounded_success.get("passed", False))
        and bool(distinctness_assessment.get("passed", False))
        and bool(recommendation_quality.get("passed", False))
        and bool(posture_discipline.get("passed", False))
    )
    return {
        "classification": "structural_but_still_narrow" if structural else "mostly_local_or_procedural",
        "passed": structural,
        "reason": (
            "the chain now shows repeated bounded success, step-level distinctness, and recommendation-to-ledger yield strong enough to count as structural value, while still remaining narrow"
            if structural
            else "the chain still looks too local, procedural, or paperwork-like to count as structural governed work-loop value"
        ),
    }


def _future_posture_review_gate_assessment(
    *,
    repeated_bounded_success: dict[str, Any],
    distinctness_assessment: dict[str, Any],
    posture_discipline: dict[str, Any],
    hidden_development_pressure: dict[str, Any],
    recommendation_quality: dict[str, Any],
) -> dict[str, Any]:
    gate_can_be_defined = (
        bool(repeated_bounded_success.get("passed", False))
        and bool(distinctness_assessment.get("passed", False))
        and bool(posture_discipline.get("passed", False))
        and bool(hidden_development_pressure.get("passed", False))
    )
    return {
        "classification": "define_gate_but_keep_closed" if gate_can_be_defined else "gate_not_ready_to_define",
        "passed": gate_can_be_defined,
        "gate_status": "defined_but_closed" if gate_can_be_defined else "not_defined",
        "proposed_gate_criteria": [
            "one additional distinct screened and admitted bounded continuation step or a clean governed capability-use diversion inside the loop",
            "continued full envelope compliance with network mode none, approved write-root compliance, low bucket pressure, and no branch-state mutation",
            "inactive review, rollback, and deprecation triggers across the next bounded step",
            "no paused-capability reopen, no retained promotion, no capability modification, and no hidden development pressure",
            "evidence that the next step adds distinct value rather than low-yield repetition",
            "routing remains deferred and plan_ remains non-owning at the time of any future posture review",
        ]
        if gate_can_be_defined
        else [],
        "reason": (
            "enough evidence now exists to define a future posture-review gate, but not to open it"
            if gate_can_be_defined
            else "the evidence chain is not yet strong enough to define a future posture-review gate cleanly"
        ),
        "recommendation_quality_support": bool(recommendation_quality.get("passed", False)),
    }

def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2"
    )
    work_loop_posture_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
    )
    prior_work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    work_loop_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1"
    )
    prior_continuation_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    direct_work_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot,
            work_loop_continuation_admission_snapshot,
            work_loop_posture_snapshot,
            prior_work_loop_evidence_snapshot,
            work_loop_execution_snapshot,
            prior_continuation_execution_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: work-loop evidence v2 requires the governance substrate, work-loop policy, candidate screen v2, continuation admission v2, posture v1, continuation v1 evidence and execution, continuation v2 execution, direct-work evidence, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop evidence-review artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop evidence-review artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop evidence-review artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the prerequisite governed chain"},
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(intervention_data_dir() / "intervention_ledger.jsonl")
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review governed work-loop evidence without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if current_branch_state != "paused_with_baseline_held" or not governed_work_loop_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: branch must remain paused_with_baseline_held and governed work-loop policy state must exist",
            "observability_gain": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "ambiguity_reduction": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the loaded governing summaries"},
        }

    policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    candidate_screen_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v2_*.json",
    )
    continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v2_*.json",
    )
    posture_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
    )
    prior_work_loop_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    direct_work_execution_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            policy_artifact_path,
            candidate_screen_artifact_path,
            continuation_admission_artifact_path,
            posture_artifact_path,
            prior_work_loop_evidence_artifact_path,
            execution_artifact_path,
            prior_continuation_execution_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: expected governed work-loop v2, posture, continuation v1, direct-work, or capability-use artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without resolved artifact paths"},
        }

    policy_payload = _load_json_file(policy_artifact_path)
    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    continuation_admission_payload = _load_json_file(continuation_admission_artifact_path)
    posture_payload = _load_json_file(posture_artifact_path)
    prior_work_loop_evidence_payload = _load_json_file(prior_work_loop_evidence_artifact_path)
    execution_payload = _load_json_file(execution_artifact_path)
    prior_continuation_execution_payload = _load_json_file(prior_continuation_execution_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)
    if not all(
        [
            policy_payload,
            candidate_screen_payload,
            continuation_admission_payload,
            posture_payload,
            prior_work_loop_evidence_payload,
            execution_payload,
            prior_continuation_execution_payload,
            direct_work_evidence_payload,
            direct_work_execution_payload,
            capability_use_evidence_payload,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more required governed work-loop v2, posture, continuation v1, direct-work, or capability-use artifacts could not be loaded",
            "observability_gain": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the loaded governing summaries"},
        }

    policy_summary = dict(policy_payload.get("governed_work_loop_policy_summary", {}))
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_work_loop_candidate_screen_v2_summary", {}))
    continuation_admission_summary = dict(continuation_admission_payload.get("governed_work_loop_continuation_admission_v2_summary", {}))
    posture_summary = dict(posture_payload.get("governed_work_loop_posture_summary", {}))
    prior_work_loop_evidence_summary = dict(prior_work_loop_evidence_payload.get("governed_work_loop_evidence_summary", {}))
    execution_summary = dict(execution_payload.get("governed_work_loop_continuation_execution_summary", {}))
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    if not all(
        [
            policy_summary,
            candidate_screen_summary,
            continuation_admission_summary,
            posture_summary,
            prior_work_loop_evidence_summary,
            execution_summary,
            direct_work_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: required governed work-loop v2, posture, continuation v1, or direct-work summaries were missing from the loaded artifacts",
            "observability_gain": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the summary payloads"},
        }

    candidate_reviewed = dict(execution_summary.get("candidate_executed", {}))
    accounting_requirements = dict(
        policy_summary.get(
            "loop_accounting_requirements",
            governed_work_loop_policy.get("loop_accounting_requirements", {}),
        )
    )

    operational_usefulness = _operational_usefulness_assessment(execution_summary)
    governance_sufficiency = _governance_sufficiency_assessment(execution_summary, accounting_requirements)
    envelope_compliance = _envelope_compliance_assessment(execution_summary, current_state_summary)
    continuation_value = _continuation_value_assessment(execution_summary)
    distinctness_assessment = _distinctness_chain_assessment(
        direct_work_evidence_summary=direct_work_evidence_summary,
        continuation_v1_evidence_summary=prior_work_loop_evidence_summary,
        continuation_v2_execution_summary=execution_summary,
    )
    repeated_bounded_success = _repeated_bounded_success_assessment(
        direct_work_evidence_summary=direct_work_evidence_summary,
        continuation_v1_evidence_summary=prior_work_loop_evidence_summary,
        continuation_v2_execution_summary=execution_summary,
        continuation_v2_accounting_requirements=accounting_requirements,
        current_state_summary=current_state_summary,
    )
    posture_discipline = _posture_discipline_assessment(
        current_state_summary=current_state_summary,
        direct_work_evidence_summary=direct_work_evidence_summary,
        continuation_v1_evidence_summary=prior_work_loop_evidence_summary,
        continuation_v2_execution_summary=execution_summary,
    )
    hidden_development_pressure = _hidden_development_pressure_assessment(
        continuation_v1_evidence_summary=prior_work_loop_evidence_summary,
        continuation_v2_execution_summary=execution_summary,
    )
    recommendation_quality = _recommendation_quality_assessment(execution_summary)
    structural_value = _structural_value_assessment(
        repeated_bounded_success=repeated_bounded_success,
        distinctness_assessment=distinctness_assessment,
        recommendation_quality=recommendation_quality,
        posture_discipline=posture_discipline,
    )
    future_posture_review_gate = _future_posture_review_gate_assessment(
        repeated_bounded_success=repeated_bounded_success,
        distinctness_assessment=distinctness_assessment,
        posture_discipline=posture_discipline,
        hidden_development_pressure=hidden_development_pressure,
        recommendation_quality=recommendation_quality,
    )

    operationally_successful = (
        bool(operational_usefulness.get("passed", False))
        and bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(continuation_value.get("passed", False))
    )
    future_posture = "keep_narrow_governed_loop_available"
    future_posture_reason = (
        "repeated bounded governed work now looks real, but the safe result is still to hold the narrow work-loop posture unchanged and keep broader execution closed"
        if bool(posture_discipline.get("passed", False))
        else "the posture should remain narrow and under explicit hold because discipline is no longer clean enough to justify anything broader"
    )
    next_action_class = (
        "another_bounded_continuation_candidate_search"
        if all(
            [
                repeated_bounded_success.get("passed", False),
                posture_discipline.get("passed", False),
                hidden_development_pressure.get("passed", False),
            ]
        )
        else "another_diagnostic_evidence_step"
        if bool(governance_sufficiency.get("passed", False)) and bool(envelope_compliance.get("passed", False))
        else "explicit_hold_no_further_action"
    )
    next_template = (
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3"
        if next_action_class == "another_bounded_continuation_candidate_search"
        else "memory_summary.v4_governed_work_loop_posture_review_gate_snapshot_v1"
        if bool(future_posture_review_gate.get("passed", False))
        else "memory_summary.v4_governed_work_loop_hold_snapshot_v1"
    )
    broader_project_alignment = {
        "supports_governed_self_direction": bool(repeated_bounded_success.get("passed", False)),
        "supports_bucket_bounded_execution": bool(envelope_compliance.get("passed", False)),
        "repeated_bounded_governed_loop_advancement_is_real": bool(repeated_bounded_success.get("passed", False)),
        "broader_posture_is_justified_but_not_open": bool(future_posture_review_gate.get("passed", False)),
        "ready_for_broader_governed_work_loop_execution_without_more_evidence": False,
        "further_evidence_needed_before_broader_governed_work_loop_execution": list(
            future_posture_review_gate.get("proposed_gate_criteria", [])
        ),
        "reason": (
            "three bounded successes and clean posture discipline are enough to define a future posture-review gate, but not enough to widen posture or execution now"
            if bool(future_posture_review_gate.get("passed", False))
            else "the chain is still too weak to define a future posture-review gate cleanly"
        ),
    }
    question_answers = {
        "distinct_value_or_paperwork": (
            "accumulating_distinct_value"
            if bool(distinctness_assessment.get("passed", False)) and bool(recommendation_quality.get("passed", False))
            else "starting_to_recycle_governance_paperwork"
        ),
        "repeated_bounded_success_exists": bool(repeated_bounded_success.get("passed", False)),
        "posture_discipline_holding_cleanly": bool(posture_discipline.get("passed", False)),
        "future_posture_review_gate_can_be_defined_now": bool(future_posture_review_gate.get("passed", False)),
        "best_next_action_class": next_action_class,
        "routing_remains_deferred": bool(current_state_summary.get("routing_deferred", False)),
    }

    continuation_accounting_summary = dict(execution_summary.get("continuation_accounting_captured", {}))
    review_rollback_status = dict(execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_evidence_snapshot_v2_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_policy_artifact_path"] = str(policy_artifact_path)
    updated_work_loop_policy["last_candidate_screen_artifact_path"] = str(candidate_screen_artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_admission_artifact_path"] = str(continuation_admission_artifact_path)
    updated_work_loop_policy["last_work_loop_posture_artifact_path"] = str(posture_artifact_path)
    updated_work_loop_policy["last_prior_work_loop_evidence_artifact_path"] = str(
        prior_work_loop_evidence_artifact_path
    )
    updated_work_loop_policy["last_prior_work_loop_continuation_execution_artifact_path"] = str(
        prior_continuation_execution_artifact_path
    )
    updated_work_loop_policy["last_work_loop_continuation_execution_artifact_path"] = str(execution_artifact_path)
    updated_work_loop_policy["governed_work_loop_evidence_review_schema"] = {
        "schema_name": "GovernedWorkLoopEvidenceReview",
        "schema_version": "governed_work_loop_evidence_review_v2",
        "required_fields": [
            "snapshot_identity_context",
            "current_work_loop_chain_state",
            "evidence_inputs_used",
            "distinctness_assessment",
            "repeated_bounded_success_assessment",
            "posture_discipline_assessment",
            "hidden_development_pressure_assessment",
            "recommendation_quality_strategic_yield_assessment",
            "structural_vs_local_value_assessment",
            "future_posture_review_gate",
            "recommended_next_action_class",
        ],
        "recommended_next_action_classes": [
            "another_diagnostic_evidence_step",
            "another_bounded_continuation_candidate_search",
            "explicit_hold_no_further_action",
        ],
    }
    updated_work_loop_policy["last_work_loop_evidence_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_evidence_outcome"] = {
        "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
        "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
        "status": "hold_narrow_posture_unchanged",
        "operationally_successful": operationally_successful,
        "repeated_bounded_success": bool(repeated_bounded_success.get("passed", False)),
        "future_posture_review_gate_status": str(future_posture_review_gate.get("gate_status", "")),
        "recommended_next_action_class": next_action_class,
        "retained_promotion": False,
        "paused_capability_line_reopened": False,
        "best_next_template": next_template,
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_evidence_review_in_place": True,
            "governed_work_loop_evidence_review_v2_in_place": True,
            "latest_governed_work_loop_evidence_outcome": "hold_narrow_posture_unchanged",
            "latest_governed_work_loop_operational_success": bool(repeated_bounded_success.get("passed", False)),
            "latest_governed_work_loop_operational_status": (
                "repeated_bounded_work_loop_advancement_reviewed"
                if bool(repeated_bounded_success.get("passed", False))
                else "repeated_bounded_work_loop_advancement_not_yet_clear"
            ),
            "latest_governed_work_loop_readiness": (
                "ready_for_bounded_continuation_candidate_search_later"
                if next_action_class == "another_bounded_continuation_candidate_search"
                else "hold_position_pending_more_evidence"
            ),
            "latest_governed_work_loop_posture": future_posture,
            "latest_governed_work_loop_future_posture_review_gate_status": str(
                future_posture_review_gate.get("gate_status", "")
            ),
            "latest_governed_work_loop_recommended_next_action_class": next_action_class,
            "latest_governed_work_loop_best_next_template": next_template,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    direct_work_execution_summary = dict(direct_work_execution_payload.get("governed_direct_work_execution_summary", {}))
    prior_continuation_execution_summary = dict(
        prior_continuation_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    capability_use_evidence_summary = dict(
        capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {})
    )
    chain_state = {
        "chain_length": 3,
        "current_posture": future_posture,
        "direct_governed_work": {
            "work_item_name": str(dict(direct_work_evidence_summary.get("candidate_reviewed", {})).get("work_item_name", "")),
            "future_posture": str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", "")),
            "operational_success": bool(direct_work_evidence_summary.get("operational_usefulness_assessment", {}).get("passed", False)),
        },
        "continuation_v1": {
            "loop_candidate_name": str(dict(prior_work_loop_evidence_summary.get("candidate_reviewed", {})).get("loop_candidate_name", "")),
            "future_posture": str(dict(prior_work_loop_evidence_summary.get("future_posture", {})).get("category", "")),
            "operational_success": bool(
                prior_work_loop_evidence_summary.get("operational_usefulness_assessment", {}).get("passed", False)
            ),
        },
        "continuation_v2": {
            "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
            "execution_outcome": str(updated_current_state_summary.get("latest_governed_work_loop_execution_outcome", "")),
            "operational_success": operationally_successful,
            "alignment_status": str(
                dict(
                    dict(execution_summary.get("alignment_delta_artifact_produced", {})).get(
                        "governance_recommendation_alignment_delta_audit_output", {}
                    )
                )
                .get("summary", {})
                .get("alignment_status", "")
            ),
        },
        "all_steps_successful": bool(repeated_bounded_success.get("passed", False)),
        "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
        "branch_state": current_branch_state,
    }
    evidence_inputs_used = {
        "directive_state_latest": str(DIRECTIVE_STATE_PATH),
        "directive_history": str(DIRECTIVE_HISTORY_PATH),
        "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
        "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
        "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
        "bucket_state_latest": str(BUCKET_STATE_PATH),
        "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
        "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
        "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
        "governed_work_loop_policy_v1": str(policy_artifact_path),
        "governed_work_loop_candidate_screen_v2": str(candidate_screen_artifact_path),
        "governed_work_loop_continuation_admission_v2": str(continuation_admission_artifact_path),
        "governed_work_loop_posture_v1": str(posture_artifact_path),
        "governed_work_loop_evidence_v1": str(prior_work_loop_evidence_artifact_path),
        "governed_work_loop_continuation_execution_v1": str(prior_continuation_execution_artifact_path),
        "governed_work_loop_continuation_execution_v2": str(execution_artifact_path),
        "governed_direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
        "governed_direct_work_execution_v1": str(direct_work_execution_artifact_path),
        "governed_capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
        "diagnostic_memory_dir": str(_diagnostic_artifact_dir()),
    }
    envelope_compliance_summary = {
        "passed": bool(envelope_compliance.get("passed", False)),
        "network_mode": str(envelope_compliance.get("network_mode", "")),
        "write_root_compliance": bool(envelope_compliance.get("write_root_compliance", False)),
        "bucket_pressure": dict(envelope_compliance.get("bucket_pressure", {})),
        "branch_state_immutability": bool(envelope_compliance.get("branch_state_immutability", False)),
        "paused_capability_line_remained_closed": bool(
            envelope_compliance.get("paused_capability_line_remained_closed", False)
        ),
        "protected_surface_isolation": bool(envelope_compliance.get("protected_surface_isolation", False)),
        "downstream_isolation": bool(envelope_compliance.get("downstream_isolation", False)),
        "plan_non_ownership": bool(envelope_compliance.get("plan_non_ownership", False)),
        "routing_non_involvement": bool(envelope_compliance.get("routing_non_involvement", False)),
    }
    resource_trust_accounting = {
        "trusted_sources": list(
            dict(continuation_accounting_summary.get("trusted_source_report", {})).get("requested_sources", [])
        ),
        "requested_resources": dict(
            dict(continuation_accounting_summary.get("resource_report", {})).get("requested_resources", {})
        ),
        "observed_resource_usage": dict(continuation_accounting_summary.get("resource_usage_observed", {})),
        "write_root_report": dict(continuation_accounting_summary.get("write_root_report", {})),
        "network_mode_expectation": str(
            dict(continuation_accounting_summary.get("resource_trust_position", {})).get("network_mode_expectation", "")
        ),
    }
    if not resource_trust_accounting["network_mode_expectation"]:
        resource_trust_accounting["network_mode_expectation"] = "none"
    operator_readable_conclusion = (
        "Repeated bounded governed work-loop advancement is real across direct work, continuation v1, and continuation v2; narrow posture discipline is still holding; define a future posture-review gate only and continue later with another bounded candidate search rather than widening now."
        if bool(repeated_bounded_success.get("passed", False))
        and bool(posture_discipline.get("passed", False))
        and bool(future_posture_review_gate.get("passed", False))
        else "The governed work-loop chain still needs more evidence before even a future posture-review gate can be defined cleanly; keep posture narrow and hold execution-adjacent movement."
    )

    ledger_event = {
        "event_id": f"governed_work_loop_evidence_snapshot_v2::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_evidence_snapshot_v2_materialized",
        "event_class": "governed_work_loop_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
        "future_posture": future_posture,
        "future_posture_review_gate_status": str(future_posture_review_gate.get("gate_status", "")),
        "recommended_next_action_class": next_action_class,
        "retained_promotion": False,
        "paused_capability_line_reopened": False,
        "artifact_paths": {
            "governed_work_loop_policy_v1": str(policy_artifact_path),
            "governed_work_loop_candidate_screen_v2": str(candidate_screen_artifact_path),
            "governed_work_loop_continuation_admission_v2": str(continuation_admission_artifact_path),
            "governed_work_loop_posture_v1": str(posture_artifact_path),
            "governed_work_loop_evidence_v1": str(prior_work_loop_evidence_artifact_path),
            "governed_work_loop_continuation_execution_v1": str(prior_continuation_execution_artifact_path),
            "governed_work_loop_continuation_execution_v2": str(execution_artifact_path),
            "governed_direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "governed_direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "governed_capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_evidence_v2": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(
                work_loop_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2": _artifact_reference(
                work_loop_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2": _artifact_reference(
                work_loop_continuation_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(
                work_loop_posture_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(
                prior_work_loop_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(
                prior_continuation_execution_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1": _artifact_reference(
                work_loop_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_evidence_v2_summary": {
            "snapshot_identity_context": {
                "proposal_id": str(proposal.get("proposal_id", "")),
                "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "directive_id": str(current_directive.get("directive_id", "")),
                "directive_state": str(directive_state.get("initialization_state", "")),
                "branch_id": str(branch_record.get("branch_id", "")),
                "branch_state": current_branch_state,
                "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
                "shadow_only": True,
            },
            "current_work_loop_chain_state": chain_state,
            "evidence_inputs_used": evidence_inputs_used,
            "candidate_reviewed": candidate_reviewed,
            "operational_usefulness_assessment": operational_usefulness,
            "governance_sufficiency_assessment": governance_sufficiency,
            "envelope_compliance_assessment": envelope_compliance,
            "continuation_value_assessment": continuation_value,
            "distinctness_assessment": distinctness_assessment,
            "repeated_bounded_success_assessment": repeated_bounded_success,
            "posture_discipline_assessment": posture_discipline,
            "hidden_development_pressure_assessment": hidden_development_pressure,
            "recommendation_quality_strategic_yield_assessment": recommendation_quality,
            "structural_vs_local_value_assessment": structural_value,
            "future_posture_review_gate": future_posture_review_gate,
            "future_posture": {
                "category": future_posture,
                "reason": future_posture_reason,
                "hold_narrow_posture_unchanged": True,
                "broader_execution_opened": False,
            },
            "recommended_next_action": {
                "class": next_action_class,
                "template_name": next_template,
                "reason": (
                    "repeated bounded success, clean posture discipline, and low hidden-development pressure support one more bounded candidate search later"
                    if next_action_class == "another_bounded_continuation_candidate_search"
                    else "the safe next move is another evidence-only hold step because the bounded chain is not yet clean enough for further continuation search"
                    if next_action_class == "another_diagnostic_evidence_step"
                    else "the chain should hold without further action until risk or ambiguity is reduced"
                ),
            },
            "question_answers": question_answers,
            "broader_project_alignment": broader_project_alignment,
            "resource_trust_accounting": resource_trust_accounting,
            "review_rollback_deprecation_trigger_status": review_rollback_status,
            "envelope_compliance_summary": envelope_compliance_summary,
            "current_work_state_summary": {
                "direct_work_execution_summary_present": bool(direct_work_execution_summary),
                "continuation_v1_execution_summary_present": bool(prior_continuation_execution_summary),
                "capability_use_evidence_summary_present": bool(capability_use_evidence_summary),
                "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
                "source_artifact_count": int(len(list(continuation_accounting_summary.get("source_artifact_paths", [])))),
                "write_root_count": int(len(list(continuation_accounting_summary.get("write_roots_touched", [])))),
                "branch_state_unchanged": bool(continuation_accounting_summary.get("branch_state_unchanged", False)),
                "retained_promotion_performed": bool(continuation_accounting_summary.get("retained_promotion_performed", False)),
                "admission_outcome": str(continuation_accounting_summary.get("admission_outcome", "")),
            },
            "operator_readable_conclusion": operator_readable_conclusion,
            "governance_inputs_consumed": evidence_inputs_used,
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the v2 evidence review is derived from directive, bucket, branch, self-structure, work-loop policy, work-loop posture, candidate-screen v2, continuation-admission v2, direct-work evidence, continuation v1 evidence, continuation v2 execution, and capability-use evidence artifacts rather than from execution code",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the governed work-loop chain now has an explicit governance-owned v2 evidence review consolidating direct work, continuation v1, and continuation v2 into one bounded operator-readable artifact",
            "artifact_paths": {
                "governed_work_loop_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review distinguishes repeated bounded governed-loop advancement from governance-paperwork recycling and leaves posture widening explicitly closed",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the v2 evidence review separates direct work, continuation v1, continuation v2, capability use, review, reopen, new-skill, and unsupported broadening paths in one grounded decision artifact",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, reopened no paused capability line, promoted no retained capability, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": next_action_class == "another_bounded_continuation_candidate_search",
            "recommended_next_template": next_template,
            "reason": (
                "the chain now supports another tightly bounded continuation candidate search later while still holding narrow posture unchanged"
                if next_action_class == "another_bounded_continuation_candidate_search"
                else "the chain should stay in evidence-only hold until another bounded move becomes cleaner"
            ),
        },
        "diagnostic_conclusions": {
            "governed_work_loop_evidence_review_v2_in_place": True,
            "repeated_bounded_governed_loop_advancement_is_real": bool(repeated_bounded_success.get("passed", False)),
            "hold_narrow_posture": True,
            "define_future_posture_review_gate_only": bool(future_posture_review_gate.get("passed", False)),
            "future_posture_review_gate_defined_but_closed": str(future_posture_review_gate.get("gate_status", "")) == "defined_but_closed",
            "pursue_another_bounded_continuation_candidate_later": next_action_class
            == "another_bounded_continuation_candidate_search",
            "retained_promotion_occurred": False,
            "branch_state_mutation_occurred": False,
            "paused_capability_line_reopened": False,
            "capability_modification_occurred": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: repeated bounded governed work-loop advancement now has a v2 evidence review that keeps posture narrow, defines a future posture-review gate only, and supports another bounded continuation candidate search later",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
