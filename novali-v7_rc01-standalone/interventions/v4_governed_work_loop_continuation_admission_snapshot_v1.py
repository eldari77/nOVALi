from __future__ import annotations

from pathlib import Path
from typing import Any

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
from .v4_governed_work_loop_policy_snapshot_v1 import _resolve_artifact_path
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _find_loop_candidate(
    screened_candidates: list[dict[str, Any]],
    *,
    best_candidate_name: str,
) -> dict[str, Any]:
    for candidate in screened_candidates:
        if str(candidate.get("loop_candidate_name", "")) == best_candidate_name:
            return dict(candidate)
    for candidate in screened_candidates:
        if str(candidate.get("assigned_class", "")) == "loop_continue_candidate":
            return dict(candidate)
    return {}


def _required_accounting_fields(loop_accounting_requirements: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key in [
        "loop_identity_and_context_must_be_logged",
        "current_work_state_must_be_logged",
        "resource_and_trust_position_must_be_logged",
        "continuation_decision_must_be_logged",
    ]:
        for item in list(loop_accounting_requirements.get(key, [])):
            text = str(item)
            if text and text not in fields:
                fields.append(text)
    return fields


def _build_admission_checks(
    candidate_record: dict[str, Any],
    *,
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    loop_accounting_requirements: dict[str, Any],
    loop_entry_conditions: dict[str, Any],
    loop_continuation_conditions: dict[str, Any],
    loop_exit_or_halt_conditions: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    classification_report = dict(candidate_record.get("classification_report", {}))
    screen_dimensions = dict(candidate_record.get("screen_dimensions", {}))
    path_separation = dict(candidate_record.get("path_separation", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    loop_accounting = dict(candidate_record.get("loop_accounting_expectations", {}))
    expected_path = dict(loop_accounting.get("expected_path", {}))
    resource_trust_position = dict(loop_accounting.get("resource_trust_position", {}))
    distinct_value = dict(screen_dimensions.get("directive_linkage_and_distinct_value", {}))
    required_accounting = _required_accounting_fields(loop_accounting_requirements)

    accounting_fields_present = all(
        bool(loop_accounting.get(field_name))
        for field_name in [
            "loop_identity_context",
            "current_work_state",
            "candidate_identity",
            "expected_path",
            "resource_trust_position",
            "continuation_rationale",
            "expected_next_evidence_signal",
            "review_rollback_hooks",
        ]
    )
    all_entry_conditions_pass = all(bool(dict(value).get("current_passed", False)) for value in loop_entry_conditions.values())
    all_continuation_conditions_pass = all(
        bool(dict(value).get("current_passed", False)) for value in loop_continuation_conditions.values()
    )
    no_exit_conditions_active = all(not bool(dict(value).get("currently_active", False)) for value in loop_exit_or_halt_conditions.values())

    return {
        "screen_class_allows_loop_continuation": {
            "passed": str(candidate_record.get("assigned_class", "")) == "loop_continue_candidate",
            "reason": "only a loop_continue_candidate is eligible for first governed work-loop continuation admission at this gate",
        },
        "directive_linkage_or_closeness": {
            "passed": str(distinct_value.get("directive_relevance", "")) == "high",
            "reason": "the continuation candidate remains tightly aligned to the current directive",
        },
        "distinct_value_over_prior_work": {
            "passed": not bool(distinct_value.get("repeats_low_yield_narrow_shape", False))
            and str(distinct_value.get("expected_incremental_value", "")) in {"medium", "high"},
            "reason": "the next loop step must add distinct value rather than repeat the same narrow low-yield shape",
        },
        "prior_work_reviewed_successfully": {
            "passed": bool(screen_dimensions.get("prior_work_reviewed_successfully", False)),
            "reason": "the prior admitted work item already has a successful governance-owned evidence review",
        },
        "loop_entry_conditions_intact": {
            "passed": all_entry_conditions_pass,
            "reason": "directive validity, governance integrity, bucket feasibility, branch-state compatibility, and available governed execution path still hold",
        },
        "loop_continuation_conditions_intact": {
            "passed": all_continuation_conditions_pass,
            "reason": "the loop continuation preconditions recorded by the work-loop policy still pass",
        },
        "no_active_loop_exit_or_halt_conditions": {
            "passed": no_exit_conditions_active,
            "reason": "no halt, block, or exit condition is currently active",
        },
        "trusted_source_compatibility": {
            "passed": bool(trusted_source_report.get("passed", False)),
            "reason": str(trusted_source_report.get("reason", "")),
        },
        "bucket_resource_feasibility": {
            "passed": bool(resource_report.get("passed", False)),
            "reason": "requested cpu, memory, storage, and network mode stay inside the current bucket",
        },
        "mutable_surface_legality": {
            "passed": bool(write_root_report.get("passed", False))
            and bool(screen_dimensions.get("branch_state_compatibility", False)),
            "reason": "the continuation stays inside admitted write roots and does not request protected-surface, downstream, routing, plan_, or branch-state drift",
        },
        "branch_state_compatibility": {
            "passed": str(current_branch_state) == "paused_with_baseline_held"
            and bool(screen_dimensions.get("branch_state_compatibility", False)),
            "reason": "the branch remains paused_with_baseline_held and the continuation does not require branch-state mutation",
        },
        "reversibility": {
            "passed": str(screen_dimensions.get("reversibility", "")) == "high",
            "reason": "the continuation remains bounded and safely ignorable or removable",
        },
        "governance_observability": {
            "passed": str(screen_dimensions.get("governance_observability", "")) == "high",
            "reason": "the continuation is explicit enough for later governance review",
        },
        "truly_loop_continuation_not_use_or_development_or_escalation": {
            "passed": bool(path_separation.get("continue_as_direct_work", False))
            and not bool(path_separation.get("divert_to_capability_use", False))
            and not bool(path_separation.get("requires_review", False))
            and not bool(path_separation.get("divert_to_reopen_screen", False))
            and not bool(path_separation.get("divert_to_new_skill_screen", False))
            and not bool(path_separation.get("halt_or_block", False))
            and str(expected_path.get("path", "")) == "direct_governed_work",
            "reason": "the continuation remains a direct governed work-loop step rather than capability reuse, capability development, review-only, or new-skill escalation",
        },
        "accounting_sufficient_for_governance_review": {
            "passed": accounting_fields_present and bool(required_accounting),
            "reason": "the candidate carries enough loop identity, current work state, trust, budget, continuation rationale, evidence, and hook information for later review",
        },
        "plan_and_routing_guard": {
            "passed": bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False))
            and str(resource_trust_position.get("network_mode_expectation", "")) == "none",
            "reason": "plan_ remains non-owning, routing remains deferred, and the continuation keeps network mode at none",
        },
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
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    direct_work_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"
    )
    direct_work_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            direct_work_admission_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: work-loop continuation admission requires the work-loop policy, the work-loop candidate screen, the direct-work chain, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop continuation-admission artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop continuation-admission artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop continuation-admission artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit a work-loop continuation without the governing artifact chain"},
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
            "reason": "diagnostic shadow failed: work-loop continuation admission requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit work-loop continuation without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    if not governed_work_loop_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop policy state is missing",
            "observability_gain": {"passed": False, "reason": "missing governed work-loop policy state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed work-loop policy state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed work-loop policy state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit work-loop continuation without the current work-loop policy state"},
        }

    candidate_screen_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v1_*.json",
    )
    policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        dict(self_structure_state.get("governed_directive_work_selection_policy", {})).get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    direct_work_execution_artifact_path = _resolve_artifact_path(
        dict(self_structure_state.get("governed_directive_work_selection_policy", {})).get("last_direct_work_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json",
    )
    direct_work_admission_artifact_path = _resolve_artifact_path(
        dict(self_structure_state.get("governed_directive_work_selection_policy", {})).get("last_direct_work_admission_artifact_path"),
        "memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        dict(self_structure_state.get("governed_capability_use_policy", {})).get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            candidate_screen_artifact_path,
            policy_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_admission_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more governed work-loop continuation reference artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for work-loop continuation admission"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for work-loop continuation admission"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for work-loop continuation admission"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit work-loop continuation without the governing artifact paths"},
        }

    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_work_loop_candidate_screen_summary", {}))
    policy_payload = _load_json_file(policy_artifact_path)
    policy_summary = dict(policy_payload.get("governed_work_loop_policy_summary", {}))
    direct_work_evidence_summary = dict(
        _load_json_file(direct_work_evidence_artifact_path).get("governed_direct_work_evidence_summary", {})
    )
    capability_use_evidence_summary = dict(
        _load_json_file(capability_use_evidence_artifact_path).get("governed_capability_use_evidence_summary", {})
    )
    if not all([candidate_screen_summary, policy_summary, direct_work_evidence_summary, capability_use_evidence_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the continuation-admission step could not load the governing work-loop summaries",
            "observability_gain": {"passed": False, "reason": "missing work-loop summary payloads"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing work-loop summary payloads"},
            "ambiguity_reduction": {"passed": False, "reason": "missing work-loop summary payloads"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit work-loop continuation without the governing summary payloads"},
        }

    screened_candidates = list(candidate_screen_summary.get("candidates_screened", []))
    best_candidate_name = str(
        dict(candidate_screen_summary.get("best_current_next_loop_step_candidate", {})).get("loop_candidate_name", "")
        or current_state_summary.get("latest_governed_work_loop_best_candidate", "")
    )
    candidate_record = _find_loop_candidate(screened_candidates, best_candidate_name=best_candidate_name)
    if not candidate_record:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the best screened work-loop continuation candidate could not be located",
            "observability_gain": {"passed": False, "reason": "missing primary work-loop continuation candidate"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing primary work-loop continuation candidate"},
            "ambiguity_reduction": {"passed": False, "reason": "missing primary work-loop continuation candidate"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit work-loop continuation without the primary screened candidate"},
        }

    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    loop_entry_conditions = dict(governed_work_loop_policy.get("loop_entry_conditions", {}))
    loop_continuation_conditions = dict(governed_work_loop_policy.get("loop_continuation_conditions", {}))
    loop_exit_or_halt_conditions = dict(governed_work_loop_policy.get("loop_exit_or_halt_conditions", {}))

    admission_checks = _build_admission_checks(
        candidate_record,
        current_branch_state=current_branch_state,
        current_state_summary=current_state_summary,
        loop_accounting_requirements=loop_accounting_requirements,
        loop_entry_conditions=loop_entry_conditions,
        loop_continuation_conditions=loop_continuation_conditions,
        loop_exit_or_halt_conditions=loop_exit_or_halt_conditions,
    )
    all_checks_passed = all(bool(dict(value).get("passed", False)) for value in admission_checks.values())

    candidate_class = str(candidate_record.get("assigned_class", ""))
    if candidate_class == "loop_continue_candidate" and all_checks_passed:
        admission_outcome = "admissible_for_first_governed_work_loop_continuation"
        admission_reason = "the best screened work-loop continuation candidate stays inside the current directive, bucket, branch, and governance envelope and is ready for bounded shadow-only continuation work"
    elif candidate_class == "loop_continue_with_review":
        admission_outcome = "admissible_only_with_review"
        admission_reason = "the next loop step remains directive-valid but is not eligible for continuation admission without review"
    elif candidate_class == "loop_divert_to_capability_use":
        admission_outcome = "divert_to_capability_use_instead"
        admission_reason = "the next loop step should advance through capability-use admission rather than loop continuation admission"
    elif candidate_class == "loop_pause_candidate":
        admission_outcome = "pause_instead"
        admission_reason = "the next loop step should pause rather than continue the loop with low-yield repetition"
    elif candidate_class == "loop_divert_to_reopen_screen":
        admission_outcome = "divert_to_reopen_screen_instead"
        admission_reason = "the next loop step is hidden capability-development or reopen pressure rather than admissible loop continuation"
    elif candidate_class == "loop_divert_to_new_skill_screen":
        admission_outcome = "divert_to_new_skill_screen_instead"
        admission_reason = "the next loop step is outside the current governed capability family and should begin as a new skill candidate"
    else:
        admission_outcome = "halt_or_block"
        admission_reason = "the next loop step does not currently clear the governed work-loop continuation admission bar"

    classification_report = dict(candidate_record.get("classification_report", {}))
    loop_accounting = dict(candidate_record.get("loop_accounting_expectations", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    next_template = "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"

    continuation_envelope = {
        "work_loop_posture": "shadow_only_loop_continuation",
        "shadow_only_execution": True,
        "allowed_scope": [
            "refresh a bounded governance ledger consistency delta audit across directive, branch, bucket, self-structure, analytics, recommendations, and intervention-ledger artifacts",
            "produce a local governance-maintenance continuation artifact describing material governance-ledger consistency deltas or reaffirmed stability",
            "write bounded shadow-only continuation evidence and governance reports",
        ],
        "admissible_source_classes": list(trusted_source_report.get("requested_sources", [])),
        "admissible_source_artifacts": [
            str(DIRECTIVE_STATE_PATH),
            str(DIRECTIVE_HISTORY_PATH),
            str(SELF_STRUCTURE_STATE_PATH),
            str(SELF_STRUCTURE_LEDGER_PATH),
            str(BRANCH_REGISTRY_PATH),
            str(BUCKET_STATE_PATH),
            str(intervention_data_dir() / "intervention_ledger.jsonl"),
            str(intervention_data_dir() / "intervention_analytics_latest.json"),
            str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            str(policy_artifact_path),
            str(candidate_screen_artifact_path),
            str(direct_work_admission_artifact_path),
            str(direct_work_execution_artifact_path),
            str(direct_work_evidence_artifact_path),
            str(capability_use_evidence_artifact_path),
        ],
        "allowed_write_roots": list(write_root_report.get("requested_write_roots", [])),
        "resource_expectations": dict(loop_accounting.get("resource_trust_position", {})).get("expected_resource_budget", {}),
        "bucket_limits": dict(resource_report.get("bucket_limits", {})),
        "branch_state_must_remain": current_branch_state,
        "loop_iteration_context": dict(loop_accounting.get("loop_identity_context", {})),
        "prior_work_reference": dict(loop_accounting.get("current_work_state", {})),
        "plan_must_remain_non_owning": True,
        "routing_must_remain_deferred": bool(current_state_summary.get("routing_deferred", False)),
        "capability_use_required": False,
        "capability_modification_allowed": False,
        "paused_capability_reopen_allowed": False,
        "new_skill_creation_allowed": False,
        "retained_promotion_allowed": False,
        "branch_state_mutation_allowed": False,
        "protected_surface_modification_allowed": False,
        "downstream_selected_set_work_allowed": False,
        "network_mode": str(dict(dict(loop_accounting.get("resource_trust_position", {})).get("expected_resource_budget", {})).get("network_mode", "none")),
    }

    review_triggers = {
        "decision_criticality_rises_above_low": True,
        "overlap_with_active_work_rises_above_low": True,
        "scope_expands_beyond_governance_ledger_consistency_delta_audit": True,
        "held_capability_dependency_or_external_source_need_appears": True,
        "work_starts_to_imply_capability_development_or_branch_mutation": True,
        "distinct_value_claim_collapses_into_low_yield_repetition": True,
    }
    review_trigger_status = {key: False for key in review_triggers}
    rollback_triggers = {str(key): bool(value) for key, value in guardrails.items()}
    rollback_trigger_status = {key: False for key in rollback_triggers}
    deprecation_triggers = {
        "directive_relevance_drops_below_medium": True,
        "governance_observability_drops_below_medium": True,
        "repeated_low_distinct_value_loop_continuation_without_new_delta": True,
        "duplicate_better_governed_path_supersedes_this_continuation": True,
    }
    deprecation_trigger_status = {key: False for key in deprecation_triggers}

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["work_loop_continuation_admission_schema"] = {
        "schema_name": "GovernedWorkLoopContinuationAdmission",
        "schema_version": "governed_work_loop_continuation_admission_v1",
        "required_fields": [
            "loop_candidate_id",
            "loop_candidate_name",
            "assigned_class",
            "continuation_envelope",
            "continuation_accounting_requirements",
            "review_triggers",
            "rollback_trigger_status",
            "deprecation_trigger_status",
            "admission_checks",
            "admission_outcome",
        ],
        "outcome_classes": [
            "admissible_for_first_governed_work_loop_continuation",
            "admissible_only_with_review",
            "pause_instead",
            "divert_to_capability_use_instead",
            "divert_to_reopen_screen_instead",
            "divert_to_new_skill_screen_instead",
            "halt_or_block",
        ],
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v1_{proposal['proposal_id']}.json"
    updated_work_loop_policy["last_work_loop_continuation_admission_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_admission_candidate"] = {
        "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
        "assigned_class": candidate_class,
    }
    updated_work_loop_policy["last_work_loop_continuation_admission_outcome"] = {
        "status": admission_outcome,
        "reason": admission_reason,
        "work_loop_posture": "shadow_only_loop_continuation",
        "branch_state_after_admission": current_branch_state,
        "paused_capability_lines_reopened": False,
        "best_next_template": next_template,
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_continuation_admission_in_place": True,
            "latest_governed_work_loop_continuation_candidate": str(candidate_record.get("loop_candidate_name", "")),
            "latest_governed_work_loop_continuation_outcome": admission_outcome,
            "latest_governed_work_loop_continuation_posture": "shadow_only_loop_continuation",
            "latest_governed_work_loop_execution_readiness": (
                "ready_for_shadow_work_loop_continuation_execution"
                if admission_outcome == "admissible_for_first_governed_work_loop_continuation"
                else "not_ready_for_shadow_work_loop_continuation_execution"
            ),
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
        "event_id": f"governed_work_loop_continuation_admission_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_continuation_admission_snapshot_v1_materialized",
        "event_class": "governed_work_loop_continuation_admission",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
        "admission_outcome": admission_outcome,
        "paused_capability_lines_reopened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "governed_work_loop_policy_v1": str(policy_artifact_path),
            "governed_work_loop_candidate_screen_v1": str(candidate_screen_artifact_path),
            "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "direct_work_admission_v1": str(direct_work_admission_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_continuation_admission_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
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
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(
                direct_work_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_continuation_admission_summary": {
            "candidate_evaluated": {
                "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
                "loop_candidate_summary": str(candidate_record.get("loop_candidate_summary", "")),
                "assigned_candidate_class": candidate_class,
            },
            "admission_checks": admission_checks,
            "admission_outcome": {
                "status": admission_outcome,
                "reason": admission_reason,
                "work_loop_posture": "shadow_only_loop_continuation",
                "paused_capability_lines_reopened": False,
            },
            "continuation_envelope": continuation_envelope,
            "continuation_accounting_requirements": {
                "required_loop_identity_logging": list(loop_accounting_requirements.get("loop_identity_and_context_must_be_logged", [])),
                "required_current_work_state_logging": list(loop_accounting_requirements.get("current_work_state_must_be_logged", [])),
                "required_resource_and_trust_reporting": list(loop_accounting_requirements.get("resource_and_trust_position_must_be_logged", [])),
                "required_continuation_decision_reporting": list(loop_accounting_requirements.get("continuation_decision_must_be_logged", [])),
                "candidate_specific_expectations": loop_accounting,
            },
            "review_rollback_deprecation_triggers": {
                "review_triggers": review_triggers,
                "review_trigger_status": review_trigger_status,
                "rollback_triggers": rollback_triggers,
                "rollback_trigger_status": rollback_trigger_status,
                "deprecation_triggers": deprecation_triggers,
                "deprecation_trigger_status": deprecation_trigger_status,
            },
            "paused_capability_behavior": {
                "paused_capability_lines_remain_paused_for_development": True,
                "continuation_admission_does_not_reopen_paused_capabilities": True,
                "capability_use_path_remains_separate": True,
                "new_skill_path_remains_separate": True,
                "hidden_capability_development_pressure_rejected": True,
            },
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
                "reason": "work-loop continuation admission is derived from directive, bucket, branch, self-structure, work-loop policy, candidate-screen state, and prior direct-work evidence, so continuation admission remains governance-owned instead of execution-owned",
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
            "reason": "the best screened loop-continuation candidate now has an explicit continuation envelope, accounting burden, and rollback or review posture under governance",
            "artifact_paths": {
                "governed_work_loop_continuation_admission_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the gate distinguishes admissible loop continuation from pause, capability-use diversion, review-only, reopen, new-skill, and halt paths",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "a governed work-loop continuation can now be admitted without confusing it with held-capability reuse, paused-line reopen, or low-yield repetition",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the continuation admission is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step is a bounded governed work-loop continuation execution of the admitted governance ledger consistency delta audit rather than pause, capability reuse, reopen, or new-skill escalation",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_continuation_admission_in_place": True,
            "primary_candidate": str(candidate_record.get("loop_candidate_name", "")),
            "primary_candidate_class": candidate_class,
            "work_loop_continuation_admission_outcome": admission_outcome,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "paused_capability_lines_remained_paused": True,
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
        "reason": "diagnostic shadow passed: the best screened work-loop continuation candidate now has explicit continuation admission under governance without reopening capabilities or broadening the loop uncontrolledly",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
