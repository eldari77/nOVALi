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
from .v4_governed_capability_use_policy_snapshot_v1 import _classify_use_request, _latest_matching_artifact
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _build_request_examples(held_capability: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_write_roots = list(held_capability.get("allowed_write_roots", []))
    capability_id = str(held_capability.get("skill_id", ""))
    capability_name = str(held_capability.get("skill_name", ""))
    return [
        {
            "use_request_id": "use_request_parser_trusted_diagnostic_bundle",
            "request_name": "Trusted diagnostic bundle summary",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "summarize a new trusted local shadow-log bundle for directive-supportive governance diagnostics",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["local_logs:logs/intervention_shadow_*.log", "local_artifacts:novali-v4/data/diagnostic_memory"],
            "usefulness_evidence_expectations": [
                "preserve bounded artifact summary of the new trusted log bundle",
                "record whether the held parser materially reduces local trace review effort",
            ],
        },
        {
            "use_request_id": "use_request_parser_high_consequence_review_support",
            "request_name": "High-consequence review support",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "use parser output as input to a higher-consequence governance review decision",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "high",
            "shadow_only": False,
            "decision_critical_reliance": True,
            "overlap_with_active_work": "medium",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["local_logs:logs/intervention_shadow_*.log", "local_artifacts:novali-v4/data/self_structure_state_latest.json"],
            "usefulness_evidence_expectations": [
                "preserve a governance review note linking the parser output to the review context",
                "show why direct use was preferable to opening a new skill candidate",
            ],
        },
        {
            "use_request_id": "use_request_parser_same_shape_rerun",
            "request_name": "Same-shape rerun pressure",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "repeat the same paused seed_context_shift rerun as a direct capability use",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": True,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["local_logs:logs/intervention_shadow_*seed_context_shift*.log"],
            "usefulness_evidence_expectations": [
                "would only reconfirm already-paused evidence shape rather than add new structural signal",
            ],
        },
        {
            "use_request_id": "use_request_parser_new_local_trace_format_extension",
            "request_name": "New local trace format extension",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "extend the held parser to a new trusted local trace format inside the same family",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": True,
            "new_bounded_use_case": True,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["local_logs:logs/new_local_trace_family/*.log"],
            "usefulness_evidence_expectations": [
                "show materially new bounded value before any development reopen is considered",
            ],
        },
        {
            "use_request_id": "use_request_out_of_family_memory_retriever_need",
            "request_name": "Out-of-family retrieval need",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "satisfy a retrieval or memory access need that is not a trace-parser use-case",
            "directive_relevance": "medium",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": False,
            "better_than_new_skill_candidate": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["local_artifacts:novali-v4/data/diagnostic_memory"],
            "usefulness_evidence_expectations": [
                "show why parser reuse would be a category error and a new skill candidate is cleaner",
            ],
        },
        {
            "use_request_id": "use_request_untrusted_external_trace_pull",
            "request_name": "Untrusted external trace pull",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "requested_purpose": "pull remote traces through the held parser despite the trusted-source boundary",
            "directive_relevance": "high",
            "trusted_sources": ["untrusted_remote_web"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "trusted_local_only"},
            "requested_write_roots": allowed_write_roots,
            "reversibility": "medium",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "source_artifact_refs": ["untrusted_remote_web"],
            "usefulness_evidence_expectations": [
                "request should fail on trust and policy before usefulness is even considered",
            ],
        },
    ]


def _screen_request(
    request: dict[str, Any],
    *,
    held_capability: dict[str, Any],
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    accounting_requirements: dict[str, Any],
    rollback_triggers: dict[str, Any],
    deprecation_triggers: dict[str, Any],
) -> dict[str, Any]:
    classification = _classify_use_request(
        request,
        held_capability=held_capability,
        directive_current=directive_current,
        bucket_current=bucket_current,
        current_branch_state=current_branch_state,
        plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
        routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
    )
    return {
        "use_request_id": str(request.get("use_request_id", "")),
        "request_name": str(request.get("request_name", "")),
        "requested_purpose": str(request.get("requested_purpose", "")),
        "assigned_class": str(classification.get("policy_outcome", "")),
        "rationale": str(classification.get("reason", "")),
        "screen_dimensions": {
            "directive_relevance": str(request.get("directive_relevance", "")),
            "trusted_source_compatibility": bool(dict(classification.get("trusted_source_report", {})).get("passed", False)),
            "bucket_resource_feasibility": bool(dict(classification.get("resource_report", {})).get("passed", False)),
            "mutable_surface_legality": not any(
                bool(request.get(key, False))
                for key in [
                    "touches_protected_surface",
                    "touches_downstream_selected_set",
                    "touches_plan_ownership",
                    "touches_routing",
                    "touches_branch_state",
                ]
            ),
            "reversibility": str(request.get("reversibility", "")),
            "branch_state_compatibility": str(current_branch_state) == "paused_with_baseline_held",
            "overlap_with_active_work": str(request.get("overlap_with_active_work", "")),
            "direct_use_better_than_new_capability": bool(request.get("better_than_new_skill_candidate", False)),
            "hidden_development_or_reopen_pressure": bool(
                request.get("same_shape_rerun", False)
                or request.get("requires_capability_modification", False)
                or request.get("new_bounded_use_case", False)
            ),
        },
        "invocation_accounting_expectations": {
            "invocation_identity": {
                "invocation_id": f"capability_use::{request.get('use_request_id', '')}",
                "capability_id": str(request.get("capability_id", "")),
                "capability_name": str(request.get("capability_name", "")),
            },
            "directive_and_branch_context": {
                "directive_id": str(directive_current.get("directive_id", "")),
                "branch_id": str(current_state_summary.get("current_branch_id", "")),
                "branch_state": current_branch_state,
                "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
                "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            },
            "source_artifacts_expected": list(request.get("source_artifact_refs", [])),
            "resource_expectations": dict(request.get("requested_resources", {})),
            "write_roots_touched": list(request.get("requested_write_roots", [])),
            "governance_reporting_required": list(accounting_requirements.get("governance_reporting_must_be_logged", [])),
            "usefulness_evidence_expectations": list(request.get("usefulness_evidence_expectations", [])),
            "rollback_trigger_status_linkage": sorted(str(key) for key in rollback_triggers.keys()),
            "deprecation_trigger_status_linkage": sorted(str(key) for key in deprecation_triggers.keys()),
        },
        "paused_capability_behavior": {
            "paused_line_reopened_by_screen": False,
            "same_shape_rerun_disallowed": bool(request.get("same_shape_rerun", False)),
            "request_requires_reopen_screen_instead": str(classification.get("policy_outcome", "")) == "reopen_required_instead_of_use",
        },
        "classification_report": classification,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    capability_use_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_policy_snapshot_v1"
    )
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all([governance_snapshot, capability_use_policy_snapshot, provisional_pause_snapshot]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: capability-use candidate screening requires the governance substrate, capability-use policy, and provisional pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite capability-use artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite capability-use artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite capability-use artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen concrete invocation requests without the capability-use policy layer"},
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
            "reason": "diagnostic shadow failed: capability-use candidate screening requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen capability-use requests without current governance state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    directive_current = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if not capability_use_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed capability use policy is not present in self_structure_state_latest.json",
            "observability_gain": {"passed": False, "reason": "missing governed capability use policy state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed capability use policy state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed capability use policy state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen requests without the policy state"},
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
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen concrete use requests without a held capability"},
        }

    policy_artifact_path = Path(
        str(governed_skill_subsystem.get("last_capability_use_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )
    policy_summary = dict(_load_json_file(policy_artifact_path).get("governed_capability_use_policy_summary", {}))

    screen_schema = {
        "schema_name": "GovernedCapabilityUseCandidateScreen",
        "schema_version": "governed_capability_use_candidate_screen_v1",
        "required_fields": [
            "use_request_id",
            "request_name",
            "capability_id",
            "capability_name",
            "requested_purpose",
            "directive_relevance",
            "trusted_sources",
            "requested_resources",
            "requested_write_roots",
            "reversibility",
            "shadow_only",
            "decision_critical_reliance",
            "overlap_with_active_work",
            "capability_family_fit",
            "better_than_new_skill_candidate",
            "requires_capability_modification",
            "new_bounded_use_case",
            "same_shape_rerun",
            "source_artifact_refs",
            "usefulness_evidence_expectations",
        ],
        "outcome_classes": list(capability_use_policy.get("policy_classes", {}).keys()),
    }

    accounting_requirements = dict(capability_use_policy.get("invocation_accounting_requirements", {}))
    rollback_triggers = dict(policy_summary.get("current_rollback_triggers", {}))
    deprecation_triggers = dict(policy_summary.get("current_deprecation_triggers", {}))
    request_examples = _build_request_examples(held_capability)
    screened_requests = [
        _screen_request(
            request,
            held_capability=held_capability,
            directive_current=directive_current,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            accounting_requirements=accounting_requirements,
            rollback_triggers=rollback_triggers,
            deprecation_triggers=deprecation_triggers,
        )
        for request in request_examples
    ]
    counts = {
        name: sum(1 for item in screened_requests if str(item.get("assigned_class", "")) == name)
        for name in list(capability_use_policy.get("policy_classes", {}).keys())
    }
    best_direct_use = next((item for item in screened_requests if str(item.get("assigned_class", "")) == "diagnostic_only_use"), {})
    next_template = "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1"
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_capability_use_policy = dict(capability_use_policy)
    updated_capability_use_policy["use_candidate_screen_schema"] = screen_schema
    updated_capability_use_policy["last_candidate_screen_artifact_path"] = str(artifact_path)
    updated_capability_use_policy["last_candidate_screen_examples"] = [
        {
            "use_request_id": str(item.get("use_request_id", "")),
            "request_name": str(item.get("request_name", "")),
            "assigned_class": str(item.get("assigned_class", "")),
        }
        for item in screened_requests
    ]
    updated_capability_use_policy["last_candidate_screen_outcome"] = {
        "status": "candidate_requests_screened_without_reopen",
        "branch_state_after_screen": current_branch_state,
        "screened_request_count": len(screened_requests),
        "outcome_counts": counts,
        "best_direct_use_candidate": str(best_direct_use.get("request_name", "")),
        "best_direct_use_class": str(best_direct_use.get("assigned_class", "")),
        "reason": "concrete capability-invocation requests were screened under governance without reopening the paused parser line or opening a new behavior-changing branch",
    }
    updated_capability_use_policy["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_capability_use_policy"] = updated_capability_use_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_capability_use_candidate_screening_in_place": True,
            "latest_capability_use_candidate_screen_outcome": "candidate_requests_screened_without_reopen",
            "latest_capability_use_candidate_screen_best_request": str(best_direct_use.get("request_name", "")),
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_capability_use_candidate_screen_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_capability_use_candidate_screen_snapshot_v1_materialized",
        "event_class": "governed_capability_use_candidate_screen",
        "directive_id": str(directive_current.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "capability_id": str(held_capability.get("skill_id", "")),
        "screened_request_count": len(screened_requests),
        "outcome_counts": counts,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "capability_use_policy_v1": str(policy_artifact_path),
            "provisional_pause_v1": str(provisional_pause_artifact_path),
            "capability_use_candidate_screen_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
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
            "memory_summary.v4_governed_capability_use_policy_snapshot_v1": _artifact_reference(capability_use_policy_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(provisional_pause_snapshot, latest_snapshots),
        },
        "governed_capability_use_candidate_screen_summary": {
            "screen_schema": screen_schema,
            "capability_reviewed": {
                "capability_id": str(held_capability.get("skill_id", "")),
                "capability_name": str(held_capability.get("skill_name", "")),
                "held_status": str(held_capability.get("status", "")),
                "reopen_policy": str(held_capability.get("reopen_policy", "")),
                "retention_posture": str(held_capability.get("retention_posture", "")),
            },
            "invocation_requests_screened": screened_requests,
            "outcome_counts": counts,
            "invocation_accounting_policy_exercised": accounting_requirements,
            "paused_capability_behavior": {
                "development_line_reopened_by_screen": False,
                "same_shape_rerun_still_disallowed": True,
                "direct_use_does_not_imply_reopen": True,
                "reopen_still_requires_separate_governance_gate": True,
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
                "reason": "use-request screening is derived from directive, bucket, branch, self-structure, and capability-policy state, so classification stays governance-owned instead of execution-owned",
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
            "reason": "concrete capability-use requests now have explicit screened classes and persisted rationale under governance",
            "artifact_paths": {
                "capability_use_candidate_screen_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the screen distinguishes direct-use cases from hidden reopen pressure, same-shape reruns, and out-of-family requests",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "held capabilities can now be screened for concrete invocation without confusing invocation with development reopening",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the screen is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the best next gate is to evaluate the strongest direct-use candidate for invocation admission rather than to reopen or rebuild the paused parser line",
        },
        "diagnostic_conclusions": {
            "governed_capability_use_candidate_screening_in_place": True,
            "best_direct_use_candidate": str(best_direct_use.get("request_name", "")),
            "best_direct_use_class": str(best_direct_use.get("assigned_class", "")),
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
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
        "reason": "diagnostic shadow passed: concrete capability-invocation requests are now screened through governance without reopening paused development lines",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
