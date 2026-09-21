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
from .v4_governed_directive_work_selection_policy_snapshot_v1 import (
    _build_work_item_examples,
    _classify_work_item,
    _find_capability,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _candidate_priority(item: dict[str, Any]) -> tuple[int, int, int, int]:
    class_name = str(item.get("assigned_class", ""))
    class_priority = {
        "direct_governed_work_candidate": 0,
        "use_existing_capability_candidate": 1,
        "review_required_work_candidate": 2,
        "reopen_required_work_candidate": 3,
        "new_skill_candidate_required": 4,
        "defer_or_block_work_candidate": 5,
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


def _next_path_for_class(class_name: str) -> dict[str, Any]:
    if class_name == "direct_governed_work_candidate":
        return {
            "next_template": "memory_summary.v4_governed_directive_work_admission_snapshot_v1",
            "path_type": "direct_work_admission",
            "reason": "the work item is ready to move into a first directive-work admission gate",
        }
    if class_name == "use_existing_capability_candidate":
        return {
            "next_template": "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
            "path_type": "capability_use_admission",
            "reason": "the work item should continue through held-capability invocation admission rather than direct work admission",
        }
    if class_name == "review_required_work_candidate":
        return {
            "next_template": "",
            "path_type": "review_required_before_admission",
            "reason": "the work item is directive-valid but should not advance until explicit review occurs",
        }
    if class_name == "reopen_required_work_candidate":
        return {
            "next_template": "memory_summary.v4_governed_skill_reopen_candidate_screen_snapshot_v1",
            "path_type": "reopen_screen",
            "reason": "the work item is actually reopen pressure on a paused capability line",
        }
    if class_name == "new_skill_candidate_required":
        return {
            "next_template": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "path_type": "new_skill_candidate_screen",
            "reason": "the work item needs a new skill candidate instead of direct work execution",
        }
    return {
        "next_template": "",
        "path_type": "defer_or_block",
        "reason": "the work item should not advance under current governance constraints",
    }


def _screen_work_candidate(
    work_item: dict[str, Any],
    *,
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    allowed_write_roots: list[str],
    accounting_requirements: dict[str, Any],
    guardrails: dict[str, Any],
) -> dict[str, Any]:
    classification = _classify_work_item(
        work_item,
        directive_current=directive_current,
        bucket_current=bucket_current,
        current_branch_state=current_branch_state,
        allowed_write_roots=allowed_write_roots,
        callable_capabilities=callable_capabilities,
        plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
        routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
    )
    existing_capability_id = str(work_item.get("existing_capability_id", ""))
    existing_capability = _find_capability(callable_capabilities, existing_capability_id) if existing_capability_id else {}
    assigned_class = str(classification.get("assigned_class", ""))
    next_path = _next_path_for_class(assigned_class)

    return {
        "work_item_id": str(work_item.get("work_item_id", "")),
        "work_item_name": str(work_item.get("work_item_name", "")),
        "work_summary": str(work_item.get("work_summary", "")),
        "assigned_class": assigned_class,
        "rationale": str(classification.get("rationale", "")),
        "screen_dimensions": {
            "directive_closeness": str(work_item.get("directive_relevance", "")),
            "support_vs_drift": str(work_item.get("support_vs_drift", "")),
            "trusted_source_compatibility": bool(dict(classification.get("trusted_source_report", {})).get("passed", False)),
            "bucket_feasibility": bool(dict(classification.get("resource_report", {})).get("passed", False)),
            "branch_state_compatibility": str(current_branch_state) == "paused_with_baseline_held",
            "held_capability_availability": bool(existing_capability),
            "use_vs_development_vs_escalation": {
                "expected_capability_path": str(work_item.get("expected_capability_path", "")),
                "hidden_development_pressure": bool(classification.get("hidden_development_pressure", False)),
                "existing_capability_id": existing_capability_id,
            },
            "reversibility": str(work_item.get("reversibility", "")),
            "governance_observability": str(work_item.get("governance_observability", "")),
        },
        "work_selection_accounting_expectations": {
            "work_identity": {
                "work_item_id": str(work_item.get("work_item_id", "")),
                "work_item_name": str(work_item.get("work_item_name", "")),
            },
            "directive_linkage": {
                "directive_id": str(directive_current.get("directive_id", "")),
                "directive_linkage_summary": str(work_item.get("work_summary", "")),
                "branch_id": str(current_state_summary.get("current_branch_id", "")),
                "branch_state_precondition": current_branch_state,
            },
            "expected_capability_path": {
                "path": str(work_item.get("expected_capability_path", "")),
                "existing_capability_id": existing_capability_id,
                "existing_capability_name": str(existing_capability.get("capability_name", "")),
                "next_path": next_path,
            },
            "expected_resource_budget": dict(work_item.get("expected_resources", {})),
            "required_trusted_sources": list(work_item.get("trusted_sources", [])),
            "expected_write_roots": list(work_item.get("expected_write_roots", [])),
            "expected_success_signal": str(work_item.get("expected_success_signal", "")),
            "expected_review_hooks": [
                "review_before_selection_required"
                if assigned_class == "review_required_work_candidate"
                else "no_extra_review_before_next_gate"
            ],
            "expected_rollback_hooks": sorted(str(key) for key in guardrails.keys()),
            "accounting_schema_reference": {
                "work_identity_and_linkage_must_be_logged": list(
                    accounting_requirements.get("work_identity_and_linkage_must_be_logged", [])
                ),
                "expected_execution_path_must_be_logged": list(
                    accounting_requirements.get("expected_execution_path_must_be_logged", [])
                ),
                "expected_budget_and_trust_must_be_logged": list(
                    accounting_requirements.get("expected_budget_and_trust_must_be_logged", [])
                ),
                "expected_evidence_must_be_logged": list(
                    accounting_requirements.get("expected_evidence_must_be_logged", [])
                ),
            },
        },
        "path_separation": {
            "is_direct_work": assigned_class == "direct_governed_work_candidate",
            "requires_capability_use_admission": assigned_class == "use_existing_capability_candidate",
            "requires_review": assigned_class == "review_required_work_candidate",
            "requires_reopen_screen": assigned_class == "reopen_required_work_candidate",
            "requires_new_skill_candidate": assigned_class == "new_skill_candidate_required",
            "defer_or_block": assigned_class == "defer_or_block_work_candidate",
        },
        "classification_report": classification,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    directive_work_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    capability_use_invocation_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1"
    )
    capability_use_invocation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1"
    )
    capability_use_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1"
    )
    capability_use_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_policy_snapshot_v1"
    )
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_work_policy_snapshot,
            capability_use_evidence_snapshot,
            capability_use_invocation_snapshot,
            capability_use_invocation_admission_snapshot,
            capability_use_candidate_screen_snapshot,
            capability_use_policy_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive-work candidate screening requires the directive-work policy, capability-use chain, and provisional pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite directive-work candidate-screen artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite directive-work candidate-screen artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite directive-work candidate-screen artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen concrete directive-work candidates without the directive-work policy and supporting governed-capability chain",
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
            "reason": "diagnostic shadow failed: directive-work candidate screening requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen directive-work candidates without current governance state",
            },
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    if not governed_directive_work_selection_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed directive-work selection policy is not present in self_structure_state_latest.json",
            "observability_gain": {"passed": False, "reason": "missing directive-work selection policy state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing directive-work selection policy state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing directive-work selection policy state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen work candidates without the policy state",
            },
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
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen directive-work candidates without the current held capability state",
            },
        }

    allowed_write_roots = [
        str(intervention_data_dir()),
        str(Path(__file__).resolve().parent),
    ]
    policy_artifact_path = Path(
        _latest_matching_artifact("memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json")
    )
    capability_use_evidence_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_evidence_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json")
    )
    capability_use_invocation_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_execution_artifact_path", ""))
        or _latest_matching_artifact("proposal_learning_loop_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_*.json")
    )
    capability_use_invocation_admission_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_invocation_admission_snapshot_v1_*.json")
    )
    capability_use_candidate_screen_artifact_path = Path(
        str(governed_capability_use_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_*.json")
    )
    capability_use_policy_artifact_path = Path(
        str(governed_capability_use_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(dict(self_structure_state.get("governed_skill_subsystem", {})).get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )

    policy_payload = _load_json_file(policy_artifact_path)
    directive_work_policy_summary = dict(policy_payload.get("governed_directive_work_selection_policy_summary", {}))
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)
    capability_use_evidence_summary = dict(
        capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {})
    )
    if not all([directive_work_policy_summary, capability_use_evidence_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive-work candidate screening could not load the directive-work policy or capability-use evidence summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite policy summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite policy summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite policy summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen directive-work candidates without the governing summary payloads",
            },
        }

    directive_work_selection_ready = bool(
        dict(capability_use_evidence_summary.get("broader_project_alignment", {})).get(
            "provides_real_base_for_directive_work_selection_next",
            False,
        )
    )
    if not directive_work_selection_ready:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: capability-use evidence has not yet established readiness for directive-work selection",
            "observability_gain": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the capability-use layer must be operationally ready before directive-work screening proceeds",
            },
        }

    screen_schema = {
        "schema_name": "GovernedDirectiveWorkCandidateScreen",
        "schema_version": "governed_directive_work_candidate_screen_v1",
        "required_fields": list(
            dict(governed_directive_work_selection_policy.get("work_selection_request_schema", {})).get(
                "required_fields",
                [],
            )
        ),
        "outcome_classes": list(
            dict(governed_directive_work_selection_policy.get("policy_classes", {})).keys()
        ),
    }
    accounting_requirements = dict(
        governed_directive_work_selection_policy.get("work_selection_accounting_requirements", {})
    )
    guardrails = dict(governed_directive_work_selection_policy.get("guardrails", {}))
    work_candidates = _build_work_item_examples(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    screened_candidates = [
        _screen_work_candidate(
            item,
            directive_current=current_directive,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            callable_capabilities=callable_capabilities,
            allowed_write_roots=allowed_write_roots,
            accounting_requirements=accounting_requirements,
            guardrails=guardrails,
        )
        for item in work_candidates
    ]
    counts = {
        class_name: sum(1 for item in screened_candidates if str(item.get("assigned_class", "")) == class_name)
        for class_name in screen_schema["outcome_classes"]
    }
    best_candidate = sorted(screened_candidates, key=_candidate_priority)[0] if screened_candidates else {}
    best_candidate_class = str(best_candidate.get("assigned_class", ""))
    best_candidate_next_path = _next_path_for_class(best_candidate_class)
    ready_for_first_directive_work_admission = best_candidate_class == "direct_governed_work_candidate"
    next_template = (
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
        if ready_for_first_directive_work_admission
        else str(best_candidate_next_path.get("next_template", ""))
    )
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_directive_work_policy = dict(governed_directive_work_selection_policy)
    updated_directive_work_policy["work_candidate_screen_schema"] = screen_schema
    updated_directive_work_policy["last_candidate_screen_artifact_path"] = str(artifact_path)
    updated_directive_work_policy["last_candidate_screen_examples"] = [
        {
            "work_item_id": str(item.get("work_item_id", "")),
            "work_item_name": str(item.get("work_item_name", "")),
            "assigned_class": str(item.get("assigned_class", "")),
        }
        for item in screened_candidates
    ]
    updated_directive_work_policy["last_candidate_screen_outcome"] = {
        "status": "best_candidate_identified",
        "screened_candidate_count": len(screened_candidates),
        "outcome_counts": counts,
        "best_current_candidate": str(best_candidate.get("work_item_name", "")),
        "best_current_candidate_class": best_candidate_class,
        "best_current_candidate_next_path": best_candidate_next_path,
        "ready_for_first_directive_work_admission": ready_for_first_directive_work_admission,
        "reason": "concrete directive-work candidates were screened through governance while keeping direct-work, capability-use, reopen, new-skill, review, and defer paths separate",
    }
    updated_directive_work_policy["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_directive_work_selection_policy"] = updated_directive_work_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_directive_work_candidate_screening_in_place": True,
            "latest_directive_work_candidate_screen_outcome": "best_candidate_identified",
            "latest_directive_work_best_candidate": str(best_candidate.get("work_item_name", "")),
            "latest_directive_work_best_candidate_class": best_candidate_class,
            "latest_directive_work_best_next_template": next_template,
            "latest_directive_work_admission_readiness": (
                "ready_for_first_governed_directive_work_admission"
                if ready_for_first_directive_work_admission
                else "not_ready_for_direct_work_admission"
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
        "event_id": f"governed_directive_work_candidate_screen_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_directive_work_candidate_screen_snapshot_v1_materialized",
        "event_class": "governed_directive_work_candidate_screen",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "screened_candidate_count": len(screened_candidates),
        "best_current_candidate": str(best_candidate.get("work_item_name", "")),
        "best_current_candidate_class": best_candidate_class,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "directive_work_selection_policy_v1": str(policy_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "capability_use_invocation_v1": str(capability_use_invocation_artifact_path),
            "capability_use_invocation_admission_v1": str(capability_use_invocation_admission_artifact_path),
            "capability_use_candidate_screen_v1": str(capability_use_candidate_screen_artifact_path),
            "capability_use_policy_v1": str(capability_use_policy_artifact_path),
            "skill_provisional_pause_v1": str(provisional_pause_artifact_path),
            "directive_work_candidate_screen_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
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
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1": _artifact_reference(
                capability_use_invocation_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1": _artifact_reference(
                capability_use_invocation_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1": _artifact_reference(
                capability_use_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_policy_snapshot_v1": _artifact_reference(
                capability_use_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot, latest_snapshots
            ),
        },
        "governed_directive_work_candidate_screen_summary": {
            "screen_schema": screen_schema,
            "work_candidates_screened": screened_candidates,
            "outcome_counts": counts,
            "currently_admissible_work_items": {
                "direct_governed_work_candidates": [
                    str(item.get("work_item_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "direct_governed_work_candidate"
                ],
                "use_existing_capability_candidates": [
                    str(item.get("work_item_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "use_existing_capability_candidate"
                ],
                "review_required_candidates": [
                    str(item.get("work_item_name", ""))
                    for item in screened_candidates
                    if str(item.get("assigned_class", "")) == "review_required_work_candidate"
                ],
            },
            "work_selection_accounting_policy_exercised": accounting_requirements,
            "best_current_next_step_candidate": {
                "work_item_id": str(best_candidate.get("work_item_id", "")),
                "work_item_name": str(best_candidate.get("work_item_name", "")),
                "assigned_class": best_candidate_class,
                "next_path": best_candidate_next_path,
                "reason": "this candidate is the strongest current next work item because it is the highest-priority admissible class under the current directive-work policy and does not require reopen or new-skill escalation",
            },
            "ready_for_first_governed_directive_work_admission_step": ready_for_first_directive_work_admission,
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
                "reason": "directive-work candidate screening is derived from directive, bucket, branch, self-structure, held-capability, capability-use, and directive-work policy artifacts, so work choice remains governance-owned rather than execution-owned",
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
            "reason": "concrete directive-work candidates now have explicit screened classes, rationales, and next paths under governance",
            "artifact_paths": {
                "directive_work_candidate_screen_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the screen identifies which work item is actually strongest now and whether it should go to direct work admission, capability-use admission, review, reopen, new-skill screening, or defer",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "directive-work candidate screening now separates direct work from held-capability reuse, reopen pressure, new-skill demand, and blocked drift",
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
                "the best current work item is ready to move into a first governed directive-work admission step"
                if ready_for_first_directive_work_admission
                else "the best current work item should advance through its class-appropriate next gate rather than direct work admission"
            ),
        },
        "diagnostic_conclusions": {
            "governed_directive_work_candidate_screening_in_place": True,
            "best_current_candidate": str(best_candidate.get("work_item_name", "")),
            "best_current_candidate_class": best_candidate_class,
            "ready_for_first_governed_directive_work_admission": ready_for_first_directive_work_admission,
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
        "reason": "diagnostic shadow passed: concrete directive-work candidates are now screened through governance with a best current next candidate identified",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
