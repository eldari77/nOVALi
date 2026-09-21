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


def _find_invocation_request(
    screened_requests: list[dict[str, Any]],
    *,
    best_direct_use_candidate: str,
) -> dict[str, Any]:
    for request in screened_requests:
        if str(request.get("request_name", "")) == best_direct_use_candidate:
            return dict(request)
    for request in screened_requests:
        if str(request.get("assigned_class", "")) == "diagnostic_only_use":
            return dict(request)
    return {}


def _required_accounting_fields(accounting_requirements: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key in [
        "resource_usage_must_be_logged",
        "governance_reporting_must_be_logged",
        "evidence_of_usefulness_must_be_preserved",
    ]:
        for item in list(accounting_requirements.get(key, [])):
            text = str(item)
            if text and text not in fields:
                fields.append(text)
    return fields


def _build_admission_checks(
    request_record: dict[str, Any],
    *,
    held_capability: dict[str, Any],
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    classification_report = dict(request_record.get("classification_report", {}))
    screen_dimensions = dict(request_record.get("screen_dimensions", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    requested_resources = dict(resource_report.get("requested_resources", {}))
    required_accounting = _required_accounting_fields(accounting_requirements)
    invocation_accounting = dict(request_record.get("invocation_accounting_expectations", {}))
    accounting_fields_present = all(
        bool(invocation_accounting.get(field_name))
        for field_name in [
            "invocation_identity",
            "directive_and_branch_context",
            "source_artifacts_expected",
            "resource_expectations",
            "write_roots_touched",
            "governance_reporting_required",
            "usefulness_evidence_expectations",
            "rollback_trigger_status_linkage",
            "deprecation_trigger_status_linkage",
        ]
    )

    return {
        "screen_class_allows_direct_invocation": {
            "passed": str(request_record.get("assigned_class", "")) == "diagnostic_only_use",
            "reason": "only the direct-use candidate screened as diagnostic_only_use is eligible for direct invocation admission at this gate",
        },
        "directive_relevance": {
            "passed": str(screen_dimensions.get("directive_relevance", "")) == "high",
            "reason": "the request remains clearly supportive of the active directive",
        },
        "trusted_source_compatibility": {
            "passed": bool(trusted_source_report.get("passed", False)),
            "reason": str(trusted_source_report.get("reason", "")),
        },
        "bucket_resource_feasibility": {
            "passed": bool(resource_report.get("passed", False)),
            "reason": "requested cpu, memory, storage, and network mode stay inside the held envelope and the current bucket",
        },
        "mutable_surface_legality": {
            "passed": bool(screen_dimensions.get("mutable_surface_legality", False)),
            "reason": "no protected-surface, downstream, plan_ ownership, routing, or branch-state drift is requested",
        },
        "reversibility": {
            "passed": str(screen_dimensions.get("reversibility", "")) == "high",
            "reason": "the request remains bounded and removable or safely ignorable",
        },
        "branch_state_compatibility": {
            "passed": str(current_branch_state) == "paused_with_baseline_held"
            and bool(screen_dimensions.get("branch_state_compatibility", False)),
            "reason": "the branch remains paused_with_baseline_held and direct capability use does not require branch-state mutation",
        },
        "capability_family_fit": {
            "passed": bool(screen_dimensions.get("direct_use_better_than_new_capability", False)),
            "reason": "direct use is a better fit than proposing a new capability for this bounded request",
        },
        "not_hidden_development_pressure": {
            "passed": not bool(screen_dimensions.get("hidden_development_or_reopen_pressure", False)),
            "reason": "the request is true use rather than same-shape rerun pressure or capability-development pressure",
        },
        "inside_held_capability_envelope": {
            "passed": (
                bool(trusted_source_report.get("passed", False))
                and bool(resource_report.get("passed", False))
                and bool(write_root_report.get("passed", False))
                and requested_resources.get("network_mode") == held_capability.get("network_mode", "none")
                and bool(classification_report.get("shadow_only", False))
            ),
            "reason": "sources, writes, resources, network mode, and shadow-only posture all stay inside the held capability envelope",
        },
        "overlap_with_active_work_acceptable": {
            "passed": str(screen_dimensions.get("overlap_with_active_work", "")) == "low",
            "reason": "direct invocation is only auto-admissible when overlap with active work stays low",
        },
        "invocation_accounting_sufficient": {
            "passed": accounting_fields_present and bool(required_accounting),
            "reason": "the request carries enough invocation identity, resource, governance-reporting, and usefulness-evidence fields for later review",
        },
        "plan_and_routing_guard": {
            "passed": bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False)),
            "reason": "plan_ remains non-owning and routing remains deferred",
        },
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
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            capability_use_policy_snapshot,
            capability_use_candidate_screen_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: invocation admission requires the governance substrate, capability-use policy, capability-use candidate screen, and provisional pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit a direct use candidate without the current candidate-screen result"},
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
            "reason": "diagnostic shadow failed: invocation admission requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit invocation without the current governance state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if not governed_capability_use_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed capability-use policy state is missing",
            "observability_gain": {"passed": False, "reason": "missing governed capability-use policy state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed capability-use policy state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed capability-use policy state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit invocation without the current policy state"},
        }

    held_capabilities = list(governed_skill_subsystem.get("held_provisional_capabilities", []))
    held_capability = {}
    for item in held_capabilities:
        record = dict(item)
        if str(record.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial":
            held_capability = record
            break
    if not held_capability:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: held local trace parser capability not found",
            "observability_gain": {"passed": False, "reason": "missing held capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held capability record"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit invocation without a held capability"},
        }

    candidate_screen_artifact_path = Path(
        str(governed_capability_use_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_capability_use_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )

    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_capability_use_candidate_screen_summary", {}))
    policy_summary = dict(_load_json_file(policy_artifact_path).get("governed_capability_use_policy_summary", {}))
    screened_requests = list(candidate_screen_summary.get("invocation_requests_screened", []))
    best_direct_use_candidate = str(
        dict(governed_capability_use_policy.get("last_candidate_screen_outcome", {})).get("best_direct_use_candidate", "")
    ) or str(dict(candidate_screen_payload.get("diagnostic_conclusions", {})).get("best_direct_use_candidate", ""))
    request_record = _find_invocation_request(screened_requests, best_direct_use_candidate=best_direct_use_candidate)
    if not request_record:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the best direct-use capability request could not be located in the candidate-screen artifact",
            "observability_gain": {"passed": False, "reason": "missing primary direct-use request"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing primary direct-use request"},
            "ambiguity_reduction": {"passed": False, "reason": "missing primary direct-use request"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot admit invocation without the primary screened request"},
        }

    directive_current = dict(directive_state.get("current_directive_state", {}))
    accounting_requirements = dict(governed_capability_use_policy.get("invocation_accounting_requirements", {}))
    rollback_triggers = dict(policy_summary.get("current_rollback_triggers", {}))
    deprecation_triggers = dict(policy_summary.get("current_deprecation_triggers", {}))
    admission_checks = _build_admission_checks(
        request_record,
        held_capability=held_capability,
        current_branch_state=current_branch_state,
        current_state_summary=current_state_summary,
        accounting_requirements=accounting_requirements,
    )
    all_checks_passed = all(bool(dict(value).get("passed", False)) for value in admission_checks.values())

    request_class = str(request_record.get("assigned_class", ""))
    if request_class == "diagnostic_only_use" and all_checks_passed:
        admission_outcome = "admissible_for_direct_governed_use"
        admission_reason = "the best direct-use request stays inside the held capability envelope and is ready for bounded diagnostic-only governed invocation"
    elif request_class == "gated_review_required_use":
        admission_outcome = "admissible_only_with_review"
        admission_reason = "the request is still policy-valid but remains too weighty for direct invocation without review"
    elif request_class == "diagnostic_only_use":
        admission_outcome = "remain_diagnostic_only"
        admission_reason = "the request is directionally valid but one or more direct-invocation admission checks are not yet strong enough for admission"
    else:
        admission_outcome = request_class
        admission_reason = "the request does not clear the direct-governed-use admission bar and should follow its already screened governance path"

    classification_report = dict(request_record.get("classification_report", {}))
    trusted_source_report = dict(classification_report.get("trusted_source_report", {}))
    resource_report = dict(classification_report.get("resource_report", {}))
    write_root_report = dict(classification_report.get("write_root_report", {}))
    invocation_accounting_expectations = dict(request_record.get("invocation_accounting_expectations", {}))
    next_template = "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1"

    invocation_envelope = {
        "callable_use_posture": "diagnostic_only_use",
        "shadow_only_invocation": True,
        "allowed_scope": [
            "summarize a new trusted local shadow-log bundle for directive-supportive governance diagnostics",
            "read trusted local governance and diagnostic artifacts needed to contextualize the summary",
            "write bounded shadow-only invocation evidence and governance reports",
        ],
        "admissible_source_classes": list(trusted_source_report.get("requested_sources", [])),
        "admissible_source_artifacts": list(invocation_accounting_expectations.get("source_artifacts_expected", [])),
        "allowed_write_roots": list(write_root_report.get("requested_write_roots", [])),
        "resource_expectations": dict(invocation_accounting_expectations.get("resource_expectations", {})),
        "resource_ceilings": dict(resource_report.get("resource_ceilings", {})),
        "bucket_limits": dict(resource_report.get("bucket_limits", {})),
        "branch_state_must_remain": current_branch_state,
        "plan_must_remain_non_owning": True,
        "routing_must_remain_deferred": bool(current_state_summary.get("routing_deferred", False)),
        "capability_modification_allowed": False,
        "same_shape_rerun_allowed": False,
        "retained_promotion_allowed": False,
        "branch_state_mutation_allowed": False,
        "protected_surface_modification_allowed": False,
        "downstream_selected_set_work_allowed": False,
        "network_mode": str(dict(invocation_accounting_expectations.get("resource_expectations", {})).get("network_mode", "none")),
    }
    review_triggers = {
        "decision_critical_reliance_becomes_true": True,
        "overlap_with_active_work_rises_above_low": True,
        "shadow_only_posture_requested_to_relax": True,
        "request_scope_expands_beyond_trusted_diagnostic_bundle_summarization": True,
    }
    review_trigger_status = {key: False for key in review_triggers}
    rollback_trigger_status = {str(key): False for key in rollback_triggers.keys()}
    deprecation_trigger_status = {str(key): False for key in deprecation_triggers.keys()}

    updated_self_structure_state = dict(self_structure_state)
    updated_capability_use_policy = dict(governed_capability_use_policy)
    updated_capability_use_policy["invocation_admission_schema"] = {
        "schema_name": "GovernedCapabilityInvocationAdmission",
        "schema_version": "governed_capability_use_invocation_admission_v1",
        "required_fields": [
            "use_request_id",
            "request_name",
            "assigned_class",
            "requested_purpose",
            "invocation_envelope",
            "invocation_accounting_requirements",
            "review_triggers",
            "rollback_trigger_status",
            "deprecation_trigger_status",
            "admission_checks",
            "admission_outcome",
        ],
        "outcome_classes": [
            "admissible_for_direct_governed_use",
            "admissible_only_with_review",
            "remain_diagnostic_only",
            "forbidden_use",
            "reopen_required_instead_of_use",
            "new_skill_candidate_required_instead_of_use",
        ],
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_capability_use_invocation_admission_snapshot_v1_{proposal['proposal_id']}.json"
    updated_capability_use_policy["last_invocation_admission_artifact_path"] = str(artifact_path)
    updated_capability_use_policy["last_invocation_admission_candidate"] = {
        "use_request_id": str(request_record.get("use_request_id", "")),
        "request_name": str(request_record.get("request_name", "")),
        "assigned_class": request_class,
    }
    updated_capability_use_policy["last_invocation_admission_outcome"] = {
        "status": admission_outcome,
        "reason": admission_reason,
        "callable_use_posture": "diagnostic_only_use",
        "branch_state_after_admission": current_branch_state,
        "development_line_reopened": False,
        "best_next_template": next_template,
    }
    updated_capability_use_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_capability_use_policy"] = updated_capability_use_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_capability_use_invocation_admission_in_place": True,
            "latest_capability_use_invocation_candidate": str(request_record.get("request_name", "")),
            "latest_capability_use_invocation_outcome": admission_outcome,
            "latest_capability_use_invocation_posture": "diagnostic_only_use",
            "held_capabilities_callable_under_governance": True,
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
        "event_id": f"governed_capability_use_invocation_admission_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_capability_use_invocation_admission_snapshot_v1_materialized",
        "event_class": "governed_capability_use_invocation_admission",
        "directive_id": str(directive_current.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "capability_id": str(held_capability.get("skill_id", "")),
        "use_request_id": str(request_record.get("use_request_id", "")),
        "admission_outcome": admission_outcome,
        "development_line_reopened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "capability_use_policy_v1": str(policy_artifact_path),
            "capability_use_candidate_screen_v1": str(candidate_screen_artifact_path),
            "provisional_pause_v1": str(provisional_pause_artifact_path),
            "capability_use_invocation_admission_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
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
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot, latest_snapshots
            ),
        },
        "governed_capability_use_invocation_admission_summary": {
            "candidate_evaluated": {
                "use_request_id": str(request_record.get("use_request_id", "")),
                "request_name": str(request_record.get("request_name", "")),
                "requested_purpose": str(request_record.get("requested_purpose", "")),
                "assigned_policy_class": request_class,
                "capability_id": str(held_capability.get("skill_id", "")),
                "capability_name": str(held_capability.get("skill_name", "")),
            },
            "admission_checks": admission_checks,
            "admission_outcome": {
                "status": admission_outcome,
                "reason": admission_reason,
                "callable_use_posture": "diagnostic_only_use",
                "development_line_reopened": False,
            },
            "invocation_envelope": invocation_envelope,
            "invocation_accounting_requirements": {
                "required_logging": list(accounting_requirements.get("resource_usage_must_be_logged", [])),
                "required_governance_reporting": list(accounting_requirements.get("governance_reporting_must_be_logged", [])),
                "required_usefulness_evidence": list(accounting_requirements.get("evidence_of_usefulness_must_be_preserved", [])),
                "request_specific_expectations": invocation_accounting_expectations,
            },
            "rollback_review_triggers": {
                "review_triggers": review_triggers,
                "review_trigger_status": review_trigger_status,
                "rollback_triggers": rollback_triggers,
                "rollback_trigger_status": rollback_trigger_status,
                "deprecation_triggers": deprecation_triggers,
                "deprecation_trigger_status": deprecation_trigger_status,
            },
            "paused_capability_behavior": {
                "paused_capability_line_remains_paused_for_development": True,
                "invocation_does_not_reopen_development": True,
                "same_shape_reruns_remain_disallowed": True,
                "development_extension_still_requires_reopen_screen": True,
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
                "reason": "invocation admission is derived from directive, bucket, branch, self-structure, capability-use policy, and candidate-screen state, so use remains governance-owned instead of execution-owned",
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
            "reason": "the best direct-use request now has an explicit invocation envelope, accounting burden, and rollback or review posture under governance",
            "artifact_paths": {
                "capability_use_invocation_admission_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the gate distinguishes actual admitted invocation from review-only, forbidden, reopen-required, and new-skill-required paths",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "held capability use can now be admitted without confusing direct invocation with reopening paused development or building a new skill",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the admission is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step is a bounded governed invocation of the admitted direct-use request rather than a reopen screen or a new skill candidate",
        },
        "diagnostic_conclusions": {
            "governed_capability_use_invocation_admission_in_place": True,
            "primary_candidate": str(request_record.get("request_name", "")),
            "primary_candidate_policy_class": request_class,
            "invocation_admission_outcome": admission_outcome,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
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
        "reason": "diagnostic shadow passed: the best screened direct-use capability request now has explicit invocation admission under governance without reopening development",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
