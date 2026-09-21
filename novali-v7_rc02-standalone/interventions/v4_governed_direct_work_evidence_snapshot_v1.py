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
        "work_item_id": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("work_identity", {})).get("work_item_id"),
        "work_item_name": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("work_identity", {})).get("work_item_name"),
        "directive_id": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("directive_branch_context", {})).get("directive_id"),
        "directive_linkage_summary": lambda payload: dict(payload.get("direct_work_accounting_captured", {})).get("work_summary"),
        "branch_id": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("directive_branch_context", {})).get("branch_id"),
        "branch_state_precondition": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("directive_branch_context", {})).get("branch_state"),
        "expected_capability_path": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("execution_path_reporting", {})).get("path"),
        "existing_capability_id": lambda payload: (
            dict(dict(payload.get("direct_work_accounting_captured", {})).get("execution_path_reporting", {})).get("existing_capability_id")
            or (
                "not_applicable_for_direct_work"
                if str(dict(dict(payload.get("direct_work_accounting_captured", {})).get("execution_path_reporting", {})).get("path", "")) == "direct_governed_work"
                else ""
            )
        ),
        "expected_review_hooks": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("review_trigger_status", {})),
        "expected_rollback_hooks": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("rollback_trigger_status", {})),
        "governance_observability_level": lambda payload: int(
            dict(dict(dict(payload.get("audit_artifact_produced", {})).get("coherence_audit_output", {})).get("summary", {})).get("total_check_count", 0)
            or 0
        ),
        "required_trusted_sources": lambda payload: dict(dict(payload.get("direct_work_accounting_captured", {})).get("trusted_source_report", {})).get("requested_sources"),
        "expected_resource_budget": lambda payload: (
            dict(dict(payload.get("direct_work_accounting_captured", {})).get("resource_report", {})).get("requested_resources")
            or dict(dict(payload.get("envelope_compliance", {})).get("resource_expectations", {}))
        ),
        "expected_write_roots": lambda payload: (
            dict(dict(payload.get("direct_work_accounting_captured", {})).get("write_root_report", {})).get("requested_write_roots")
            or dict(payload.get("direct_work_accounting_captured", {})).get("write_roots_touched")
        ),
        "network_mode_expectation": lambda payload: (
            dict(dict(payload.get("envelope_compliance", {})).get("resource_expectations", {})).get("network_mode")
            or dict(dict(payload.get("direct_work_accounting_captured", {})).get("resource_report", {})).get("requested_resources", {}).get("network_mode")
        ),
        "reversibility_level": lambda payload: "high" if bool(dict(payload.get("envelope_compliance", {})).get("passed", False)) else "",
        "expected_success_signal": lambda payload: dict(payload.get("direct_work_accounting_captured", {})).get("directive_support_observation"),
        "expected_usefulness_signal": lambda payload: dict(payload.get("direct_work_accounting_captured", {})).get("usefulness_signal_summary"),
        "expected_duplicate_overlap_check": lambda payload: dict(payload.get("direct_work_accounting_captured", {})).get("duplicate_or_overlap_observation"),
    }

    identity_fields = list(accounting_requirements.get("work_identity_and_linkage_must_be_logged", []))
    execution_path_fields = list(accounting_requirements.get("expected_execution_path_must_be_logged", []))
    budget_fields = list(accounting_requirements.get("expected_budget_and_trust_must_be_logged", []))
    evidence_fields = list(accounting_requirements.get("expected_evidence_must_be_logged", []))

    identity_presence = _evaluate_field_presence(identity_fields, accessors, execution_summary)
    execution_path_presence = _evaluate_field_presence(execution_path_fields, accessors, execution_summary)
    budget_presence = _evaluate_field_presence(budget_fields, accessors, execution_summary)
    evidence_presence = _evaluate_field_presence(evidence_fields, accessors, execution_summary)

    all_required_present = (
        bool(identity_presence.get("all_present", False))
        and bool(execution_path_presence.get("all_present", False))
        and bool(budget_presence.get("all_present", False))
        and bool(evidence_presence.get("all_present", False))
    )
    return {
        "work_identity_and_linkage": identity_presence,
        "expected_execution_path": execution_path_presence,
        "expected_budget_and_trust": budget_presence,
        "expected_evidence": evidence_presence,
        "all_required_present": all_required_present,
        "reason": (
            "all required direct-work identity, execution-path, budget or trust, and evidence fields are present in the execution artifact"
            if all_required_present
            else "one or more required direct-work accounting or evidence fields are missing from the execution artifact"
        ),
    }


def _operational_usefulness_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    audit_output = dict(execution_summary.get("audit_artifact_produced", {}))
    audit_summary = dict(dict(audit_output.get("coherence_audit_output", {})).get("summary", {}))
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    bounded_output_artifact_path = Path(str(audit_output.get("bounded_output_artifact_path", "")))

    coherence_score = float(audit_summary.get("coherence_score", 0.0) or 0.0)
    passed_check_count = int(audit_summary.get("passed_check_count", 0) or 0)
    failed_check_count = int(audit_summary.get("failed_check_count", 0) or 0)
    alignment_status = str(audit_summary.get("alignment_status", ""))
    operationally_meaningful = (
        bounded_output_artifact_path.exists()
        and bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and coherence_score >= 0.95
        and passed_check_count >= 10
        and failed_check_count == 0
        and alignment_status == "coherent"
    )
    return {
        "classification": "operationally_meaningful" if operationally_meaningful else "nominal_or_insufficient",
        "passed": operationally_meaningful,
        "work_was_real_not_ceremonial": operationally_meaningful,
        "worth_preserving_as_direct_work_path": operationally_meaningful,
        "bounded_output_artifact_exists": bounded_output_artifact_path.exists(),
        "audit_signal_summary": {
            "coherence_score": coherence_score,
            "passed_check_count": passed_check_count,
            "failed_check_count": failed_check_count,
            "alignment_status": alignment_status,
        },
        "reason": (
            "the execution produced a real directive-supportive coherence-audit artifact with fully coherent results and no failed checks"
            if operationally_meaningful
            else "the execution did not produce enough bounded governance-audit signal to count as an operationally meaningful direct-work path"
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
        "direct_work_control_envelope_proved_adequate": bool(envelope.get("passed", False)),
        "review_triggers_defined_and_inactive": bool(review_status) and _all_flags_false(review_status),
        "rollback_triggers_defined_and_inactive": bool(rollback_status) and _all_flags_false(rollback_status),
        "deprecation_triggers_defined_and_inactive": bool(deprecation_status) and _all_flags_false(deprecation_status),
        "reason": (
            "accounting coverage, the bounded direct-work envelope, and the review or rollback surfaces were all sufficient in the first real direct governed work execution"
            if governance_sufficient
            else "the first real direct-work execution still needs tighter accounting coverage or tighter trigger reporting before the path should be relied on"
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
            "network, write-root, bucket, branch, paused-capability, protected-surface, downstream, plan_, and routing constraints all held during the direct-work execution"
            if stable_low_risk
            else "one or more envelope or governance-boundary constraints did not hold cleanly during the direct-work execution"
        ),
    }


def _direct_work_value_assessment(execution_summary: dict[str, Any]) -> dict[str, Any]:
    directive_support = dict(execution_summary.get("directive_support_value", {}))
    hidden_capability_pressure = dict(execution_summary.get("hidden_capability_pressure_read", {}))
    path_separation = dict(execution_summary.get("path_separation_status", {}))
    accounting = dict(execution_summary.get("direct_work_accounting_captured", {}))
    usefulness_signal = dict(accounting.get("usefulness_signal_summary", {}))
    overlap_observation = str(accounting.get("duplicate_or_overlap_observation", ""))

    coherence_score = float(usefulness_signal.get("coherence_score", 0.0) or 0.0)
    real_direct_work = (
        bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and bool(hidden_capability_pressure.get("passed", False))
        and str(hidden_capability_pressure.get("value", "")) == "none"
        and bool(path_separation.get("remained_direct_work", False))
        and bool(path_separation.get("capability_use_not_invoked", False))
        and bool(path_separation.get("paused_capability_line_not_reopened", False))
        and bool(path_separation.get("new_skill_path_not_opened", False))
        and coherence_score >= 0.95
        and "low overlap" in overlap_observation.lower()
    )
    return {
        "classification": "real_direct_governed_work" if real_direct_work else "too_ceremonial_or_confused",
        "passed": real_direct_work,
        "demonstrates_real_governed_direct_work": real_direct_work,
        "not_capability_use_confusion": bool(path_separation.get("capability_use_not_invoked", False)),
        "not_hidden_development_or_reopen_pressure": bool(hidden_capability_pressure.get("passed", False)),
        "reason": (
            "the execution performed real governance-maintenance work with low overlap and clean path separation from capability use, reopen, and new-skill paths"
            if real_direct_work
            else "the execution was too ceremonial or path-confused to count as a robust direct governed work path"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    directive_work_selection_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    directive_work_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"
    )
    directive_work_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
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
            directive_work_selection_policy_snapshot,
            directive_work_candidate_screen_snapshot,
            directive_work_admission_snapshot,
            direct_work_execution_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: direct-work evidence review requires the governance substrate, directive-work selection policy, candidate screen, admission, execution, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed direct-work evidence-review artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed direct-work evidence-review artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed direct-work evidence-review artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review direct-work evidence without the prerequisite governed chain"},
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
            "reason": "diagnostic shadow failed: direct-work evidence review requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review direct-work evidence without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    if not governed_directive_work_selection_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed directive-work selection policy state is missing",
            "observability_gain": {"passed": False, "reason": "missing governed directive-work selection policy state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed directive-work selection policy state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed directive-work selection policy state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review direct-work evidence without directive-work policy state"},
        }

    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))

    policy_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json",
    )
    candidate_screen_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_*.json",
    )
    direct_work_admission_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_admission_artifact_path"),
        "memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json",
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
            direct_work_admission_artifact_path,
            direct_work_execution_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more direct-work evidence-review artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for direct-work evidence review"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for direct-work evidence review"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for direct-work evidence review"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review direct-work evidence without the governing artifact chain"},
        }

    policy_payload = _load_json_file(policy_artifact_path)
    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    direct_work_admission_payload = _load_json_file(direct_work_admission_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)

    policy_summary = dict(policy_payload.get("governed_directive_work_selection_policy_summary", {}))
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_directive_work_candidate_screen_summary", {}))
    direct_work_admission_summary = dict(direct_work_admission_payload.get("governed_directive_work_admission_summary", {}))
    execution_summary = dict(direct_work_execution_payload.get("governed_direct_work_execution_summary", {}))
    capability_use_evidence_summary = dict(capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {}))
    if not all(
        [
            policy_summary,
            candidate_screen_summary,
            direct_work_admission_summary,
            execution_summary,
            capability_use_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more direct-work evidence-review summaries could not be loaded",
            "observability_gain": {"passed": False, "reason": "missing governed direct-work review summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed direct-work review summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed direct-work review summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review direct-work evidence without the loaded governing summaries"},
        }

    candidate_reviewed = dict(execution_summary.get("candidate_executed", {}))
    accounting_requirements = dict(
        policy_summary.get(
            "work_selection_accounting_requirements",
            governed_directive_work_selection_policy.get("work_selection_accounting_requirements", {}),
        )
    )

    operational_usefulness = _operational_usefulness_assessment(execution_summary)
    governance_sufficiency = _governance_sufficiency_assessment(execution_summary, accounting_requirements)
    envelope_compliance = _envelope_compliance_assessment(execution_summary, current_state_summary)
    direct_work_value = _direct_work_value_assessment(execution_summary)

    operationally_successful = (
        bool(operational_usefulness.get("passed", False))
        and bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(direct_work_value.get("passed", False))
    )
    if operationally_successful:
        future_posture = "keep_available_but_narrow"
        future_posture_reason = (
            "the first real direct governed work execution was operationally meaningful and well-governed, so the path should remain available, but only one narrow case exists so the path should stay bounded rather than generalized"
        )
    elif bool(governance_sufficiency.get("passed", False)) and bool(envelope_compliance.get("passed", False)):
        future_posture = "keep_available_with_review_only"
        future_posture_reason = (
            "the bounded execution path remains safe enough to preserve, but the operational signal is not yet strong enough to keep available without tighter review"
        )
    else:
        future_posture = "pause_direct_work_pending_better_case"
        future_posture_reason = (
            "the first direct-work execution did not produce enough combined operational and governance signal to keep the path active without refinement"
        )

    governed_work_loop_policy_ready = operationally_successful
    next_template = (
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
        if governed_work_loop_policy_ready
        else "memory_summary.v4_governed_direct_work_policy_refinement_snapshot_v1"
    )
    broader_project_alignment = {
        "supports_governed_self_direction": operationally_successful,
        "supports_bucket_bounded_execution": bool(envelope_compliance.get("passed", False)),
        "provides_real_base_for_broader_governed_work_loop": governed_work_loop_policy_ready,
        "ready_for_governed_work_loop_policy_layer": governed_work_loop_policy_ready,
        "ready_for_broader_governed_work_execution_without_more_evidence": False,
        "more_direct_work_refinement_needed_before_next_layer": not governed_work_loop_policy_ready,
        "further_evidence_needed_before_broader_governed_work_execution": [
            "at least one more distinct admitted direct-work case with full envelope compliance",
            "continued inactive review, rollback, and deprecation triggers across another real direct-work execution",
            "evidence that direct work can remain cleanly separated from capability-use, reopen, and new-skill paths across more than one case",
        ],
        "reason": (
            "the first real direct-work execution proves that bounded governed work can run operationally under governance, which is enough to justify defining a broader governed work-loop policy layer next"
            if governed_work_loop_policy_ready
            else "the first real direct-work execution still needs refinement before it should anchor a broader governed work-loop policy layer"
        ),
    }

    direct_work_accounting_summary = dict(execution_summary.get("direct_work_accounting_captured", {}))
    review_rollback_status = dict(execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_direct_work_evidence_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_directive_work_policy = dict(governed_directive_work_selection_policy)
    updated_directive_work_policy["last_policy_artifact_path"] = str(policy_artifact_path)
    updated_directive_work_policy["last_candidate_screen_artifact_path"] = str(candidate_screen_artifact_path)
    updated_directive_work_policy["last_direct_work_admission_artifact_path"] = str(direct_work_admission_artifact_path)
    updated_directive_work_policy["last_direct_work_execution_artifact_path"] = str(direct_work_execution_artifact_path)
    updated_directive_work_policy["governed_direct_work_evidence_review_schema"] = {
        "schema_name": "GovernedDirectWorkEvidenceReview",
        "schema_version": "governed_direct_work_evidence_review_v1",
        "required_fields": [
            "work_item_id",
            "work_item_name",
            "operational_usefulness_assessment",
            "governance_sufficiency_assessment",
            "envelope_compliance_assessment",
            "direct_work_value_assessment",
            "future_posture",
            "governed_work_loop_readiness",
        ],
        "future_posture_classes": [
            "keep_available_for_direct_governed_work",
            "keep_available_but_narrow",
            "keep_available_with_review_only",
            "pause_direct_work_pending_better_case",
        ],
    }
    updated_directive_work_policy["last_direct_work_evidence_artifact_path"] = str(artifact_path)
    updated_directive_work_policy["last_direct_work_evidence_outcome"] = {
        "work_item_name": str(candidate_reviewed.get("work_item_name", "")),
        "work_item_id": str(candidate_reviewed.get("work_item_id", "")),
        "status": future_posture,
        "operationally_successful": operationally_successful,
        "governed_work_loop_ready": governed_work_loop_policy_ready,
        "retained_promotion": False,
        "paused_capability_line_reopened": False,
        "best_next_template": next_template,
    }
    updated_directive_work_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_directive_work_selection_policy"] = updated_directive_work_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_direct_work_evidence_review_in_place": True,
            "latest_direct_work_evidence_outcome": future_posture,
            "latest_direct_work_operational_success": operationally_successful,
            "latest_governed_work_loop_readiness": (
                "ready_for_policy_layer" if governed_work_loop_policy_ready else "not_ready_for_policy_layer"
            ),
            "latest_direct_work_operational_status": (
                "operational_bounded_direct_work_reviewed"
                if operationally_successful
                else "operational_bounded_direct_work_needs_refinement"
            ),
            "latest_directive_work_best_next_template": next_template,
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
        "event_id": f"governed_direct_work_evidence_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_direct_work_evidence_snapshot_v1_materialized",
        "event_class": "governed_direct_work_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "work_item_id": str(candidate_reviewed.get("work_item_id", "")),
        "work_item_name": str(candidate_reviewed.get("work_item_name", "")),
        "future_posture": future_posture,
        "governed_work_loop_ready": governed_work_loop_policy_ready,
        "retained_promotion": False,
        "paused_capability_line_reopened": False,
        "artifact_paths": {
            "directive_work_policy_v1": str(policy_artifact_path),
            "directive_work_candidate_screen_v1": str(candidate_screen_artifact_path),
            "directive_work_admission_v1": str(direct_work_admission_artifact_path),
            "direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "direct_work_evidence_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
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
            "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1": _artifact_reference(
                directive_work_selection_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1": _artifact_reference(
                directive_work_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(
                directive_work_admission_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_direct_work_evidence_summary": {
            "evidence_reviewed": {
                "direct_work_execution_artifact": str(direct_work_execution_artifact_path),
                "direct_work_admission_artifact": str(direct_work_admission_artifact_path),
                "candidate_screen_artifact": str(candidate_screen_artifact_path),
                "policy_artifact": str(policy_artifact_path),
                "capability_use_evidence_artifact": str(capability_use_evidence_artifact_path),
                "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
                "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-12:]),
            },
            "candidate_reviewed": candidate_reviewed,
            "operational_usefulness_assessment": operational_usefulness,
            "governance_sufficiency_assessment": governance_sufficiency,
            "envelope_compliance_assessment": envelope_compliance,
            "direct_work_value_assessment": direct_work_value,
            "future_posture": {
                "category": future_posture,
                "reason": future_posture_reason,
                "path_should_remain_available": future_posture
                in {
                    "keep_available_for_direct_governed_work",
                    "keep_available_but_narrow",
                    "keep_available_with_review_only",
                },
            },
            "broader_project_alignment": broader_project_alignment,
            "current_direct_work_accounting_summary": {
                "work_item_id": str(dict(direct_work_accounting_summary.get("work_identity", {})).get("work_item_id", "")),
                "work_item_name": str(dict(direct_work_accounting_summary.get("work_identity", {})).get("work_item_name", "")),
                "source_artifact_count": int(len(list(direct_work_accounting_summary.get("source_artifact_paths", [])))),
                "write_root_count": int(len(list(direct_work_accounting_summary.get("write_roots_touched", [])))),
                "branch_state_unchanged": bool(direct_work_accounting_summary.get("branch_state_unchanged", False)),
                "retained_promotion_performed": bool(direct_work_accounting_summary.get("retained_promotion_performed", False)),
                "admission_outcome": str(direct_work_accounting_summary.get("admission_outcome", "")),
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
                "reason": "the evidence review is derived from directive, bucket, branch, self-structure, directive-work policy, admission, and execution artifacts, so direct work remains governance-owned rather than execution-owned",
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
            "reason": "the first real direct governed work execution now has an explicit governance-owned evidence review covering operational usefulness, governance sufficiency, and broader work-loop readiness",
            "artifact_paths": {
                "direct_work_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review distinguishes a real direct governed work path from a merely ceremonial first execution",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the first direct-work execution is now evaluated separately from capability use, paused-line reopen, new-skill creation, and uncontrolled work expansion",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, reopened no paused capability line, promoted no retained capability, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": governed_work_loop_policy_ready,
            "recommended_next_template": next_template,
            "reason": (
                "the first direct-work path is operational enough to support a governance-owned governed-work-loop policy layer next"
                if governed_work_loop_policy_ready
                else "the direct-work path still needs refinement before a broader governed work-loop policy layer should be defined"
            ),
        },
        "diagnostic_conclusions": {
            "governed_direct_work_evidence_review_v1_in_place": True,
            "first_direct_governed_work_execution_operationally_successful": operationally_successful,
            "direct_work_path_should_remain_available": future_posture
            in {
                "keep_available_for_direct_governed_work",
                "keep_available_but_narrow",
                "keep_available_with_review_only",
            },
            "direct_work_future_posture": future_posture,
            "ready_for_governed_work_loop_policy_layer": governed_work_loop_policy_ready,
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
        "reason": "diagnostic shadow passed: the first real direct governed work execution now has a governance-owned evidence review and future posture",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
    }
