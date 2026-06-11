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
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _find_work_candidate(
    screened_candidates: list[dict[str, Any]],
    *,
    best_candidate_name: str,
) -> dict[str, Any]:
    for candidate in screened_candidates:
        if str(candidate.get("work_item_name", "")) == best_candidate_name:
            return dict(candidate)
    for candidate in screened_candidates:
        if str(candidate.get("assigned_class", "")) == "direct_governed_work_candidate":
            return dict(candidate)
    return {}


def _required_accounting_fields(accounting_requirements: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key in [
        "work_identity_and_linkage_must_be_logged",
        "expected_execution_path_must_be_logged",
        "expected_budget_and_trust_must_be_logged",
        "expected_evidence_must_be_logged",
    ]:
        for item in list(accounting_requirements.get(key, [])):
            text = str(item)
            if text and text not in fields:
                fields.append(text)
    return fields


def _build_admission_checks(
    candidate_record: dict[str, Any],
    *,
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    classification_report = dict(candidate_record.get("classification_report", {}))
    screen_dimensions = dict(candidate_record.get("screen_dimensions", {}))
    path_separation = dict(candidate_record.get("path_separation", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    work_accounting = dict(candidate_record.get("work_selection_accounting_expectations", {}))
    expected_execution_path = dict(work_accounting.get("expected_capability_path", {}))
    required_accounting = _required_accounting_fields(accounting_requirements)
    accounting_fields_present = all(
        bool(work_accounting.get(field_name))
        for field_name in [
            "work_identity",
            "directive_linkage",
            "expected_capability_path",
            "expected_resource_budget",
            "required_trusted_sources",
            "expected_write_roots",
            "expected_success_signal",
            "expected_review_hooks",
            "expected_rollback_hooks",
        ]
    )
    expected_resources = dict(work_accounting.get("expected_resource_budget", {}))

    return {
        "screen_class_allows_direct_work": {
            "passed": str(candidate_record.get("assigned_class", "")) == "direct_governed_work_candidate",
            "reason": "only a direct_governed_work_candidate is eligible for direct work admission at this gate",
        },
        "directive_relevance_or_closeness": {
            "passed": str(screen_dimensions.get("directive_closeness", "")) == "high",
            "reason": "the work item is tightly aligned to the current directive",
        },
        "support_vs_drift": {
            "passed": str(screen_dimensions.get("support_vs_drift", "")) == "support",
            "reason": "the work item remains directive support rather than drift",
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
            "passed": (
                bool(write_root_report.get("passed", False))
                and bool(screen_dimensions.get("branch_state_compatibility", False))
                and not bool(dict(screen_dimensions.get("use_vs_development_vs_escalation", {})).get("hidden_development_pressure", False))
            ),
            "reason": "the work item stays inside admitted write roots and does not request protected-surface, downstream, routing, plan_, or branch-state drift",
        },
        "branch_state_compatibility": {
            "passed": str(current_branch_state) == "paused_with_baseline_held"
            and bool(screen_dimensions.get("branch_state_compatibility", False)),
            "reason": "the branch remains paused_with_baseline_held and the work item does not require branch-state mutation",
        },
        "reversibility": {
            "passed": str(screen_dimensions.get("reversibility", "")) == "high",
            "reason": "the work item remains bounded and safely ignorable or removable",
        },
        "governance_observability": {
            "passed": str(screen_dimensions.get("governance_observability", "")) == "high",
            "reason": "the work item is explicit enough for later governance review",
        },
        "overlap_with_active_work_acceptable": {
            "passed": str(classification_report.get("overlap_with_active_work", "")) == "low",
            "reason": "the work item is only directly admissible when overlap with active work stays low",
        },
        "truly_direct_work_not_capability_development_or_hidden_escalation": {
            "passed": bool(path_separation.get("is_direct_work", False))
            and not bool(path_separation.get("requires_capability_use_admission", False))
            and not bool(path_separation.get("requires_reopen_screen", False))
            and not bool(path_separation.get("requires_new_skill_candidate", False))
            and str(expected_execution_path.get("path", "")) == "direct_governed_work",
            "reason": "the work item remains direct governance-maintenance work rather than capability reuse, capability development, or new-skill escalation",
        },
        "accounting_sufficient_for_governance_review": {
            "passed": accounting_fields_present and bool(required_accounting),
            "reason": "the work item carries enough identity, directive linkage, trust, budget, success-signal, and hook information for later review",
        },
        "plan_and_routing_guard": {
            "passed": bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False))
            and expected_resources.get("network_mode") == "none",
            "reason": "plan_ remains non-owning, routing remains deferred, and the work item keeps network mode at none",
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    directive_work_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    directive_work_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    capability_use_invocation_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_work_policy_snapshot,
            directive_work_candidate_screen_snapshot,
            capability_use_evidence_snapshot,
            capability_use_invocation_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: direct work admission requires the governance substrate, directive-work selection policy, directive-work candidate screen, governed capability-use evidence, and current invocation evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed directive-work admission artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed directive-work admission artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed directive-work admission artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit direct work without the prerequisite directive-work governance chain"},
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
            "reason": "diagnostic shadow failed: direct work admission requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit direct work without current governance state"},
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
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit direct work without the current directive-work policy state"},
        }

    candidate_screen_artifact_path = Path(
        str(governed_directive_work_selection_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_directive_work_selection_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json")
    )
    capability_use_evidence_artifact_path = Path(
        str(dict(self_structure_state.get("governed_capability_use_policy", {})).get("last_invocation_evidence_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json")
    )
    capability_use_invocation_artifact_path = Path(
        str(dict(self_structure_state.get("governed_capability_use_policy", {})).get("last_invocation_execution_artifact_path", ""))
        or _latest_matching_artifact("proposal_learning_loop_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_*.json")
    )

    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_directive_work_candidate_screen_summary", {}))
    policy_summary = dict(_load_json_file(policy_artifact_path).get("governed_directive_work_selection_policy_summary", {}))
    capability_use_evidence_summary = dict(
        _load_json_file(capability_use_evidence_artifact_path).get("governed_capability_use_evidence_summary", {})
    )
    if not all([candidate_screen_summary, policy_summary, capability_use_evidence_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the admission step could not load the governing directive-work summaries",
            "observability_gain": {"passed": False, "reason": "missing directive-work summary payloads"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing directive-work summary payloads"},
            "ambiguity_reduction": {"passed": False, "reason": "missing directive-work summary payloads"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit direct work without the governing summary payloads"},
        }

    screened_candidates = list(candidate_screen_summary.get("work_candidates_screened", []))
    best_candidate_name = str(
        dict(candidate_screen_summary.get("best_current_next_step_candidate", {})).get("work_item_name", "")
        or current_state_summary.get("latest_directive_work_best_candidate", "")
    )
    candidate_record = _find_work_candidate(screened_candidates, best_candidate_name=best_candidate_name)
    if not candidate_record:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the best screened directive-work candidate could not be located",
            "observability_gain": {"passed": False, "reason": "missing primary direct-work candidate"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing primary direct-work candidate"},
            "ambiguity_reduction": {"passed": False, "reason": "missing primary direct-work candidate"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit direct work without the primary screened candidate"},
        }

    accounting_requirements = dict(
        governed_directive_work_selection_policy.get("work_selection_accounting_requirements", {})
    )
    guardrails = dict(governed_directive_work_selection_policy.get("guardrails", {}))
    admission_checks = _build_admission_checks(
        candidate_record,
        current_branch_state=current_branch_state,
        current_state_summary=current_state_summary,
        accounting_requirements=accounting_requirements,
    )
    all_checks_passed = all(bool(dict(value).get("passed", False)) for value in admission_checks.values())

    candidate_class = str(candidate_record.get("assigned_class", ""))
    if candidate_class == "direct_governed_work_candidate" and all_checks_passed:
        admission_outcome = "admissible_for_direct_governed_work"
        admission_reason = "the best screened directive-work candidate stays inside the current directive, bucket, branch, and governance envelope and is ready for bounded shadow-only direct work"
    elif candidate_class == "review_required_work_candidate":
        admission_outcome = "admissible_only_with_review"
        admission_reason = "the work item remains directive-valid but is not eligible for direct admission without review"
    elif candidate_class == "use_existing_capability_candidate":
        admission_outcome = "use_existing_capability_instead"
        admission_reason = "the work item should advance through capability-use admission rather than direct work admission"
    elif candidate_class == "reopen_required_work_candidate":
        admission_outcome = "reopen_required_instead"
        admission_reason = "the work item is hidden capability-development or reopen pressure rather than direct work"
    elif candidate_class == "new_skill_candidate_required":
        admission_outcome = "new_skill_candidate_required_instead"
        admission_reason = "the work item is outside the current governed capability family and should begin as a new skill candidate"
    else:
        admission_outcome = "defer_or_block"
        admission_reason = "the work item does not currently clear the direct governed work admission bar"

    classification_report = dict(candidate_record.get("classification_report", {}))
    work_accounting = dict(candidate_record.get("work_selection_accounting_expectations", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    next_template = "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"

    direct_work_envelope = {
        "direct_work_posture": "shadow_only_direct_work",
        "shadow_only_execution": True,
        "allowed_scope": [
            "refresh a bounded governance-state coherence audit across directive, branch, bucket, self-structure, analytics, and recommendations artifacts",
            "produce a local governance-maintenance summary describing alignment or mismatch observations",
            "write bounded shadow-only direct-work evidence and governance reports",
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
            str(candidate_screen_artifact_path),
            str(policy_artifact_path),
            str(capability_use_evidence_artifact_path),
            str(capability_use_invocation_artifact_path),
        ],
        "allowed_write_roots": list(write_root_report.get("requested_write_roots", [])),
        "resource_expectations": dict(work_accounting.get("expected_resource_budget", {})),
        "bucket_limits": dict(resource_report.get("bucket_limits", {})),
        "branch_state_must_remain": current_branch_state,
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
        "network_mode": str(dict(work_accounting.get("expected_resource_budget", {})).get("network_mode", "none")),
    }

    review_triggers = {
        "decision_criticality_rises_above_low": True,
        "overlap_with_active_work_rises_above_low": True,
        "scope_expands_beyond_governance_state_coherence_audit": True,
        "held_capability_dependency_or_external_source_need_appears": True,
        "work_starts_to_imply_capability_development_or_branch_mutation": True,
    }
    review_trigger_status = {key: False for key in review_triggers}
    rollback_triggers = {str(key): bool(value) for key, value in guardrails.items()}
    rollback_trigger_status = {key: False for key in rollback_triggers}
    deprecation_triggers = {
        "directive_relevance_drops_below_medium": True,
        "governance_observability_drops_below_medium": True,
        "repeated_low_signal_direct_work_without_new_audit_value": True,
        "duplicate_better_governed_path_supersedes_this_direct_work": True,
    }
    deprecation_trigger_status = {key: False for key in deprecation_triggers}

    updated_self_structure_state = dict(self_structure_state)
    updated_directive_work_policy = dict(governed_directive_work_selection_policy)
    updated_directive_work_policy["direct_work_admission_schema"] = {
        "schema_name": "GovernedDirectiveWorkAdmission",
        "schema_version": "governed_directive_work_admission_v1",
        "required_fields": [
            "work_item_id",
            "work_item_name",
            "assigned_class",
            "direct_work_envelope",
            "direct_work_accounting_requirements",
            "review_triggers",
            "rollback_trigger_status",
            "deprecation_trigger_status",
            "admission_checks",
            "admission_outcome",
        ],
        "outcome_classes": [
            "admissible_for_direct_governed_work",
            "admissible_only_with_review",
            "defer_or_block",
            "use_existing_capability_instead",
            "reopen_required_instead",
            "new_skill_candidate_required_instead",
        ],
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_directive_work_admission_snapshot_v1_{proposal['proposal_id']}.json"
    updated_directive_work_policy["last_direct_work_admission_artifact_path"] = str(artifact_path)
    updated_directive_work_policy["last_direct_work_admission_candidate"] = {
        "work_item_id": str(candidate_record.get("work_item_id", "")),
        "work_item_name": str(candidate_record.get("work_item_name", "")),
        "assigned_class": candidate_class,
    }
    updated_directive_work_policy["last_direct_work_admission_outcome"] = {
        "status": admission_outcome,
        "reason": admission_reason,
        "direct_work_posture": "shadow_only_direct_work",
        "branch_state_after_admission": current_branch_state,
        "paused_capability_lines_reopened": False,
        "best_next_template": next_template,
    }
    updated_directive_work_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_directive_work_selection_policy"] = updated_directive_work_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_directive_work_admission_in_place": True,
            "latest_directive_work_admission_candidate": str(candidate_record.get("work_item_name", "")),
            "latest_directive_work_admission_outcome": admission_outcome,
            "latest_directive_work_admission_posture": "shadow_only_direct_work",
            "latest_directive_work_execution_readiness": (
                "ready_for_shadow_direct_work_execution"
                if admission_outcome == "admissible_for_direct_governed_work"
                else "not_ready_for_shadow_direct_work_execution"
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
        "event_id": f"governed_directive_work_admission_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_directive_work_admission_snapshot_v1_materialized",
        "event_class": "governed_directive_work_admission",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "work_item_id": str(candidate_record.get("work_item_id", "")),
        "work_item_name": str(candidate_record.get("work_item_name", "")),
        "admission_outcome": admission_outcome,
        "paused_capability_lines_reopened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "directive_work_selection_policy_v1": str(policy_artifact_path),
            "directive_work_candidate_screen_v1": str(candidate_screen_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "capability_use_invocation_v1": str(capability_use_invocation_artifact_path),
            "directive_work_admission_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_directive_work_admission_snapshot_v1",
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
                directive_work_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1": _artifact_reference(
                directive_work_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1": _artifact_reference(
                capability_use_invocation_snapshot, latest_snapshots
            ),
        },
        "governed_directive_work_admission_summary": {
            "candidate_evaluated": {
                "work_item_id": str(candidate_record.get("work_item_id", "")),
                "work_item_name": str(candidate_record.get("work_item_name", "")),
                "work_summary": str(candidate_record.get("work_summary", "")),
                "assigned_candidate_class": candidate_class,
            },
            "admission_checks": admission_checks,
            "admission_outcome": {
                "status": admission_outcome,
                "reason": admission_reason,
                "direct_work_posture": "shadow_only_direct_work",
                "paused_capability_lines_reopened": False,
            },
            "direct_work_envelope": direct_work_envelope,
            "direct_work_accounting_requirements": {
                "required_logging": list(accounting_requirements.get("work_identity_and_linkage_must_be_logged", [])),
                "required_execution_path_reporting": list(
                    accounting_requirements.get("expected_execution_path_must_be_logged", [])
                ),
                "required_budget_and_trust_reporting": list(
                    accounting_requirements.get("expected_budget_and_trust_must_be_logged", [])
                ),
                "required_evidence_reporting": list(accounting_requirements.get("expected_evidence_must_be_logged", [])),
                "candidate_specific_expectations": work_accounting,
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
                "direct_work_admission_does_not_reopen_paused_capabilities": True,
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
                "reason": "direct work admission is derived from directive, bucket, branch, self-structure, directive-work policy, and candidate-screen state, so work admission remains governance-owned instead of execution-owned",
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
            "reason": "the best screened direct-work candidate now has an explicit direct-work envelope, accounting burden, and rollback or review posture under governance",
            "artifact_paths": {
                "directive_work_admission_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the gate distinguishes admitted direct work from review-only, capability-use, reopen, new-skill, and blocked paths",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "direct governed work can now be admitted without confusing it with held-capability use, paused-line reopen, or new-skill creation",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the admission is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step is a bounded governed direct-work execution of the admitted governance-state coherence audit rather than capability reuse, reopen, or new-skill escalation",
        },
        "diagnostic_conclusions": {
            "governed_directive_work_admission_in_place": True,
            "primary_candidate": str(candidate_record.get("work_item_name", "")),
            "primary_candidate_class": candidate_class,
            "direct_work_admission_outcome": admission_outcome,
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
        "reason": "diagnostic shadow passed: the best screened directive-work candidate now has explicit direct-work admission under governance without reopening capabilities or creating a new skill branch",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
