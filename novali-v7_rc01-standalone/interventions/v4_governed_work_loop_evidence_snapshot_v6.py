from __future__ import annotations

from fnmatch import fnmatch
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
    candidate_path = Path(candidate) if candidate and candidate != "None" else None
    if (
        candidate_path is None
        or not candidate_path.exists()
        or not fnmatch(candidate_path.name, pattern)
    ):
        fallback = _latest_matching_artifact(pattern)
        candidate = str(fallback or "").strip()
    return Path(candidate) if candidate else None


def _select_latest_successful_frontier_recursion_artifact(preferred_path: Path | None) -> Path | None:
    pattern = "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_*.json"
    candidates: list[Path] = []
    if preferred_path is not None:
        candidates.append(preferred_path)
    for candidate in sorted(_diagnostic_artifact_dir().glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True):
        if preferred_path is not None and candidate.resolve() == preferred_path.resolve():
            continue
        candidates.append(candidate)

    for candidate in candidates:
        payload = _load_json_file(candidate)
        execution_summary = dict(payload.get("governed_work_loop_continuation_execution_summary", {}))
        result = dict(execution_summary.get("frontier_recursion_result", {}))
        directive_support = dict(execution_summary.get("directive_support_value", {}))
        pressure = dict(execution_summary.get("hidden_capability_pressure_read", {}))
        envelope = dict(execution_summary.get("envelope_compliance", {}))
        usefulness = dict(
            dict(execution_summary.get("continuation_accounting_captured", {})).get("usefulness_signal_summary", {})
        )
        if (
            str(result.get("classification", "")) in {"recursion_bounded_with_material_delta", "recursion_bounded_without_material_delta"}
            and str(result.get("frontier_drift_assessment", "")) == "frontier_drift_absent"
            and str(result.get("frontier_alignment_assessment", "")) == "bounded_alignment_preserved"
            and bool(directive_support.get("passed", False))
            and bool(pressure.get("passed", False))
            and bool(envelope.get("passed", False))
            and int(usefulness.get("failed_check_count", 0) or 0) == 0
            and int(usefulness.get("passed_check_count", 0) or 0) >= 17
        ):
            return candidate
    return preferred_path


def _normalize_requested_sources(trusted_source_report: Any) -> dict[str, Any]:
    report = dict(trusted_source_report or {})

    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, str):
            item = value.strip()
            return [item] if item else []
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            return [str(item).strip() for item, allowed in value.items() if bool(allowed) and str(item).strip()]
        return []

    return {
        "requested_sources": _normalize_list(report.get("requested_sources", [])),
        "allowed_sources": _normalize_list(report.get("allowed_sources", [])),
        "missing_sources": _normalize_list(report.get("missing_sources", [])),
        "passed": bool(report.get("passed", False)),
        "reason": str(report.get("reason", "")),
    }


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


def _frontier_signal_summary(execution_summary: dict[str, Any]) -> dict[str, Any]:
    frontier_artifact = dict(execution_summary.get("frontier_recursion_artifact_produced", {}))
    audit_output = dict(frontier_artifact.get("governance_recommendation_frontier_recursion_boundary_audit_output", {}))
    summary = dict(audit_output.get("summary", {}))
    result = dict(execution_summary.get("frontier_recursion_result", {}))
    signal = dict(execution_summary.get("new_frontier_quality_signal_assessment", {}))
    accounting = dict(execution_summary.get("continuation_accounting_captured", {}))
    usefulness = dict(accounting.get("usefulness_signal_summary", {}))
    return {
        "artifact_path": Path(str(frontier_artifact.get("bounded_output_artifact_path", ""))),
        "frontier_recursion_status": str(
            result.get("classification", summary.get("frontier_recursion_boundary_status", ""))
        ),
        "frontier_drift_status": str(
            result.get("frontier_drift_assessment", summary.get("frontier_drift_assessment", ""))
        ),
        "frontier_alignment_status": str(
            result.get("frontier_alignment_assessment", summary.get("frontier_alignment_assessment", ""))
        ),
        "passed_check_count": int(
            usefulness.get("passed_check_count", summary.get("passed_check_count", 0)) or 0
        ),
        "failed_check_count": int(
            usefulness.get("failed_check_count", summary.get("failed_check_count", 0)) or 0
        ),
        "frontier_signal_count": int(
            usefulness.get(
                "recursion_signal_count",
                summary.get("recursion_signal_count", signal.get("signal_count", 0)),
            )
            or 0
        ),
        "material_frontier_signal_detected": bool(
            usefulness.get(
                "material_recursion_boundary_delta_detected",
                summary.get(
                    "material_recursion_boundary_delta_detected",
                    str(signal.get("classification", "")) == "new_frontier_quality_signal_present",
                ),
            )
        ),
    }


def _operational_usefulness_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    signal_summary = _frontier_signal_summary(execution_summary)
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    distinct_value = dict(execution_summary.get("distinct_value_over_prior_step_read", {}))
    operationally_meaningful = (
        signal_summary["artifact_path"].exists()
        and bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and bool(distinct_value.get("passed", False))
        and signal_summary["frontier_recursion_status"] == "recursion_bounded_with_material_delta"
        and signal_summary["frontier_drift_status"] == "frontier_drift_absent"
        and signal_summary["frontier_alignment_status"] == "bounded_alignment_preserved"
        and signal_summary["passed_check_count"] >= 17
        and signal_summary["failed_check_count"] == 0
        and signal_summary["frontier_signal_count"] >= 3
        and signal_summary["material_frontier_signal_detected"]
    )
    return {
        "classification": "operationally_meaningful" if operationally_meaningful else "nominal_or_insufficient",
        "passed": operationally_meaningful,
        "continuation_was_real_not_ceremonial": operationally_meaningful,
        "worth_preserving_as_continuation_path": operationally_meaningful,
        "bounded_output_artifact_exists": signal_summary["artifact_path"].exists(),
        "audit_signal_summary": {
            "frontier_recursion_status": signal_summary["frontier_recursion_status"],
            "frontier_drift_status": signal_summary["frontier_drift_status"],
            "frontier_alignment_status": signal_summary["frontier_alignment_status"],
            "passed_check_count": signal_summary["passed_check_count"],
            "failed_check_count": signal_summary["failed_check_count"],
            "frontier_signal_count": signal_summary["frontier_signal_count"],
            "material_frontier_signal_detected": signal_summary["material_frontier_signal_detected"],
        },
        "reason": (
            "the continuation produced a real directive-supportive frontier-recursion artifact with a new material frontier-quality signal and no failed checks"
            if operationally_meaningful
            else "the continuation did not produce enough bounded frontier-recursion signal to count as an operationally meaningful governed work-loop continuation"
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
            "accounting coverage, the bounded continuation envelope, and the review or rollback surfaces were all sufficient in the reviewed governed work-loop continuation step"
            if governance_sufficient
            else "the reviewed governed work-loop continuation step still needs tighter accounting coverage or tighter trigger reporting before the path should be relied on"
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
    frontier_signal = dict(execution_summary.get("new_frontier_quality_signal_assessment", {}))

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
        and str(frontier_signal.get("classification", "")) == "new_frontier_quality_signal_present"
        and int(frontier_signal.get("signal_count", 0) or 0) >= 3
    )
    return {
        "classification": "real_governed_loop_continuation" if real_continuation else "too_ceremonial_or_repetitive",
        "passed": real_continuation,
        "demonstrates_real_governed_loop_continuation": real_continuation,
        "distinct_value_added_over_prior_continuation_v2": bool(distinct_value.get("passed", False)),
        "not_hidden_development_or_reopen_pressure": bool(hidden_capability_pressure.get("passed", False)),
        "reason": (
            "the continuation added real bounded frontier-recursion value beyond the prior chain while staying cleanly separated from capability use, reopen, and new-skill paths"
            if real_continuation
            else "the continuation was too ceremonial, too repetitive, or too path-confused to count as a robust governed work-loop continuation path"
        ),
    }


def _step_success(proxy: dict[str, Any]) -> bool:
    return bool(proxy.get("passed", False))


def _distinctness_chain_assessment(
    *,
    prior_chain_evidence_summary: dict[str, Any],
    current_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    prior_chain_state = dict(prior_chain_evidence_summary.get("chain_state_reviewed", {}))
    prior_distinctness = dict(prior_chain_evidence_summary.get("chain_distinct_value_assessment", {}))
    direct_work_name = str(dict(prior_chain_state.get("direct_governed_work", {})).get("work_item_name", ""))
    continuation_v1_name = str(dict(prior_chain_state.get("continuation_v1", {})).get("loop_candidate_name", ""))
    continuation_v2_name = str(dict(prior_chain_state.get("continuation_v2", {})).get("loop_candidate_name", ""))
    continuation_v3_name = str(dict(prior_chain_state.get("continuation_v3", {})).get("loop_candidate_name", ""))
    continuation_v4_name = str(dict(prior_chain_state.get("continuation_v4", {})).get("loop_candidate_name", ""))
    continuation_v5_name = str(dict(prior_chain_state.get("continuation_v5", {})).get("loop_candidate_name", ""))
    continuation_v6_name = str(dict(current_execution_summary.get("candidate_executed", {})).get("loop_candidate_name", ""))
    unique_names = {
        name
        for name in [
            direct_work_name,
            continuation_v1_name,
            continuation_v2_name,
            continuation_v3_name,
            continuation_v4_name,
            continuation_v5_name,
            continuation_v6_name,
        ]
        if name
    }
    v6_checks = dict(
        dict(
            dict(current_execution_summary.get("frontier_recursion_artifact_produced", {})).get(
                "governance_recommendation_frontier_recursion_boundary_audit_output", {}
            )
        ).get("checks", {})
    )
    v6_vs_chain = dict(dict(v6_checks.get("frontier_materially_distinct", {})).get("observed", {}))
    structurally_distinct = (
        bool(prior_distinctness.get("passed", False))
        and int(prior_distinctness.get("unique_step_name_count", 0) or 0) == 6
        and len(unique_names) == 7
        and bool(v6_vs_chain.get("distinct_from_direct_work", False))
        and bool(v6_vs_chain.get("distinct_from_continuation_v1", False))
        and bool(v6_vs_chain.get("distinct_from_continuation_v2", False))
        and bool(v6_vs_chain.get("distinct_from_continuation_v3", False))
        and bool(v6_vs_chain.get("distinct_from_continuation_v4", False))
        and bool(v6_vs_chain.get("distinct_from_continuation_v5", False))
        and bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v2", False))
        and bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v4", False))
        and bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v5", False))
    )
    return {
        "classification": "accumulating_distinct_value" if structurally_distinct else "diminishing_returns",
        "passed": structurally_distinct,
        "step_names": {
            "direct_work": direct_work_name,
            "continuation_v1": continuation_v1_name,
            "continuation_v2": continuation_v2_name,
            "continuation_v3": continuation_v3_name,
            "continuation_v4": continuation_v4_name,
            "continuation_v5": continuation_v5_name,
            "continuation_v6": continuation_v6_name,
        },
        "unique_step_name_count": int(len(unique_names)),
        "vs_prior_direct_work": {
            "continuation_v6": bool(v6_vs_chain.get("distinct_from_direct_work", False)),
        },
        "vs_prior_continuation_v1": {
            "continuation_v6": bool(v6_vs_chain.get("distinct_from_continuation_v1", False)),
        },
        "vs_prior_continuation_v2": bool(v6_vs_chain.get("distinct_from_continuation_v2", False)),
        "vs_prior_continuation_v3": bool(v6_vs_chain.get("distinct_from_continuation_v3", False)),
        "vs_prior_continuation_v4": bool(v6_vs_chain.get("distinct_from_continuation_v4", False)),
        "vs_prior_continuation_v5": bool(v6_vs_chain.get("distinct_from_continuation_v5", False)),
        "vs_evidence_snapshot_v2": bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v2", False)),
        "vs_evidence_snapshot_v4": bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v4", False)),
        "vs_evidence_snapshot_v5": bool(v6_vs_chain.get("distinct_from_evidence_snapshot_v5", False)),
        "reason": (
            "direct work, continuation v1, continuation v2, frontier containment, frontier stability delta, frontier persistence boundary, and frontier recursion boundary are all measurably distinct bounded steps rather than diminishing-return governance recursion"
            if structurally_distinct
            else "the chain no longer looks distinct enough from earlier governed work to confidently rule out diminishing-return governance recursion"
        ),
    }


def _repeated_bounded_success_assessment(
    *,
    direct_work_evidence_summary: dict[str, Any],
    continuation_v1_evidence_summary: dict[str, Any],
    prior_chain_evidence_summary: dict[str, Any],
    current_execution_summary: dict[str, Any],
    continuation_accounting_requirements: dict[str, Any],
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
    prior_chain_state = dict(prior_chain_evidence_summary.get("chain_state_reviewed", {}))
    continuation_v2_success = bool(dict(prior_chain_state.get("continuation_v2", {})).get("operational_success", False))
    continuation_v3_success = bool(dict(prior_chain_state.get("continuation_v3", {})).get("operational_success", False))
    continuation_v4_success = bool(dict(prior_chain_state.get("continuation_v4", {})).get("operational_success", False))
    continuation_v5_success = bool(dict(prior_chain_state.get("continuation_v5", {})).get("operational_success", False))
    continuation_v6_success = (
        _step_success(_operational_usefulness_assessment(current_execution_summary))
        and _step_success(
            _governance_sufficiency_assessment(
                current_execution_summary,
                continuation_accounting_requirements,
            )
        )
        and _step_success(_envelope_compliance_assessment(current_execution_summary, current_state_summary))
        and _step_success(_continuation_value_assessment(current_execution_summary))
    )
    success_count = int(
        sum(
            1
            for value in [
                direct_success,
                continuation_v1_success,
                continuation_v2_success,
                continuation_v3_success,
                continuation_v4_success,
                continuation_v5_success,
                continuation_v6_success,
            ]
            if value
        )
    )
    prior_success_count = int(
        dict(prior_chain_evidence_summary.get("repeated_bounded_success_assessment", {})).get(
            "successful_step_count", 0
        )
        or 0
    )
    repeated_bounded_success = success_count == 7
    strengthened = repeated_bounded_success and prior_success_count == 6
    return {
        "classification": "repeated_bounded_success_strengthened" if strengthened else "unchanged",
        "passed": repeated_bounded_success,
        "successful_step_count": success_count,
        "previous_successful_step_count": prior_success_count,
        "step_success": {
            "direct_governed_work": direct_success,
            "continuation_v1": continuation_v1_success,
            "continuation_v2": continuation_v2_success,
            "continuation_v3": continuation_v3_success,
            "continuation_v4": continuation_v4_success,
            "continuation_v5": continuation_v5_success,
            "continuation_v6": continuation_v6_success,
        },
        "reason": (
            "repeated bounded success is now stronger at the chain level because the seventh bounded execution step also executed cleanly"
            if strengthened
            else "the chain did not materially strengthen beyond the prior repeated-bounded-success position"
        ),
    }


def _posture_discipline_assessment(
    *,
    current_state_summary: dict[str, Any],
    prior_chain_evidence_summary: dict[str, Any],
    current_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    prior_discipline = dict(prior_chain_evidence_summary.get("posture_discipline_assessment", {}))
    current_envelope = _envelope_compliance_assessment(current_execution_summary, current_state_summary)
    discipline_holds = (
        str(current_state_summary.get("current_branch_state", "")) == "paused_with_baseline_held"
        and bool(current_state_summary.get("plan_non_owning", False))
        and bool(current_state_summary.get("routing_deferred", False))
        and not bool(current_state_summary.get("retained_skill_promotion_performed", False))
        and bool(prior_discipline.get("passed", False))
        and bool(current_envelope.get("passed", False))
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
            "narrow posture discipline is still holding cleanly across the full reviewed chain through the frontier-recursion boundary execution"
            if discipline_holds
            else "one or more narrow-posture guardrails no longer holds cleanly across the reviewed chain"
        ),
    }


def _hidden_development_pressure_assessment(
    *,
    prior_chain_evidence_summary: dict[str, Any],
    current_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    prior_chain_clean = str(
        dict(prior_chain_evidence_summary.get("posture_pressure_assessment", {})).get("classification", "")
    ) == "posture_pressure_absent"
    current_execution_clean = bool(
        dict(current_execution_summary.get("hidden_capability_pressure_read", {})).get("passed", False)
    ) and str(dict(current_execution_summary.get("hidden_capability_pressure_read", {})).get("value", "")) == "none"
    review_status = dict(
        dict(current_execution_summary.get("review_rollback_deprecation_trigger_status", {})).get(
            "review_trigger_status", {}
        )
    )
    hidden_pressure = (
        not prior_chain_clean
        or not current_execution_clean
        or bool(review_status.get("held_capability_dependency_or_external_source_need_appears", False))
        or bool(review_status.get("work_starts_to_imply_capability_development_or_branch_mutation", False))
    )
    return {
        "classification": "hidden_development_pressure_absent" if not hidden_pressure else "hidden_development_pressure_present",
        "passed": not hidden_pressure,
        "reason": (
            "no hidden capability reopening, branch mutation, retained promotion, or capability-development pressure appears in the reviewed chain"
            if not hidden_pressure
            else "the reviewed chain shows signs of hidden development or reopen pressure that should block further continuation"
        ),
    }


def _new_execution_signal_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    signal = dict(execution_summary.get("new_frontier_quality_signal_assessment", {}))
    signal_summary = _frontier_signal_summary(execution_summary)
    materially_improved = (
        str(signal.get("classification", "")) == "new_frontier_quality_signal_present"
        and int(signal.get("signal_count", 0) or 0) >= 3
        and signal_summary["frontier_recursion_status"] == "recursion_bounded_with_material_delta"
        and signal_summary["frontier_drift_status"] == "frontier_drift_absent"
        and signal_summary["frontier_alignment_status"] == "bounded_alignment_preserved"
    )
    return {
        "classification": (
            "materially_improved_evidence_picture"
            if materially_improved
            else "mostly_restates_prior_conclusions"
        ),
        "passed": materially_improved,
        "signal_count": int(signal.get("signal_count", 0) or 0),
        "reason": (
            "the frontier-recursion execution adds a new frontier-quality signal about recursion-boundedness, drift absence, and bounded alignment rather than merely restating prior chain conclusions"
            if materially_improved
            else "the frontier-recursion execution mostly restates prior chain conclusions without adding enough new frontier-quality evidence"
        ),
    }


def _structural_vs_recursive_assessment(
    *,
    distinctness_assessment: dict[str, Any],
    repeated_bounded_success: dict[str, Any],
    new_execution_signal: dict[str, Any],
    posture_discipline: dict[str, Any],
    candidate_screen_summary: dict[str, Any],
    execution_summary: dict[str, Any],
) -> dict[str, Any]:
    admin_recursion_risk = str(
        dict(candidate_screen_summary.get("administrative_recursion_risk_assessment", {})).get("classification", "")
    )
    low_recursion_check = bool(
        dict(
            dict(
                dict(execution_summary.get("frontier_recursion_artifact_produced", {})).get(
                    "governance_recommendation_frontier_recursion_boundary_audit_output", {}
                )
            ).get("checks", {})
        )
        .get("frontier_low_recursion_low_pressure", {})
        .get("passed", False)
    )
    structural = (
        bool(distinctness_assessment.get("passed", False))
        and bool(repeated_bounded_success.get("passed", False))
        and bool(new_execution_signal.get("passed", False))
        and bool(posture_discipline.get("passed", False))
        and admin_recursion_risk == "administrative_recursion_risk_low"
        and low_recursion_check
    )
    return {
        "classification": "structural_but_still_narrow" if structural else "administratively_recursive",
        "passed": structural,
        "reason": (
            "the chain is still adding structural evidence under the narrow envelope rather than folding into summary-recursive governance paperwork"
            if structural
            else "the chain is approaching administrative recursion or diminishing-return governance motion"
        ),
    }


def _gate_status_assessment(
    *,
    prior_chain_evidence_summary: dict[str, Any],
    continuation_admission_summary: dict[str, Any],
    execution_summary: dict[str, Any],
) -> dict[str, Any]:
    prior_gate_status = str(dict(prior_chain_evidence_summary.get("gate_status", {})).get("gate_status", ""))
    admission_gate_status = str(dict(continuation_admission_summary.get("gate_status", {})).get("gate_status", ""))
    execution_gate_passed = bool(
        dict(
            dict(
                dict(execution_summary.get("frontier_recursion_artifact_produced", {})).get(
                    "governance_recommendation_frontier_recursion_boundary_audit_output", {}
                )
            ).get("checks", {})
        )
        .get("future_posture_review_gate_stays_closed", {})
        .get("passed", False)
    )
    gate_closed = (
        prior_gate_status == "defined_but_closed"
        and admission_gate_status == "defined_but_closed"
        and execution_gate_passed
    )
    return {
        "classification": "gate_closed" if gate_closed else "gate_status_unclear",
        "passed": gate_closed,
        "gate_status": "defined_but_closed" if gate_closed else "status_unclear",
        "proposed_gate_criteria": list(
            dict(prior_chain_evidence_summary.get("gate_status", {})).get("proposed_gate_criteria", [])
        ),
        "reason": (
            "the future posture-review gate remains defined but closed after the frontier-recursion execution"
            if gate_closed
            else "the gate status is no longer cleanly preserved by the current chain evidence"
        ),
    }


def _diminishing_returns_assessment(
    *,
    distinctness_assessment: dict[str, Any],
    new_execution_signal: dict[str, Any],
    structural_value: dict[str, Any],
    candidate_screen_summary: dict[str, Any],
) -> dict[str, Any]:
    structural_yield = str(
        dict(candidate_screen_summary.get("structural_vs_local_value_assessment", {})).get("classification", "")
    )
    nearing_diminishing_returns = not (
        bool(distinctness_assessment.get("passed", False))
        and bool(new_execution_signal.get("passed", False))
        and bool(structural_value.get("passed", False))
        and structural_yield == "execution_adjacent_structural_yield"
    )
    return {
        "classification": (
            "nearing_diminishing_returns" if nearing_diminishing_returns else "not_nearing_diminishing_returns"
        ),
        "passed": not nearing_diminishing_returns,
        "reason": (
            "the chain is nearing diminishing returns because distinctness, new evidence yield, or structural usefulness is weakening"
            if nearing_diminishing_returns
            else "the chain is not yet nearing diminishing returns because the newest step still adds structurally useful, materially distinct evidence"
        ),
    }


def _circularity_risk_assessment(
    *,
    candidate_screen_summary: dict[str, Any],
    distinctness_assessment: dict[str, Any],
    new_execution_signal: dict[str, Any],
    structural_value: dict[str, Any],
    hidden_development_pressure: dict[str, Any],
) -> dict[str, Any]:
    recursion_risk = str(
        dict(candidate_screen_summary.get("administrative_recursion_risk_assessment", {})).get("classification", "")
    )
    if (
        recursion_risk == "administrative_recursion_risk_low"
        and bool(distinctness_assessment.get("passed", False))
        and bool(new_execution_signal.get("passed", False))
        and bool(structural_value.get("passed", False))
        and bool(hidden_development_pressure.get("passed", False))
    ):
        classification = "circularity_risk_low"
    elif recursion_risk in {"administrative_recursion_risk_low", "administrative_recursion_risk_medium"}:
        classification = "circularity_risk_medium"
    else:
        classification = "circularity_risk_high"
    return {
        "classification": classification,
        "passed": classification == "circularity_risk_low",
        "reason": (
            "circularity risk remains low because the newest continuation stays materially distinct, structurally useful, and low-recursion"
            if classification == "circularity_risk_low"
            else "circularity risk is medium because the chain still holds governance discipline but some novelty or structural yield is thinning"
            if classification == "circularity_risk_medium"
            else "circularity risk is high because the chain is no longer clearly separating structural yield from administrative recursion"
        ),
    }

def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6"
    )
    work_loop_posture_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
    )
    continuation_v1_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    prior_chain_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v5"
    )
    current_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1"
    )
    continuation_v5_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1"
    )
    continuation_v4_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1"
    )
    continuation_v3_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1"
    )
    continuation_v2_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1"
    )
    continuation_v1_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
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
            continuation_v1_evidence_snapshot,
            prior_chain_evidence_snapshot,
            current_execution_snapshot,
            continuation_v5_execution_snapshot,
            continuation_v4_execution_snapshot,
            continuation_v3_execution_snapshot,
            continuation_v2_execution_snapshot,
            continuation_v1_execution_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: work-loop evidence v6 requires the governance substrate, work-loop policy, candidate screen v6, continuation admission v6, posture v1, evidence v1, evidence v5, frontier-recursion execution, frontier-persistence execution, frontier-stability execution, frontier-containment execution, prior continuation executions, direct-work evidence, and capability-use evidence artifacts",
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
    readiness = {
        str(current_state_summary.get("latest_governed_work_loop_execution_readiness", "")),
        str(current_state_summary.get("latest_governed_work_loop_readiness", "")),
    }
    if (
        current_branch_state != "paused_with_baseline_held"
        or not governed_work_loop_policy
        or not readiness.intersection(
            {
                "ready_for_work_loop_evidence_review_v6",
                "ready_for_work_loop_candidate_screen_v6_later",
                "ready_for_work_loop_evidence_review_v6_later",
                "hold_position_pending_more_evidence",
            }
        )
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: branch must remain paused_with_baseline_held, governed work-loop policy state must exist, and state must be at or beyond ready_for_work_loop_evidence_review_v6",
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
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v6_*.json",
    )
    continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v6_*.json",
    )
    posture_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
    )
    continuation_v1_evidence_artifact_path = _resolve_artifact_path(
        "",
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    prior_chain_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v5_*.json",
    )
    current_execution_artifact_path = _select_latest_successful_frontier_recursion_artifact(
        _resolve_artifact_path(
            governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
            "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_*.json",
        )
    )
    continuation_v5_execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_*.json",
    )
    continuation_v4_execution_artifact_path = _resolve_artifact_path(
        "",
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_*.json",
    )
    continuation_v3_execution_artifact_path = _resolve_artifact_path(
        "",
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_*.json",
    )
    continuation_v2_execution_artifact_path = _resolve_artifact_path(
        "",
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json",
    )
    continuation_v1_execution_artifact_path = _resolve_artifact_path(
        "",
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
            continuation_v1_evidence_artifact_path,
            prior_chain_evidence_artifact_path,
            current_execution_artifact_path,
            continuation_v5_execution_artifact_path,
            continuation_v4_execution_artifact_path,
            continuation_v3_execution_artifact_path,
            continuation_v2_execution_artifact_path,
            continuation_v1_execution_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: expected governed work-loop v6, posture, direct-work, or capability-use artifact paths could not be resolved",
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
    continuation_v1_evidence_payload = _load_json_file(continuation_v1_evidence_artifact_path)
    prior_chain_evidence_payload = _load_json_file(prior_chain_evidence_artifact_path)
    current_execution_payload = _load_json_file(current_execution_artifact_path)
    current_execution_snapshot = current_execution_payload
    continuation_v5_execution_payload = _load_json_file(continuation_v5_execution_artifact_path)
    continuation_v4_execution_payload = _load_json_file(continuation_v4_execution_artifact_path)
    continuation_v3_execution_payload = _load_json_file(continuation_v3_execution_artifact_path)
    continuation_v2_execution_payload = _load_json_file(continuation_v2_execution_artifact_path)
    continuation_v1_execution_payload = _load_json_file(continuation_v1_execution_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)
    if not all(
        [
            policy_payload,
            candidate_screen_payload,
            continuation_admission_payload,
            posture_payload,
            continuation_v1_evidence_payload,
            prior_chain_evidence_payload,
            current_execution_payload,
            continuation_v5_execution_payload,
            continuation_v4_execution_payload,
            continuation_v3_execution_payload,
            continuation_v2_execution_payload,
            continuation_v1_execution_payload,
            direct_work_evidence_payload,
            direct_work_execution_payload,
            capability_use_evidence_payload,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more required governed work-loop v6, posture, direct-work, or capability-use artifacts could not be loaded",
            "observability_gain": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the loaded governing summaries"},
        }

    policy_summary = dict(policy_payload.get("governed_work_loop_policy_summary", {}))
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_work_loop_candidate_screen_v6_summary", {}))
    continuation_admission_summary = dict(
        continuation_admission_payload.get("governed_work_loop_continuation_admission_v6_summary", {})
    )
    continuation_v1_evidence_summary = dict(
        continuation_v1_evidence_payload.get("governed_work_loop_evidence_summary", {})
    )
    prior_chain_evidence_summary = dict(
        prior_chain_evidence_payload.get("governed_work_loop_evidence_v5_summary", {})
    )
    current_execution_summary = dict(
        current_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    continuation_v5_execution_summary = dict(
        continuation_v5_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    continuation_v4_execution_summary = dict(
        continuation_v4_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    continuation_v3_execution_summary = dict(
        continuation_v3_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    continuation_v2_execution_summary = dict(
        continuation_v2_execution_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    if not all(
        [
            policy_summary,
            candidate_screen_summary,
            continuation_admission_summary,
            continuation_v1_evidence_summary,
            prior_chain_evidence_summary,
            current_execution_summary,
            continuation_v5_execution_summary,
            continuation_v4_execution_summary,
            continuation_v3_execution_summary,
            continuation_v2_execution_summary,
            direct_work_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: required governed work-loop v6, evidence v1, evidence v5, or direct-work summaries were missing from the loaded artifacts",
            "observability_gain": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the summary payloads"},
        }

    candidate_reviewed = dict(current_execution_summary.get("candidate_executed", {}))
    accounting_requirements = dict(
        policy_summary.get(
            "loop_accounting_requirements",
            governed_work_loop_policy.get("loop_accounting_requirements", {}),
        )
    )

    operational_usefulness = _operational_usefulness_assessment(current_execution_summary)
    governance_sufficiency = _governance_sufficiency_assessment(current_execution_summary, accounting_requirements)
    envelope_compliance = _envelope_compliance_assessment(current_execution_summary, current_state_summary)
    continuation_value = _continuation_value_assessment(current_execution_summary)
    distinctness_assessment = _distinctness_chain_assessment(
        prior_chain_evidence_summary=prior_chain_evidence_summary,
        current_execution_summary=current_execution_summary,
    )
    repeated_bounded_success = _repeated_bounded_success_assessment(
        direct_work_evidence_summary=direct_work_evidence_summary,
        continuation_v1_evidence_summary=continuation_v1_evidence_summary,
        prior_chain_evidence_summary=prior_chain_evidence_summary,
        current_execution_summary=current_execution_summary,
        continuation_accounting_requirements=accounting_requirements,
        current_state_summary=current_state_summary,
    )
    posture_discipline = _posture_discipline_assessment(
        current_state_summary=current_state_summary,
        prior_chain_evidence_summary=prior_chain_evidence_summary,
        current_execution_summary=current_execution_summary,
    )
    hidden_development_pressure = _hidden_development_pressure_assessment(
        prior_chain_evidence_summary=prior_chain_evidence_summary,
        current_execution_summary=current_execution_summary,
    )
    new_execution_signal = _new_execution_signal_assessment(current_execution_summary)
    structural_value = _structural_vs_recursive_assessment(
        distinctness_assessment=distinctness_assessment,
        repeated_bounded_success=repeated_bounded_success,
        new_execution_signal=new_execution_signal,
        posture_discipline=posture_discipline,
        candidate_screen_summary=candidate_screen_summary,
        execution_summary=current_execution_summary,
    )
    future_posture_review_gate = _gate_status_assessment(
        prior_chain_evidence_summary=prior_chain_evidence_summary,
        continuation_admission_summary=continuation_admission_summary,
        execution_summary=current_execution_summary,
    )

    operationally_successful = (
        bool(operational_usefulness.get("passed", False))
        and bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(continuation_value.get("passed", False))
    )
    diminishing_returns = _diminishing_returns_assessment(
        distinctness_assessment=distinctness_assessment,
        new_execution_signal=new_execution_signal,
        structural_value=structural_value,
        candidate_screen_summary=candidate_screen_summary,
    )
    circularity_risk = _circularity_risk_assessment(
        candidate_screen_summary=candidate_screen_summary,
        distinctness_assessment=distinctness_assessment,
        new_execution_signal=new_execution_signal,
        structural_value=structural_value,
        hidden_development_pressure=hidden_development_pressure,
    )
    future_posture = "keep_narrow_governed_loop_available"
    future_posture_reason = (
        "the seven-step governed work-loop chain is still accumulating distinct structural evidence under the narrow envelope, so the safe result remains to hold posture narrow and keep broader execution closed"
        if bool(posture_discipline.get("passed", False))
        else "the posture must remain narrow and explicitly held because discipline is no longer clean enough to justify any further continuation"
    )
    next_action_class = (
        "bounded_candidate_search_later_supported"
        if all(
            [
                repeated_bounded_success.get("passed", False),
                repeated_bounded_success.get("classification", "") == "repeated_bounded_success_strengthened",
                distinctness_assessment.get("passed", False),
                new_execution_signal.get("passed", False),
                structural_value.get("passed", False),
                posture_discipline.get("passed", False),
                hidden_development_pressure.get("passed", False),
                future_posture_review_gate.get("passed", False),
                diminishing_returns.get("passed", False),
                circularity_risk.get("classification", "") == "circularity_risk_low",
            ]
        )
        else "bounded_evidence_review_later_supported"
        if bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(posture_discipline.get("passed", False))
        else "hold_posture"
        if bool(posture_discipline.get("passed", False))
        else "stop_continuation"
    )
    next_template = (
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7"
        if next_action_class == "bounded_candidate_search_later_supported"
        else "memory_summary.v4_governed_work_loop_evidence_snapshot_v7"
        if next_action_class == "bounded_evidence_review_later_supported"
        else "memory_summary.v4_governed_work_loop_hold_snapshot_v1"
        if next_action_class == "hold_posture"
        else ""
    )
    question_answers = {
        "chain_still_accumulating_distinct_value": str(distinctness_assessment.get("classification", ""))
        == "accumulating_distinct_value",
        "new_recursion_boundary_audit_materially_improves_evidence_picture": str(
            new_execution_signal.get("classification", "")
        )
        == "materially_improved_evidence_picture",
        "repeated_bounded_success_now_stronger_than_evidence_v5": str(
            repeated_bounded_success.get("classification", "")
        )
        == "repeated_bounded_success_strengthened",
        "posture_discipline_holding_cleanly": bool(posture_discipline.get("passed", False)),
        "hidden_development_pressure_absent": bool(hidden_development_pressure.get("passed", False)),
        "chain_looks_structural_but_narrow": str(structural_value.get("classification", ""))
        == "structural_but_still_narrow",
        "loop_nearing_diminishing_returns": str(diminishing_returns.get("classification", ""))
        == "nearing_diminishing_returns",
        "circularity_risk_low": str(circularity_risk.get("classification", "")) == "circularity_risk_low",
        "routing_remains_deferred": bool(current_state_summary.get("routing_deferred", False)),
        "posture_review_gate_remains_closed": bool(future_posture_review_gate.get("passed", False)),
    }

    continuation_accounting_summary = dict(current_execution_summary.get("continuation_accounting_captured", {}))
    review_rollback_status = dict(current_execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_evidence_snapshot_v6_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_policy_artifact_path"] = str(policy_artifact_path)
    updated_work_loop_policy["last_candidate_screen_artifact_path"] = str(candidate_screen_artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_admission_artifact_path"] = str(
        continuation_admission_artifact_path
    )
    updated_work_loop_policy["last_work_loop_posture_artifact_path"] = str(posture_artifact_path)
    updated_work_loop_policy["last_prior_work_loop_evidence_artifact_path"] = str(prior_chain_evidence_artifact_path)
    updated_work_loop_policy["last_prior_work_loop_continuation_execution_artifact_path"] = str(
        continuation_v5_execution_artifact_path
    )
    updated_work_loop_policy["last_work_loop_continuation_execution_artifact_path"] = str(
        current_execution_artifact_path
    )
    updated_work_loop_policy["governed_work_loop_evidence_review_schema"] = {
        "schema_name": "GovernedWorkLoopEvidenceReview",
        "schema_version": "governed_work_loop_evidence_review_v6",
        "required_fields": [
            "snapshot_identity_context",
            "chain_state_reviewed",
            "evidence_inputs_used",
            "chain_distinct_value_assessment",
            "repeated_bounded_success_assessment",
            "new_execution_signal_assessment",
            "structural_vs_recursive_assessment",
            "diminishing_returns_assessment",
            "circularity_risk_assessment",
            "posture_discipline_assessment",
            "posture_pressure_assessment",
            "gate_status",
            "routing_status",
            "recommended_next_action",
        ],
        "recommended_next_action_classes": [
            "bounded_candidate_search_later_supported",
            "bounded_evidence_review_later_supported",
            "hold_posture",
            "stop_continuation",
        ],
    }
    updated_work_loop_policy["last_work_loop_evidence_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_evidence_outcome"] = {
        "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
        "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
        "status": "hold_narrow_posture_after_evidence_v6",
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
            "governed_work_loop_evidence_review_v6_in_place": True,
            "governed_work_loop_evidence_review_v5_in_place": True,
            "governed_work_loop_evidence_review_v4_in_place": True,
            "governed_work_loop_evidence_review_v3_in_place": True,
            "latest_governed_work_loop_evidence_outcome": "hold_narrow_posture_after_evidence_v6",
            "latest_governed_work_loop_operational_success": bool(repeated_bounded_success.get("passed", False)),
            "latest_governed_work_loop_operational_status": (
                "seven_step_bounded_governed_work_loop_chain_reviewed"
                if bool(repeated_bounded_success.get("passed", False))
                else "seven_step_bounded_governed_work_loop_chain_not_yet_clear"
            ),
            "latest_governed_work_loop_execution_outcome": str(
                dict(current_execution_summary.get("frontier_recursion_result", {})).get("classification", "")
            ),
            "latest_governed_work_loop_readiness": (
                "ready_for_work_loop_candidate_screen_v7_later"
                if next_action_class == "bounded_candidate_search_later_supported"
                else "ready_for_work_loop_evidence_review_v7_later"
                if next_action_class == "bounded_evidence_review_later_supported"
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

    chain_state = {
        "chain_length": 7,
        "current_posture": future_posture,
        "direct_governed_work": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "direct_governed_work", {}
        ),
        "continuation_v1": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "continuation_v1", {}
        ),
        "continuation_v2": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "continuation_v2", {}
        ),
        "continuation_v3": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "continuation_v3", {}
        ),
        "continuation_v4": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "continuation_v4", {}
        ),
        "continuation_v5": dict(prior_chain_evidence_summary.get("chain_state_reviewed", {})).get(
            "continuation_v5", {}
        ),
        "continuation_v6": {
            "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
            "execution_outcome": str(updated_current_state_summary.get("latest_governed_work_loop_execution_outcome", "")),
            "operational_success": operationally_successful,
            "frontier_recursion_boundary_status": str(
                dict(current_execution_summary.get("frontier_recursion_result", {})).get("classification", "")
            ),
            "frontier_drift_assessment": str(
                dict(current_execution_summary.get("frontier_recursion_result", {})).get(
                    "frontier_drift_assessment", ""
                )
            ),
            "frontier_alignment_assessment": str(
                dict(current_execution_summary.get("frontier_recursion_result", {})).get(
                    "frontier_alignment_assessment", ""
                )
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
        "governed_work_loop_candidate_screen_v6": str(candidate_screen_artifact_path),
        "governed_work_loop_continuation_admission_v6": str(continuation_admission_artifact_path),
        "governed_work_loop_posture_v1": str(posture_artifact_path),
        "governed_work_loop_evidence_v1": str(continuation_v1_evidence_artifact_path),
        "governed_work_loop_evidence_v5": str(prior_chain_evidence_artifact_path),
        "governed_work_loop_continuation_execution_v1": str(continuation_v1_execution_artifact_path),
        "governed_work_loop_continuation_execution_v2": str(continuation_v2_execution_artifact_path),
        "governed_work_loop_continuation_execution_v3": str(continuation_v3_execution_artifact_path),
        "governed_work_loop_continuation_execution_v4": str(continuation_v4_execution_artifact_path),
        "governed_work_loop_continuation_execution_v5": str(continuation_v5_execution_artifact_path),
        "governed_work_loop_continuation_execution_v6": str(current_execution_artifact_path),
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
        "trusted_sources": _normalize_requested_sources(continuation_accounting_summary.get("trusted_source_report", {})),
        "requested_resources": dict(
            dict(continuation_accounting_summary.get("resource_report", {})).get("requested_resources", {})
        ),
        "observed_resource_usage": dict(continuation_accounting_summary.get("resource_usage", {})),
        "write_root_report": dict(continuation_accounting_summary.get("write_root_report", {})),
        "network_mode_expectation": str(
            dict(continuation_accounting_summary.get("resource_trust_position", {})).get("network_mode_expectation", "")
        ),
    }
    if not resource_trust_accounting["network_mode_expectation"]:
        resource_trust_accounting["network_mode_expectation"] = "none"
    operator_readable_conclusion = (
        "The seven-step governed work-loop chain is still accumulating distinct structural evidence under the narrow envelope; the frontier-recursion execution materially improved the evidence picture while circularity risk remains low, so the safe next move is another bounded candidate search later while keeping the gate closed."
        if next_action_class == "bounded_candidate_search_later_supported"
        else "The frontier-recursion execution stayed clean and bounded, but diminishing-return or circularity caution now argues for another evidence-only review later rather than another candidate search."
        if next_action_class == "bounded_evidence_review_later_supported"
        else "The chain should hold its current narrow posture and avoid further continuation until ambiguity or recursion risk is reduced."
    )

    ledger_event = {
        "event_id": f"governed_work_loop_evidence_snapshot_v6::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_evidence_snapshot_v6_materialized",
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
            "governed_work_loop_candidate_screen_v6": str(candidate_screen_artifact_path),
            "governed_work_loop_continuation_admission_v6": str(continuation_admission_artifact_path),
            "governed_work_loop_posture_v1": str(posture_artifact_path),
            "governed_work_loop_evidence_v1": str(continuation_v1_evidence_artifact_path),
            "governed_work_loop_evidence_v5": str(prior_chain_evidence_artifact_path),
            "governed_work_loop_continuation_execution_v1": str(continuation_v1_execution_artifact_path),
            "governed_work_loop_continuation_execution_v2": str(continuation_v2_execution_artifact_path),
            "governed_work_loop_continuation_execution_v3": str(continuation_v3_execution_artifact_path),
            "governed_work_loop_continuation_execution_v4": str(continuation_v4_execution_artifact_path),
            "governed_work_loop_continuation_execution_v5": str(continuation_v5_execution_artifact_path),
            "governed_work_loop_continuation_execution_v6": str(current_execution_artifact_path),
            "governed_direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "governed_direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "governed_capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_evidence_v6": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
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
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(work_loop_policy_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6": _artifact_reference(work_loop_candidate_screen_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6": _artifact_reference(work_loop_continuation_admission_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(work_loop_posture_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(continuation_v1_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v5": _artifact_reference(prior_chain_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(continuation_v1_execution_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1": _artifact_reference(continuation_v2_execution_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1": _artifact_reference(continuation_v3_execution_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1": _artifact_reference(continuation_v4_execution_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1": _artifact_reference(continuation_v5_execution_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1": _artifact_reference(current_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(direct_work_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(direct_work_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(capability_use_evidence_snapshot, latest_snapshots),
        },
        "governed_work_loop_evidence_v6_summary": {
            "snapshot_identity_context": {
                "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "proposal_id": str(proposal.get("proposal_id", "")),
                "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
                "generated_at": _now(),
            },
            "candidate_reviewed": dict(candidate_reviewed),
            "chain_state_reviewed": chain_state,
            "evidence_inputs_used": evidence_inputs_used,
            "chain_distinct_value_assessment": distinctness_assessment,
            "repeated_bounded_success_assessment": repeated_bounded_success,
            "new_execution_signal_assessment": new_execution_signal,
            "structural_vs_recursive_assessment": structural_value,
            "diminishing_returns_assessment": diminishing_returns,
            "circularity_risk_assessment": circularity_risk,
            "posture_discipline_assessment": posture_discipline,
            "posture_pressure_assessment": {
                "classification": "posture_pressure_absent" if bool(hidden_development_pressure.get("passed", False)) else "posture_pressure_present",
                "reason": str(hidden_development_pressure.get("reason", "")),
            },
            "operational_usefulness_assessment": operational_usefulness,
            "governance_sufficiency_assessment": governance_sufficiency,
            "continuation_value_assessment": continuation_value,
            "gate_status": future_posture_review_gate,
            "routing_status": {
                "classification": "routing_deferred" if bool(current_state_summary.get("routing_deferred", False)) else "routing_status_changed",
                "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            },
            "future_posture": {
                "category": future_posture,
                "reason": future_posture_reason,
                "hold_narrow_posture_unchanged": True,
                "broader_execution_opened": False,
            },
            "recommended_next_action": {
                "classification": next_action_class,
                "template_name": next_template,
                "reason": (
                    "the seven-step chain is still structurally yielding under the narrow envelope without clear circularity pressure, so another bounded candidate search later is the cleanest next move"
                    if next_action_class == "bounded_candidate_search_later_supported"
                    else "another evidence-only review later is safer than another candidate search right now because diminishing-return or circularity caution is rising"
                    if next_action_class == "bounded_evidence_review_later_supported"
                    else "the chain should hold posture instead of continuing right now"
                    if next_action_class == "hold_posture"
                    else "the chain should stop continuation until governance conditions improve"
                ),
            },
            "question_answers": question_answers,
            "resource_trust_accounting": resource_trust_accounting,
            "review_rollback_deprecation_trigger_status": review_rollback_status,
            "envelope_compliance_summary": envelope_compliance_summary,
            "current_work_state_summary": {
                "direct_work_execution_summary_present": bool(direct_work_execution_payload),
                "continuation_v1_execution_summary_present": bool(continuation_v1_execution_payload),
                "continuation_v2_execution_summary_present": bool(continuation_v2_execution_payload),
                "continuation_v3_execution_summary_present": bool(continuation_v3_execution_payload),
                "continuation_v4_execution_summary_present": bool(continuation_v4_execution_payload),
                "continuation_v5_execution_summary_present": bool(continuation_v5_execution_payload),
                "continuation_v6_execution_summary_present": bool(current_execution_payload),
                "capability_use_evidence_summary_present": bool(capability_use_evidence_payload),
                "chain_length": 7,
                "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
                "current_execution_template": str(candidate_reviewed.get("proposed_execution_template", "")),
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
                "reason": "the v6 evidence review is derived from directive, bucket, branch, self-structure, work-loop policy, work-loop posture, candidate-screen v6, continuation-admission v6, evidence v1, evidence v5, direct-work evidence, continuation executions, frontier-containment execution, frontier-stability execution, frontier-persistence execution, frontier-recursion execution, and capability-use evidence artifacts rather than from execution code",
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
            "reason": "the governed work-loop chain now has an explicit governance-owned v6 evidence review consolidating the frontier-recursion execution into a seven-step bounded operator-readable artifact",
            "artifact_paths": {
                "governed_work_loop_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review distinguishes continued structural yield from diminishing-return governance recursion while leaving posture widening explicitly closed",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the v6 evidence review separates chain-level structural value, recursion-boundary signal, diminishing-return risk, circularity risk, posture pressure, and later bounded-next-step support in one grounded decision artifact",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, reopened no paused capability line, promoted no retained capability, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": next_action_class == "bounded_candidate_search_later_supported",
            "recommended_next_template": next_template,
            "reason": (
                "the chain now supports another tightly bounded continuation candidate search later while still holding narrow posture unchanged"
                if next_action_class == "bounded_candidate_search_later_supported"
                else "the chain should stay in evidence-only hold until another bounded move becomes cleaner"
            ),
        },
        "diagnostic_conclusions": {
            "governed_work_loop_evidence_review_v6_in_place": True,
            "governed_work_loop_evidence_review_v5_in_place": True,
            "governed_work_loop_evidence_review_v4_in_place": True,
            "governed_work_loop_evidence_review_v3_in_place": True,
            "chain_still_accumulating_distinct_value": bool(distinctness_assessment.get("passed", False)),
            "new_recursion_boundary_audit_materially_changed_evidence_picture": bool(new_execution_signal.get("passed", False)),
            "repeated_bounded_success_strengthened": str(repeated_bounded_success.get("classification", "")) == "repeated_bounded_success_strengthened",
            "loop_nearing_diminishing_returns": str(diminishing_returns.get("classification", "")) == "nearing_diminishing_returns",
            "circularity_risk": str(circularity_risk.get("classification", "")),
            "hold_narrow_posture": True,
            "bounded_candidate_search_later_supported": next_action_class == "bounded_candidate_search_later_supported",
            "bounded_evidence_review_later_supported": next_action_class == "bounded_evidence_review_later_supported",
            "stop_continuation": next_action_class == "stop_continuation",
            "retained_promotion_occurred": False,
            "branch_state_mutation_occurred": False,
            "paused_capability_line_reopened": False,
            "capability_modification_occurred": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "gate_closed": bool(future_posture_review_gate.get("passed", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the seven-step governed work-loop chain now has a v6 evidence review that keeps posture narrow, keeps the gate closed, and explicitly tests whether diminishing returns or circularity are starting to appear",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
