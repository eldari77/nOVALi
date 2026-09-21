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
    delta_artifact = dict(execution_summary.get("delta_audit_artifact_produced", {}))
    delta_summary = dict(dict(delta_artifact.get("governance_ledger_delta_audit_output", {})).get("summary", {}))
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    distinct_value = dict(execution_summary.get("distinct_value_over_prior_step_read", {}))
    bounded_output_artifact_path = Path(str(delta_artifact.get("bounded_output_artifact_path", "")))

    passed_check_count = int(delta_summary.get("passed_check_count", 0) or 0)
    failed_check_count = int(delta_summary.get("failed_check_count", 0) or 0)
    delta_signal_count = int(delta_summary.get("delta_signal_count", 0) or 0)
    material_delta_detected = bool(delta_summary.get("material_delta_detected", False))
    alignment_status = str(delta_summary.get("alignment_status", ""))
    operationally_meaningful = (
        bounded_output_artifact_path.exists()
        and bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and bool(distinct_value.get("passed", False))
        and alignment_status == "coherent_with_material_delta"
        and passed_check_count >= 11
        and failed_check_count == 0
        and delta_signal_count >= 1
        and material_delta_detected
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
            "delta_signal_count": delta_signal_count,
            "material_delta_detected": material_delta_detected,
        },
        "reason": (
            "the continuation produced a real directive-supportive delta-audit artifact with coherent material progression and no failed checks"
            if operationally_meaningful
            else "the continuation did not produce enough bounded governance-ledger delta signal to count as an operationally meaningful work-loop continuation path"
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
        and bool(path_separation.get("capability_use_not_invoked", False))
        and bool(path_separation.get("paused_capability_line_not_reopened", False))
        and bool(path_separation.get("new_skill_path_not_opened", False))
        and bool(usefulness_signal.get("material_delta_detected", False))
        and int(usefulness_signal.get("delta_signal_count", 0) or 0) >= 1
    )
    return {
        "classification": "real_governed_loop_continuation" if real_continuation else "too_ceremonial_or_repetitive",
        "passed": real_continuation,
        "demonstrates_real_governed_loop_continuation": real_continuation,
        "distinct_value_added_over_prior_direct_work": bool(distinct_value.get("passed", False)),
        "not_hidden_development_or_reopen_pressure": bool(hidden_capability_pressure.get("passed", False)),
        "reason": (
            "the continuation added real bounded governance-ledger value beyond the prior direct-work step while staying cleanly separated from capability use, reopen, and new-skill paths"
            if real_continuation
            else "the continuation was too ceremonial, too repetitive, or too path-confused to count as a robust governed work-loop continuation path"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1"
    )
    work_loop_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    direct_work_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot,
            work_loop_continuation_admission_snapshot,
            work_loop_execution_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: work-loop evidence review requires the governance substrate, work-loop policy, candidate screen, continuation admission, continuation execution, and prior direct-work evidence artifacts",
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
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v1_*.json",
    )
    continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v1_*.json",
    )
    execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
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
    if not all(
        [
            policy_artifact_path,
            candidate_screen_artifact_path,
            continuation_admission_artifact_path,
            execution_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: expected governed work-loop and direct-work artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without resolved artifact paths"},
        }

    policy_payload = _load_json_file(policy_artifact_path)
    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    continuation_admission_payload = _load_json_file(continuation_admission_artifact_path)
    execution_payload = _load_json_file(execution_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    if not all(
        [
            policy_payload,
            candidate_screen_payload,
            continuation_admission_payload,
            execution_payload,
            direct_work_evidence_payload,
            direct_work_execution_payload,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more required governed work-loop or direct-work artifacts could not be loaded",
            "observability_gain": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review work-loop evidence without the loaded governing summaries"},
        }

    execution_summary = dict(execution_payload.get("governed_work_loop_continuation_execution_summary", {}))
    policy_summary = dict(policy_payload.get("governed_work_loop_policy_summary", {}))
    continuation_admission_summary = dict(continuation_admission_payload.get("governed_work_loop_continuation_admission_summary", {}))
    if not execution_summary or not policy_summary or not continuation_admission_summary:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: required governed work-loop summaries were missing from the loaded artifacts",
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

    operationally_successful = (
        bool(operational_usefulness.get("passed", False))
        and bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(continuation_value.get("passed", False))
    )
    if operationally_successful:
        future_posture = "keep_available_but_narrow"
        future_posture_reason = (
            "the first real governed work-loop continuation was operationally meaningful and well-governed, so the path should remain available, but only one bounded continuation case exists so it should stay narrow rather than broaden automatically"
        )
    elif bool(governance_sufficiency.get("passed", False)) and bool(envelope_compliance.get("passed", False)):
        future_posture = "keep_available_with_review_only"
        future_posture_reason = (
            "the continuation path remains safe enough to preserve, but the operational signal is not yet strong enough to keep available without tighter review"
        )
    else:
        future_posture = "pause_loop_continuation_pending_better_case"
        future_posture_reason = (
            "the first governed work-loop continuation did not produce enough combined operational and governance signal to keep the continuation path active without refinement"
        )

    broader_work_loop_posture_ready = operationally_successful
    next_template = (
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
        if broader_work_loop_posture_ready
        else "memory_summary.v4_governed_work_loop_continuation_refinement_snapshot_v1"
    )
    broader_project_alignment = {
        "supports_governed_self_direction": operationally_successful,
        "supports_bucket_bounded_execution": bool(envelope_compliance.get("passed", False)),
        "provides_real_base_for_broader_governed_work_loop_posture": broader_work_loop_posture_ready,
        "ready_for_broader_governed_work_loop_posture_layer": broader_work_loop_posture_ready,
        "ready_for_broader_governed_work_loop_execution_without_more_evidence": False,
        "more_continuation_refinement_needed_before_broader_execution": not broader_work_loop_posture_ready,
        "further_evidence_needed_before_broader_governed_work_loop_execution": [
            "at least one more distinct screened and admitted loop step or governed capability-use diversion inside the loop",
            "continued full envelope compliance and inactive review, rollback, and deprecation triggers across another loop step",
            "evidence that the loop can continue without collapsing into low-yield repetition, hidden development pressure, or silent broadening",
        ],
        "reason": (
            "the first governed work-loop continuation proves that bounded continuation can run operationally under governance, which is enough to justify defining a broader governed work-loop posture layer next"
            if broader_work_loop_posture_ready
            else "the first governed work-loop continuation still needs refinement before it should anchor a broader governed work-loop posture layer"
        ),
    }

    continuation_accounting_summary = dict(execution_summary.get("continuation_accounting_captured", {}))
    review_rollback_status = dict(execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_evidence_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_policy_artifact_path"] = str(policy_artifact_path)
    updated_work_loop_policy["last_candidate_screen_artifact_path"] = str(candidate_screen_artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_admission_artifact_path"] = str(continuation_admission_artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_execution_artifact_path"] = str(execution_artifact_path)
    updated_work_loop_policy["governed_work_loop_evidence_review_schema"] = {
        "schema_name": "GovernedWorkLoopEvidenceReview",
        "schema_version": "governed_work_loop_evidence_review_v1",
        "required_fields": [
            "loop_candidate_id",
            "loop_candidate_name",
            "operational_usefulness_assessment",
            "governance_sufficiency_assessment",
            "envelope_compliance_assessment",
            "continuation_value_assessment",
            "future_posture",
            "broader_governed_work_loop_posture_readiness",
        ],
        "future_posture_classes": [
            "keep_available_for_governed_loop_continuation",
            "keep_available_but_narrow",
            "keep_available_with_review_only",
            "pause_loop_continuation_pending_better_case",
        ],
    }
    updated_work_loop_policy["last_work_loop_evidence_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_evidence_outcome"] = {
        "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
        "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
        "status": future_posture,
        "operationally_successful": operationally_successful,
        "broader_work_loop_posture_ready": broader_work_loop_posture_ready,
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
            "latest_governed_work_loop_evidence_outcome": future_posture,
            "latest_governed_work_loop_operational_success": operationally_successful,
            "latest_governed_work_loop_operational_status": (
                "operational_bounded_work_loop_continuation_reviewed"
                if operationally_successful
                else "operational_bounded_work_loop_continuation_needs_refinement"
            ),
            "latest_governed_work_loop_readiness": (
                "ready_for_broader_work_loop_posture_layer"
                if broader_work_loop_posture_ready
                else "not_ready_for_broader_work_loop_posture_layer"
            ),
            "latest_governed_work_loop_posture": future_posture,
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

    ledger_event = {
        "event_id": f"governed_work_loop_evidence_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_evidence_snapshot_v1_materialized",
        "event_class": "governed_work_loop_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
        "future_posture": future_posture,
        "broader_work_loop_posture_ready": broader_work_loop_posture_ready,
        "retained_promotion": False,
        "paused_capability_line_reopened": False,
        "artifact_paths": {
            "governed_work_loop_policy_v1": str(policy_artifact_path),
            "governed_work_loop_candidate_screen_v1": str(candidate_screen_artifact_path),
            "governed_work_loop_continuation_admission_v1": str(continuation_admission_artifact_path),
            "governed_work_loop_continuation_execution_v1": str(execution_artifact_path),
            "governed_direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "governed_direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "governed_work_loop_evidence_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
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
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1": _artifact_reference(
                work_loop_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1": _artifact_reference(
                work_loop_continuation_admission_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(
                work_loop_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_evidence_summary": {
            "evidence_reviewed": {
                "work_loop_execution_artifact": str(execution_artifact_path),
                "work_loop_continuation_admission_artifact": str(continuation_admission_artifact_path),
                "candidate_screen_artifact": str(candidate_screen_artifact_path),
                "policy_artifact": str(policy_artifact_path),
                "direct_work_evidence_artifact": str(direct_work_evidence_artifact_path),
                "direct_work_execution_artifact": str(direct_work_execution_artifact_path),
                "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
                "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-12:]),
            },
            "candidate_reviewed": candidate_reviewed,
            "operational_usefulness_assessment": operational_usefulness,
            "governance_sufficiency_assessment": governance_sufficiency,
            "envelope_compliance_assessment": envelope_compliance,
            "continuation_value_assessment": continuation_value,
            "future_posture": {
                "category": future_posture,
                "reason": future_posture_reason,
                "path_should_remain_available": future_posture
                in {
                    "keep_available_for_governed_loop_continuation",
                    "keep_available_but_narrow",
                    "keep_available_with_review_only",
                },
            },
            "broader_project_alignment": broader_project_alignment,
            "current_work_loop_accounting_summary": {
                "loop_candidate_id": str(candidate_reviewed.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_reviewed.get("loop_candidate_name", "")),
                "source_artifact_count": int(len(list(continuation_accounting_summary.get("source_artifact_paths", [])))),
                "write_root_count": int(len(list(continuation_accounting_summary.get("write_roots_touched", [])))),
                "branch_state_unchanged": bool(continuation_accounting_summary.get("branch_state_unchanged", False)),
                "retained_promotion_performed": bool(continuation_accounting_summary.get("retained_promotion_performed", False)),
                "admission_outcome": str(continuation_accounting_summary.get("admission_outcome", "")),
            },
            "trigger_status": review_rollback_status,
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the evidence review is derived from directive, bucket, branch, self-structure, work-loop policy, continuation-admission, and continuation-execution artifacts, so loop continuation remains governance-owned rather than execution-owned",
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
            "reason": "the first real governed work-loop continuation now has an explicit governance-owned evidence review covering operational usefulness, governance sufficiency, continuation value, and broader loop-posture readiness",
            "artifact_paths": {
                "governed_work_loop_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review distinguishes a real governed work-loop continuation path from a merely ceremonial first extension of the direct-work chain",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the first governed work-loop continuation is now evaluated separately from direct-work repetition, capability use, paused-line reopen, new-skill creation, and uncontrolled work-loop broadening",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, reopened no paused capability line, promoted no retained capability, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": broader_work_loop_posture_ready,
            "recommended_next_template": next_template,
            "reason": (
                "the first governed work-loop continuation is operational enough to support a governance-owned broader work-loop posture layer next"
                if broader_work_loop_posture_ready
                else "the continuation path still needs refinement before a broader governed work-loop posture layer should be defined"
            ),
        },
        "diagnostic_conclusions": {
            "governed_work_loop_evidence_review_v1_in_place": True,
            "first_governed_work_loop_continuation_operationally_successful": operationally_successful,
            "continuation_path_should_remain_available": future_posture
            in {
                "keep_available_for_governed_loop_continuation",
                "keep_available_but_narrow",
                "keep_available_with_review_only",
            },
            "work_loop_future_posture": future_posture,
            "ready_for_broader_governed_work_loop_posture_layer": broader_work_loop_posture_ready,
            "retained_promotion_occurred": False,
            "branch_state_mutation_occurred": False,
            "paused_capability_line_reopened": False,
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
        "reason": "diagnostic shadow passed: the first real governed work-loop continuation now has a governance-owned evidence review and future posture",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
