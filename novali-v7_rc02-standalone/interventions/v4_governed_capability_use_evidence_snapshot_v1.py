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


def _evaluate_field_presence(
    fields: list[str],
    accessors: dict[str, Callable[[dict[str, Any]], Any]],
    accounting: dict[str, Any],
) -> dict[str, Any]:
    presence = {
        str(field): _value_present(accessors.get(str(field), lambda _: None)(accounting))
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
    accounting: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, Any]:
    resource_accessors: dict[str, Callable[[dict[str, Any]], Any]] = {
        "invocation_id": lambda payload: dict(payload.get("invocation_identity", {})).get("invocation_id"),
        "capability_id": lambda payload: dict(payload.get("invocation_identity", {})).get("capability_id"),
        "directive_id": lambda payload: dict(payload.get("directive_branch_context", {})).get("directive_id"),
        "branch_id": lambda payload: dict(payload.get("directive_branch_context", {})).get("branch_id"),
        "branch_state": lambda payload: dict(payload.get("directive_branch_context", {})).get("branch_state"),
        "cpu_parallel_units_used": lambda payload: dict(payload.get("resource_usage", {})).get("cpu_parallel_units_used"),
        "memory_mb_used": lambda payload: dict(payload.get("resource_usage", {})).get("memory_mb_used"),
        "storage_write_mb_used": lambda payload: dict(payload.get("resource_usage", {})).get("storage_write_mb_used"),
        "network_mode_used": lambda payload: dict(payload.get("resource_usage", {})).get("network_mode_used"),
        "write_roots_touched": lambda payload: payload.get("write_roots_touched"),
        "source_artifact_paths": lambda payload: payload.get("source_artifact_paths"),
    }
    governance_accessors: dict[str, Callable[[dict[str, Any]], Any]] = {
        "policy_outcome": lambda payload: payload.get("policy_outcome"),
        "decision_rationale": lambda payload: payload.get("rationale"),
        "trusted_source_report": lambda payload: payload.get("trusted_source_report"),
        "resource_report": lambda payload: payload.get("resource_report"),
        "write_root_report": lambda payload: payload.get("write_root_report"),
        "branch_state_unchanged": lambda payload: payload.get("branch_state_unchanged"),
        "retained_promotion_performed": lambda payload: payload.get("retained_promotion_performed"),
        "rollback_trigger_status": lambda payload: payload.get("rollback_trigger_status"),
        "deprecation_trigger_status": lambda payload: payload.get("deprecation_trigger_status"),
    }
    evidence_accessors: dict[str, Callable[[dict[str, Any]], Any]] = {
        "use_case_summary": lambda payload: payload.get("use_case_summary"),
        "directive_support_observation": lambda payload: payload.get("directive_support_observation"),
        "bounded_output_artifact_path": lambda payload: payload.get("bounded_output_artifact_path"),
        "usefulness_signal_summary": lambda payload: payload.get("usefulness_signal_summary"),
        "duplication_or_overlap_observation": lambda payload: payload.get("duplication_or_overlap_observation"),
    }

    resource_fields = list(accounting_requirements.get("resource_usage_must_be_logged", []))
    governance_fields = list(accounting_requirements.get("governance_reporting_must_be_logged", []))
    evidence_fields = list(accounting_requirements.get("evidence_of_usefulness_must_be_preserved", []))

    resource_presence = _evaluate_field_presence(resource_fields, resource_accessors, accounting)
    governance_presence = _evaluate_field_presence(governance_fields, governance_accessors, accounting)
    evidence_presence = _evaluate_field_presence(evidence_fields, evidence_accessors, accounting)

    all_required_present = (
        bool(resource_presence.get("all_present", False))
        and bool(governance_presence.get("all_present", False))
        and bool(evidence_presence.get("all_present", False))
    )
    return {
        "resource_usage_logging": resource_presence,
        "governance_reporting": governance_presence,
        "usefulness_evidence": evidence_presence,
        "all_required_present": all_required_present,
        "reason": (
            "all required invocation accounting, governance reporting, and usefulness-evidence fields are present"
            if all_required_present
            else "one or more required accounting or governance-reporting fields are missing from the invocation artifact"
        ),
    }


def _operational_usefulness_assessment(
    invocation_summary: dict[str, Any],
) -> dict[str, Any]:
    directive_support = dict(invocation_summary.get("directive_support_value", {}))
    output_artifact = dict(invocation_summary.get("output_artifact_produced", {}))
    bundle_summary = dict(output_artifact.get("bundle_summary", {}))
    bounded_output_path = Path(str(output_artifact.get("bounded_output_artifact_path", "")))

    parsed_file_count = int(bundle_summary.get("parsed_file_count", 0) or 0)
    dummy_eval_count = int(bundle_summary.get("dummy_eval_count", 0) or 0)
    patch_tuple_count = int(bundle_summary.get("patch_tuple_count", 0) or 0)
    recognized_line_share_weighted = float(bundle_summary.get("recognized_line_share_weighted", 0.0) or 0.0)
    operationally_meaningful = (
        bounded_output_path.exists()
        and bool(directive_support.get("passed", False))
        and str(directive_support.get("value", "")) == "high"
        and parsed_file_count >= 3
        and dummy_eval_count >= 100
        and patch_tuple_count >= 500
        and recognized_line_share_weighted >= 0.95
    )
    return {
        "classification": "operationally_meaningful" if operationally_meaningful else "nominal_or_insufficient",
        "passed": operationally_meaningful,
        "use_case_was_real_not_nominal": operationally_meaningful,
        "worth_preserving_for_future_directive_valid_tasks": operationally_meaningful,
        "summary_signal": {
            "parsed_file_count": parsed_file_count,
            "dummy_eval_count": dummy_eval_count,
            "patch_tuple_count": patch_tuple_count,
            "recognized_line_share_weighted": recognized_line_share_weighted,
        },
        "bounded_output_artifact_exists": bounded_output_path.exists(),
        "reason": (
            "the invocation produced a real directive-supportive diagnostic artifact with strong parse coverage and high recognized output quality"
            if operationally_meaningful
            else "the invocation did not produce enough bounded diagnostic signal to count as an operationally meaningful governed use path"
        ),
    }


def _governance_sufficiency_assessment(
    invocation_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, Any]:
    accounting = dict(invocation_summary.get("invocation_accounting_captured", {}))
    envelope = dict(invocation_summary.get("envelope_compliance", {}))
    trigger_status = dict(invocation_summary.get("rollback_review_trigger_status", {}))
    review_status = dict(trigger_status.get("review_trigger_status", {}))
    rollback_status = dict(trigger_status.get("rollback_trigger_status", {}))
    deprecation_status = dict(trigger_status.get("deprecation_trigger_status", {}))
    accounting_completeness = _accounting_completeness(accounting, accounting_requirements)

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
        "control_envelope_proved_adequate": bool(envelope.get("passed", False)),
        "review_triggers_defined_and_inactive": bool(review_status) and _all_flags_false(review_status),
        "rollback_triggers_defined_and_inactive": bool(rollback_status) and _all_flags_false(rollback_status),
        "deprecation_triggers_defined_and_inactive": bool(deprecation_status) and _all_flags_false(deprecation_status),
        "reason": (
            "accounting coverage, the bounded control envelope, and the review or rollback surfaces were all sufficient in the first real governed invocation"
            if governance_sufficient
            else "the first real invocation still needs tighter accounting coverage or tighter review or rollback reporting before the use path should be relied on"
        ),
    }


def _envelope_compliance_assessment(
    invocation_summary: dict[str, Any],
    current_state_summary: dict[str, Any],
) -> dict[str, Any]:
    envelope = dict(invocation_summary.get("envelope_compliance", {}))
    bucket_pressure = dict(envelope.get("bucket_pressure", {}))
    stable_low_risk = (
        bool(envelope.get("passed", False))
        and str(envelope.get("network_mode_observed", "")) == "none"
        and bool(envelope.get("writes_within_approved_roots", False))
        and bool(envelope.get("resource_limits_respected", False))
        and bool(envelope.get("storage_budget_respected", False))
        and bool(envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(envelope.get("no_branch_state_mutation", False))
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
        "protected_surface_isolation": bool(envelope.get("no_protected_surface_modification", False)),
        "downstream_isolation": bool(envelope.get("no_downstream_selected_set_work", False)),
        "plan_non_ownership": bool(envelope.get("no_plan_ownership_change", False))
        and bool(current_state_summary.get("plan_non_owning", False)),
        "routing_non_involvement": bool(envelope.get("no_routing_work", False))
        and bool(current_state_summary.get("routing_deferred", False)),
        "reason": (
            "network, write-root, bucket, branch, protected-surface, downstream, plan_, and routing constraints all held during the invocation"
            if stable_low_risk
            else "one or more envelope or governance-boundary constraints did not hold cleanly during the invocation"
        ),
    }


def _capability_use_value_assessment(
    invocation_summary: dict[str, Any],
) -> dict[str, Any]:
    duplication = dict(invocation_summary.get("duplication_overlap_read", {}))
    paused_behavior = dict(invocation_summary.get("paused_capability_behavior", {}))
    envelope = dict(invocation_summary.get("envelope_compliance", {}))

    real_reuse = (
        bool(duplication.get("passed", False))
        and str(duplication.get("value", "")) == "low"
        and bool(paused_behavior.get("invocation_did_not_reopen_development", False))
        and bool(paused_behavior.get("new_skill_candidate_not_opened", False))
        and bool(paused_behavior.get("paused_capability_line_remained_paused_for_development", False))
        and bool(envelope.get("no_capability_modification", False))
    )
    return {
        "classification": "real_governed_reuse" if real_reuse else "too_ceremonial_or_confused",
        "passed": real_reuse,
        "shows_real_reuse_of_held_capability": real_reuse,
        "shows_hidden_development_pressure": not real_reuse,
        "reason": (
            "the invocation reused a held capability for directive-valid work while keeping development paused and duplication low"
            if real_reuse
            else "the invocation looked too close to hidden development, reopen pressure, or ceremonial demonstration to count as durable governed capability reuse"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    capability_use_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_policy_snapshot_v1"
    )
    capability_use_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1"
    )
    capability_use_invocation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1"
    )
    capability_use_invocation_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1"
    )
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            capability_use_policy_snapshot,
            capability_use_candidate_screen_snapshot,
            capability_use_invocation_admission_snapshot,
            capability_use_invocation_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: capability-use evidence review requires governance, capability-use policy, candidate-screen, invocation-admission, invocation-execution, and provisional-pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-capability evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-capability evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-capability evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot review operational governed capability use without the full invocation and policy artifact chain",
            },
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
            "reason": "diagnostic shadow failed: capability-use evidence review requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot review operational governed capability use without current directive, bucket, self-structure, and branch state",
            },
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))

    invocation_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_execution_artifact_path", ""))
        or _latest_matching_artifact("proposal_learning_loop_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_capability_use_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    candidate_screen_artifact_path = Path(
        str(governed_capability_use_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_*.json")
    )
    invocation_admission_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_invocation_admission_snapshot_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )

    invocation_payload = _load_json_file(invocation_artifact_path)
    invocation_summary = dict(invocation_payload.get("governed_capability_invocation_summary", {}))
    policy_payload = _load_json_file(policy_artifact_path)
    policy_summary = dict(policy_payload.get("governed_capability_use_policy_summary", {}))
    invocation_admission_payload = _load_json_file(invocation_admission_artifact_path)
    invocation_admission_summary = dict(
        invocation_admission_payload.get("governed_capability_use_invocation_admission_summary", {})
    )
    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_capability_use_candidate_screen_summary", {}))
    provisional_pause_summary = dict(
        _load_json_file(provisional_pause_artifact_path).get("governed_skill_provisional_pause_summary", {})
    )
    if not all([invocation_summary, policy_summary, invocation_admission_summary, candidate_screen_summary, provisional_pause_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: capability-use evidence review could not load one or more prerequisite summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot review operational governed capability use without the prerequisite summary payloads",
            },
        }

    capability_reviewed = dict(invocation_summary.get("candidate_invoked", {}))
    accounting_requirements = dict(governed_capability_use_policy.get("invocation_accounting_requirements", {}))
    operational_usefulness = _operational_usefulness_assessment(invocation_summary)
    governance_sufficiency = _governance_sufficiency_assessment(invocation_summary, accounting_requirements)
    envelope_compliance = _envelope_compliance_assessment(invocation_summary, current_state_summary)
    capability_use_value = _capability_use_value_assessment(invocation_summary)

    operationally_successful = (
        bool(operational_usefulness.get("passed", False))
        and bool(governance_sufficiency.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and bool(capability_use_value.get("passed", False))
    )
    invocation_posture = str(dict(invocation_admission_summary.get("admission_outcome", {})).get("callable_use_posture", ""))
    if operationally_successful and invocation_posture == "diagnostic_only_use":
        future_posture = "keep_available_but_diagnostic_only"
        future_posture_reason = (
            "the first governed invocation was operationally useful and sufficiently governed, so the path should stay available while remaining inside its diagnostic-only use class"
        )
    elif operationally_successful:
        future_posture = "keep_available_for_governed_use"
        future_posture_reason = (
            "the first governed invocation was operationally useful and sufficiently governed, so the path should remain available for future bounded governed use"
        )
    elif bool(governance_sufficiency.get("passed", False)) and bool(envelope_compliance.get("passed", False)):
        future_posture = "keep_available_with_review_only"
        future_posture_reason = (
            "the use path is directionally valid, but the first invocation did not yet provide a strong enough operational signal to preserve unreviewed operational use"
        )
    else:
        future_posture = "pause_operational_use_pending_better_case"
        future_posture_reason = (
            "the first invocation did not yet prove enough operational or governance sufficiency to justify keeping the path active as an operational governed use channel"
        )

    directive_work_selection_ready = operationally_successful
    next_template = (
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
        if directive_work_selection_ready
        else "memory_summary.v4_governed_capability_use_policy_refinement_snapshot_v1"
    )
    broader_project_alignment = {
        "supports_governed_self_direction": operationally_successful,
        "supports_bucket_bounded_execution": bool(envelope_compliance.get("passed", False)),
        "provides_real_base_for_directive_work_selection_next": directive_work_selection_ready,
        "more_use_layer_refinement_needed_first": not directive_work_selection_ready,
        "further_evidence_needed_before_directive_work_selection": []
        if directive_work_selection_ready
        else [
            "at least one more operationally meaningful governed invocation with full accounting and envelope compliance",
            "or a clearer demonstration that the use layer adds real operational value rather than a one-off demonstration",
        ],
        "further_evidence_needed_before_broader_use_expansion": [
            "more than one bounded governed invocation case",
            "continued low-duplication direct use with the development line still paused",
            "evidence from a review-only or higher-consequence use candidate before broadening beyond diagnostic-only use",
        ],
        "reason": (
            "the first real invocation proved that a held capability can be reused for directive-valid governed work without reopening development, which is enough to justify defining directive-work selection on top of the use layer"
            if directive_work_selection_ready
            else "the first invocation was not yet strong enough to justify building directive-work selection on top of the use layer"
        ),
    }

    invocation_accounting_summary = dict(invocation_summary.get("invocation_accounting_captured", {}))
    review_rollback_status = dict(invocation_summary.get("rollback_review_trigger_status", {}))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_capability_use_evidence_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_capability_use_policy = dict(governed_capability_use_policy)
    updated_capability_use_policy["governed_capability_use_evidence_review_schema"] = {
        "schema_name": "GovernedCapabilityUseEvidenceReview",
        "schema_version": "governed_capability_use_evidence_review_v1",
        "required_fields": [
            "use_request_id",
            "request_name",
            "operational_usefulness_assessment",
            "governance_sufficiency_assessment",
            "envelope_compliance_assessment",
            "capability_use_value_assessment",
            "future_posture",
            "directive_work_selection_readiness",
        ],
        "future_posture_classes": [
            "keep_available_for_governed_use",
            "keep_available_but_diagnostic_only",
            "keep_available_with_review_only",
            "pause_operational_use_pending_better_case",
        ],
    }
    updated_capability_use_policy["last_invocation_evidence_artifact_path"] = str(artifact_path)
    updated_capability_use_policy["last_invocation_evidence_outcome"] = {
        "request_name": str(capability_reviewed.get("request_name", "")),
        "use_request_id": str(capability_reviewed.get("use_request_id", "")),
        "status": future_posture,
        "operationally_successful": operationally_successful,
        "directive_work_selection_ready": directive_work_selection_ready,
        "retained_promotion": False,
        "development_line_reopened": False,
        "best_next_template": next_template,
    }
    updated_capability_use_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_capability_use_policy"] = updated_capability_use_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_capability_use_evidence_review_in_place": True,
            "latest_capability_use_evidence_outcome": future_posture,
            "latest_capability_use_operational_success": operationally_successful,
            "latest_capability_use_directive_work_selection_readiness": (
                "ready_for_policy_layer" if directive_work_selection_ready else "not_ready_for_policy_layer"
            ),
            "latest_capability_use_operational_status": (
                "operational_bounded_diagnostic_use_reviewed"
                if operationally_successful
                else "operational_bounded_diagnostic_use_needs_refinement"
            ),
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
        "event_id": f"governed_capability_use_evidence_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_capability_use_evidence_snapshot_v1_materialized",
        "event_class": "governed_capability_use_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "capability_id": str(capability_reviewed.get("capability_id", "")),
        "use_request_id": str(capability_reviewed.get("use_request_id", "")),
        "future_posture": future_posture,
        "directive_work_selection_ready": directive_work_selection_ready,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "capability_use_policy_v1": str(policy_artifact_path),
            "capability_use_candidate_screen_v1": str(candidate_screen_artifact_path),
            "capability_use_invocation_admission_v1": str(invocation_admission_artifact_path),
            "capability_use_invocation_execution_v1": str(invocation_artifact_path),
            "skill_provisional_pause_v1": str(provisional_pause_artifact_path),
            "capability_use_evidence_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
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
            "memory_summary.v4_governed_capability_use_policy_snapshot_v1": _artifact_reference(
                capability_use_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1": _artifact_reference(
                capability_use_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1": _artifact_reference(
                capability_use_invocation_admission_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1": _artifact_reference(
                capability_use_invocation_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot, latest_snapshots
            ),
        },
        "governed_capability_use_evidence_summary": {
            "evidence_reviewed": {
                "invocation_execution_artifact": str(invocation_artifact_path),
                "invocation_admission_artifact": str(invocation_admission_artifact_path),
                "candidate_screen_artifact": str(candidate_screen_artifact_path),
                "policy_artifact": str(policy_artifact_path),
                "provisional_pause_artifact": str(provisional_pause_artifact_path),
                "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
                "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-12:]),
            },
            "candidate_reviewed": capability_reviewed,
            "operational_usefulness_assessment": operational_usefulness,
            "governance_sufficiency_assessment": governance_sufficiency,
            "envelope_compliance_assessment": envelope_compliance,
            "capability_use_value_assessment": capability_use_value,
            "future_posture": {
                "category": future_posture,
                "reason": future_posture_reason,
                "path_should_remain_available": future_posture
                in {
                    "keep_available_for_governed_use",
                    "keep_available_but_diagnostic_only",
                    "keep_available_with_review_only",
                },
            },
            "broader_project_alignment": broader_project_alignment,
            "current_invocation_accounting_summary": {
                "policy_outcome": str(invocation_accounting_summary.get("policy_outcome", "")),
                "use_case_summary": str(invocation_accounting_summary.get("use_case_summary", "")),
                "source_artifact_count": int(len(list(invocation_accounting_summary.get("source_artifact_paths", [])))),
                "write_root_count": int(len(list(invocation_accounting_summary.get("write_roots_touched", [])))),
                "branch_state_unchanged": bool(invocation_accounting_summary.get("branch_state_unchanged", False)),
                "retained_promotion_performed": bool(invocation_accounting_summary.get("retained_promotion_performed", False)),
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
                "reason": "the evidence review is derived from directive, bucket, branch, self-structure, capability-use policy, invocation-admission, and invocation-execution artifacts, so capability use remains governance-owned rather than execution-owned",
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
            "reason": "the first real governed capability invocation now has an explicit governance-owned evidence review covering operational usefulness, governance sufficiency, and future posture",
            "artifact_paths": {
                "capability_use_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review distinguishes an operationally meaningful governed use path from a merely ceremonial or insufficient first invocation",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the first real invocation is now evaluated separately from capability development, reopen pressure, and new-skill acquisition",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; it opened no new behavior-changing branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": directive_work_selection_ready,
            "recommended_next_template": next_template,
            "reason": (
                "the first governed capability-use path is operational enough to support a governance-owned directive-work selection layer next"
                if directive_work_selection_ready
                else "the capability-use layer still needs refinement before directive-work selection should be layered on top"
            ),
        },
        "diagnostic_conclusions": {
            "governed_capability_use_evidence_review_v1_in_place": True,
            "first_governed_capability_invocation_operationally_successful": operationally_successful,
            "use_path_should_remain_available": future_posture
            in {
                "keep_available_for_governed_use",
                "keep_available_but_diagnostic_only",
                "keep_available_with_review_only",
            },
            "use_path_future_posture": future_posture,
            "ready_for_directive_work_selection_policy_layer": directive_work_selection_ready,
            "retained_promotion_occurred": False,
            "branch_state_mutation_occurred": False,
            "paused_capability_line_remained_paused_for_development": True,
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
        "reason": "diagnostic shadow passed: the first real governed capability invocation now has a governance-owned evidence review and future posture",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
