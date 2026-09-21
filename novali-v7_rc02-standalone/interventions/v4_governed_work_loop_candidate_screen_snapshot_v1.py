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
from .v4_governed_directive_work_selection_policy_snapshot_v1 import _find_capability
from .v4_governed_work_loop_policy_snapshot_v1 import (
    _build_loop_candidate_examples,
    _classify_loop_candidate,
    _resolve_artifact_path,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _candidate_priority(item: dict[str, Any]) -> tuple[int, int, int, int]:
    class_name = str(item.get("assigned_class", ""))
    class_priority = {
        "loop_continue_candidate": 0,
        "loop_divert_to_capability_use": 1,
        "loop_continue_with_review": 2,
        "loop_pause_candidate": 3,
        "loop_divert_to_reopen_screen": 4,
        "loop_divert_to_new_skill_screen": 5,
        "loop_halt_or_block": 6,
    }
    relevance_priority = {"high": 0, "medium": 1, "low": 2}
    decision_priority = {"low": 0, "medium": 1, "high": 2}
    overlap_priority = {"low": 0, "medium": 1, "high": 2}
    return (
        class_priority.get(class_name, 99),
        relevance_priority.get(str(item.get("directive_relevance", "")), 99),
        decision_priority.get(str(item.get("decision_criticality", "")), 99),
        overlap_priority.get(str(item.get("overlap_with_active_work", "")), 99),
    )


def _next_path_for_loop_class(class_name: str) -> dict[str, Any]:
    if class_name == "loop_continue_candidate":
        return {
            "next_template": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
            "path_type": "work_loop_continuation_admission",
            "reason": "the next loop step can advance into a first governed work-loop continuation admission gate",
        }
    if class_name == "loop_divert_to_capability_use":
        return {
            "next_template": "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
            "path_type": "capability_use_admission",
            "reason": "the cleanest next loop step is governed reuse of a held capability rather than another direct-work continuation",
        }
    if class_name == "loop_continue_with_review":
        return {
            "next_template": "",
            "path_type": "review_required_before_continuation",
            "reason": "the next loop step is directive-valid but should not advance until explicit review occurs",
        }
    if class_name == "loop_pause_candidate":
        return {
            "next_template": "",
            "path_type": "pause_loop",
            "reason": "the loop should pause rather than spend another iteration on low-yield narrow repetition",
        }
    if class_name == "loop_divert_to_reopen_screen":
        return {
            "next_template": "memory_summary.v4_governed_skill_reopen_candidate_screen_snapshot_v1",
            "path_type": "reopen_screen",
            "reason": "the next loop step is actually reopen pressure on a paused capability line",
        }
    if class_name == "loop_divert_to_new_skill_screen":
        return {
            "next_template": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "path_type": "new_skill_candidate_screen",
            "reason": "the next loop step needs a new skill candidate instead of loop continuation",
        }
    return {
        "next_template": "",
        "path_type": "halt_or_block",
        "reason": "the next loop step should not advance under current trust, bucket, or governance constraints",
    }


def _screen_loop_candidate(
    candidate: dict[str, Any],
    *,
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    allowed_write_roots: list[str],
    current_direct_work_future_posture: str,
    loop_accounting_requirements: dict[str, Any],
    guardrails: dict[str, Any],
) -> dict[str, Any]:
    classification = _classify_loop_candidate(
        candidate,
        directive_current=directive_current,
        bucket_current=bucket_current,
        current_branch_state=current_branch_state,
        allowed_write_roots=allowed_write_roots,
        callable_capabilities=callable_capabilities,
        current_direct_work_future_posture=current_direct_work_future_posture,
        plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
        routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
    )
    existing_capability_id = str(candidate.get("existing_capability_id", ""))
    existing_capability = _find_capability(callable_capabilities, existing_capability_id) if existing_capability_id else {}
    assigned_class = str(classification.get("assigned_class", ""))
    next_path = _next_path_for_loop_class(assigned_class)

    return {
        "loop_candidate_id": str(candidate.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate.get("loop_candidate_name", "")),
        "loop_candidate_summary": str(candidate.get("loop_candidate_summary", "")),
        "assigned_class": assigned_class,
        "rationale": str(classification.get("rationale", "")),
        "directive_relevance": str(candidate.get("directive_relevance", "")),
        "decision_criticality": str(candidate.get("decision_criticality", "")),
        "overlap_with_active_work": str(candidate.get("overlap_with_active_work", "")),
        "screen_dimensions": {
            "directive_linkage_and_distinct_value": {
                "directive_relevance": str(candidate.get("directive_relevance", "")),
                "support_vs_drift": str(candidate.get("support_vs_drift", "")),
                "expected_incremental_value": str(candidate.get("expected_incremental_value", "")),
                "repeats_low_yield_narrow_shape": bool(candidate.get("repeats_low_yield_narrow_shape", False)),
            },
            "prior_work_reviewed_successfully": bool(current_state_summary.get("latest_direct_work_operational_success", False)),
            "adds_new_value_vs_repeats_low_yield": not bool(candidate.get("repeats_low_yield_narrow_shape", False)),
            "trusted_source_compatibility": bool(dict(classification.get("trusted_source_report", {})).get("passed", False)),
            "bucket_resource_feasibility": bool(dict(classification.get("resource_report", {})).get("passed", False)),
            "branch_state_compatibility": str(current_branch_state) == "paused_with_baseline_held",
            "held_capability_availability": bool(existing_capability),
            "path_distinction": {
                "expected_execution_path": str(candidate.get("expected_execution_path", "")),
                "requires_capability_use_admission": bool(candidate.get("requires_capability_use_admission", False)),
                "requires_capability_modification": bool(candidate.get("requires_capability_modification", False)),
                "new_skill_family_required": bool(candidate.get("new_skill_family_required", False)),
            },
            "reversibility": str(candidate.get("reversibility", "")),
            "governance_observability": str(candidate.get("governance_observability", "")),
        },
        "loop_accounting_expectations": {
            "loop_identity_context": {
                "loop_id": str(current_state_summary.get("current_branch_id", "")),
                "directive_id": str(directive_current.get("directive_id", "")),
                "branch_id": str(current_state_summary.get("current_branch_id", "")),
                "branch_state": current_branch_state,
                "loop_iteration": "post_first_successful_direct_work",
            },
            "current_work_state": {
                "prior_work_item": str(current_state_summary.get("latest_directive_work_execution_candidate", "")),
                "prior_work_future_posture": current_direct_work_future_posture,
                "prior_work_reviewed_successfully": bool(current_state_summary.get("latest_direct_work_operational_success", False)),
                "capability_status_context": str(current_state_summary.get("latest_held_capability_use_status", "")),
            },
            "candidate_identity": {
                "loop_candidate_id": str(candidate.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate.get("loop_candidate_name", "")),
                "existing_capability_id": existing_capability_id,
                "existing_capability_name": str(existing_capability.get("capability_name", "")),
            },
            "expected_path": {
                "path": str(candidate.get("expected_execution_path", "")),
                "assigned_class": assigned_class,
                "next_path": next_path,
            },
            "resource_trust_position": {
                "expected_resource_budget": dict(candidate.get("expected_resources", {})),
                "required_trusted_sources": list(candidate.get("trusted_sources", [])),
                "expected_write_roots": list(candidate.get("expected_write_roots", [])),
                "network_mode_expectation": str(dict(candidate.get("expected_resources", {})).get("network_mode", "")),
            },
            "continuation_rationale": str(classification.get("rationale", "")),
            "expected_next_evidence_signal": str(candidate.get("expected_success_signal", "")),
            "review_rollback_hooks": {
                "review_hooks": [
                    "explicit_review_before_loop_continuation"
                    if assigned_class == "loop_continue_with_review"
                    else "no_extra_review_before_next_gate"
                ],
                "rollback_hooks": sorted(str(key) for key in guardrails.keys()),
                "accounting_schema_reference": {
                    "loop_identity_and_context_must_be_logged": list(
                        loop_accounting_requirements.get("loop_identity_and_context_must_be_logged", [])
                    ),
                    "current_work_state_must_be_logged": list(
                        loop_accounting_requirements.get("current_work_state_must_be_logged", [])
                    ),
                    "resource_and_trust_position_must_be_logged": list(
                        loop_accounting_requirements.get("resource_and_trust_position_must_be_logged", [])
                    ),
                    "continuation_decision_must_be_logged": list(
                        loop_accounting_requirements.get("continuation_decision_must_be_logged", [])
                    ),
                },
            },
        },
        "path_separation": {
            "continue_as_direct_work": assigned_class == "loop_continue_candidate",
            "divert_to_capability_use": assigned_class == "loop_divert_to_capability_use",
            "requires_review": assigned_class == "loop_continue_with_review",
            "pause_candidate": assigned_class == "loop_pause_candidate",
            "divert_to_reopen_screen": assigned_class == "loop_divert_to_reopen_screen",
            "divert_to_new_skill_screen": assigned_class == "loop_divert_to_new_skill_screen",
            "halt_or_block": assigned_class == "loop_halt_or_block",
        },
        "classification_report": classification,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
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
    direct_work_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"
    )
    direct_work_selection_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            direct_work_admission_snapshot,
            direct_work_candidate_screen_snapshot,
            direct_work_selection_policy_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening requires the work-loop policy, the direct-work governance chain, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop candidate-screen artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop candidate-screen artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop candidate-screen artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen next loop-step candidates without the full governing artifact chain"},
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
            "reason": "diagnostic shadow failed: governed work-loop candidate screening requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen loop candidates without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    if not governed_work_loop_policy or not governed_capability_use_policy or not governed_directive_work_selection_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening requires current work-loop, capability-use, and directive-work governance state",
            "observability_gain": {"passed": False, "reason": "missing governed work-loop, capability-use, or directive-work state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed work-loop, capability-use, or directive-work state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed work-loop, capability-use, or directive-work state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen loop candidates without the current governance state chain"},
        }

    work_loop_policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    direct_work_execution_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json",
    )
    direct_work_admission_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_admission_artifact_path"),
        "memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json",
    )
    direct_work_candidate_screen_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_*.json",
    )
    direct_work_selection_policy_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            work_loop_policy_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_admission_artifact_path,
            direct_work_candidate_screen_artifact_path,
            direct_work_selection_policy_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more governed work-loop reference artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen next loop-step candidates without the governing artifact chain"},
        }

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    work_loop_policy_summary = dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {}))
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    if not all([work_loop_policy_summary, direct_work_evidence_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening could not load the work-loop policy or direct-work evidence summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite work-loop summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite work-loop summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite work-loop summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen loop candidates without the governing summary payloads"},
        }

    ready_for_candidate_screen = bool(
        dict(work_loop_policy_summary.get("broader_architecture_role", {})).get(
            "current_state_sufficient_to_define_work_loop_policy_now",
            False,
        )
    ) and str(current_state_summary.get("latest_governed_work_loop_readiness", "")) == "ready_for_candidate_screen"
    if not ready_for_candidate_screen:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current state is not yet marked ready for governed work-loop candidate screening",
            "observability_gain": {"passed": False, "reason": "governed work-loop candidate-screen readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "governed work-loop candidate-screen readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "governed work-loop candidate-screen readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the work-loop policy must be active and ready before concrete loop candidates are screened"},
        }

    callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    if not parser_capability:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no current held callable capability record was found for the local trace parser",
            "observability_gain": {"passed": False, "reason": "missing held callable capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held callable capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held callable capability record"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen loop diversion candidates without the current held capability state"},
        }

    allowed_write_roots = [str(intervention_data_dir()), str(Path(__file__).resolve().parent)]
    direct_work_future_posture = str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", ""))
    screen_schema = {
        "schema_name": "GovernedWorkLoopCandidateScreen",
        "schema_version": "governed_work_loop_candidate_screen_v1",
        "required_fields": [
            "loop_candidate_id",
            "loop_candidate_name",
            "loop_candidate_summary",
            "directive_relevance",
            "support_vs_drift",
            "trusted_sources",
            "expected_resources",
            "expected_write_roots",
            "expected_execution_path",
            "decision_criticality",
            "overlap_with_active_work",
            "reversibility",
            "governance_observability",
            "expected_incremental_value",
            "expected_success_signal",
        ],
        "outcome_classes": list(dict(governed_work_loop_policy.get("policy_classes", {})).keys()),
    }
    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    loop_candidates = _build_loop_candidate_examples(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    screened_candidates = [
        _screen_loop_candidate(
            item,
            directive_current=current_directive,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            callable_capabilities=callable_capabilities,
            allowed_write_roots=allowed_write_roots,
            current_direct_work_future_posture=direct_work_future_posture,
            loop_accounting_requirements=loop_accounting_requirements,
            guardrails=guardrails,
        )
        for item in loop_candidates
    ]
    counts = {
        class_name: sum(1 for item in screened_candidates if str(item.get("assigned_class", "")) == class_name)
        for class_name in screen_schema["outcome_classes"]
    }
    best_candidate = sorted(screened_candidates, key=_candidate_priority)[0] if screened_candidates else {}
    best_candidate_class = str(best_candidate.get("assigned_class", ""))
    best_candidate_next_path = _next_path_for_loop_class(best_candidate_class)
    ready_for_first_continuation_admission = best_candidate_class == "loop_continue_candidate"
    next_template = (
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1"
        if ready_for_first_continuation_admission
        else str(best_candidate_next_path.get("next_template", ""))
    )
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["work_loop_candidate_screen_schema"] = screen_schema
    updated_work_loop_policy["last_candidate_screen_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_candidate_screen_examples"] = [
        {
            "loop_candidate_id": str(item.get("loop_candidate_id", "")),
            "loop_candidate_name": str(item.get("loop_candidate_name", "")),
            "assigned_class": str(item.get("assigned_class", "")),
        }
        for item in screened_candidates
    ]
    updated_work_loop_policy["last_candidate_screen_outcome"] = {
        "status": "best_candidate_identified",
        "screened_candidate_count": len(screened_candidates),
        "outcome_counts": counts,
        "best_current_candidate": str(best_candidate.get("loop_candidate_name", "")),
        "best_current_candidate_class": best_candidate_class,
        "best_current_candidate_next_path": best_candidate_next_path,
        "ready_for_first_governed_work_loop_continuation_admission": ready_for_first_continuation_admission,
        "reason": "concrete next-loop-step candidates were screened through governance while keeping direct work, capability use, review, pause, reopen, new-skill, and halt paths separate",
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_candidate_screening_in_place": True,
            "latest_governed_work_loop_candidate_screen_outcome": "best_candidate_identified",
            "latest_governed_work_loop_best_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "latest_governed_work_loop_best_candidate_class": best_candidate_class,
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_continuation_readiness": (
                "ready_for_first_governed_work_loop_continuation_admission"
                if ready_for_first_continuation_admission
                else "not_ready_for_first_governed_work_loop_continuation_admission"
            ),
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_work_loop_candidate_screen_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_candidate_screen_snapshot_v1_materialized",
        "event_class": "governed_work_loop_candidate_screen",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "screened_candidate_count": len(screened_candidates),
        "best_current_candidate": str(best_candidate.get("loop_candidate_name", "")),
        "best_current_candidate_class": best_candidate_class,
        "new_behavior_changing_branch_opened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
            "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "direct_work_admission_v1": str(direct_work_admission_artifact_path),
            "direct_work_candidate_screen_v1": str(direct_work_candidate_screen_artifact_path),
            "directive_work_selection_policy_v1": str(direct_work_selection_policy_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_candidate_screen_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
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
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(
                direct_work_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1": _artifact_reference(
                direct_work_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1": _artifact_reference(
                direct_work_selection_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_candidate_screen_summary": {
            "screen_schema": screen_schema,
            "candidates_screened": screened_candidates,
            "outcome_counts": counts,
            "currently_admissible_next_loop_steps": {
                "loop_continue_candidates": [
                    str(item.get("loop_candidate_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "loop_continue_candidate"
                ],
                "loop_divert_to_capability_use": [
                    str(item.get("loop_candidate_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "loop_divert_to_capability_use"
                ],
                "loop_continue_with_review": [
                    str(item.get("loop_candidate_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "loop_continue_with_review"
                ],
            },
            "loop_accounting_policy_exercised": loop_accounting_requirements,
            "best_current_next_loop_step_candidate": {
                "loop_candidate_id": str(best_candidate.get("loop_candidate_id", "")),
                "loop_candidate_name": str(best_candidate.get("loop_candidate_name", "")),
                "assigned_class": best_candidate_class,
                "next_path": best_candidate_next_path,
                "reason": "this candidate is the strongest current next loop-step because it is the highest-priority admissible class under the work-loop policy and adds distinct value without hiding review or development pressure",
            },
            "ready_for_first_governed_work_loop_continuation_admission_step": ready_for_first_continuation_admission,
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
                "reason": "work-loop candidate screening is derived from directive, bucket, branch, self-structure, direct-work evidence, held-capability state, and work-loop policy artifacts, so continuation choice remains governance-owned rather than execution-owned",
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
            "reason": "concrete next-loop-step candidates now have explicit screened classes, rationales, loop-accounting expectations, and next paths under governance",
            "artifact_paths": {
                "governed_work_loop_candidate_screen_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the screen identifies which next loop-step is strongest now and whether it should continue as direct work, divert to capability use, require review, pause, reopen, new-skill screen, or halt",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "governed work-loop candidate screening now separates direct-work continuation from held-capability reuse, review escalation, pause, reopen pressure, new-skill demand, and blocked drift",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the screen is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": (
                "the best current loop candidate is ready to move into a first governed work-loop continuation admission step"
                if ready_for_first_continuation_admission
                else "the best current loop candidate should advance through its class-appropriate next gate rather than direct loop continuation admission"
            ),
        },
        "diagnostic_conclusions": {
            "governed_work_loop_candidate_screening_in_place": True,
            "best_current_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "best_current_candidate_class": best_candidate_class,
            "ready_for_first_governed_work_loop_continuation_admission": ready_for_first_continuation_admission,
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
        "reason": "diagnostic shadow passed: concrete next-loop-step candidates are now screened through governance with a best current continuation path identified",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
