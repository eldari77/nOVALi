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
    _find_capability,
    _resource_request_within_bucket,
    _trusted_sources_allowed,
    _write_roots_allowed,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _resolve_artifact_path(raw_candidate: Any, pattern: str) -> Path | None:
    candidate = str(raw_candidate or "").strip()
    if not candidate or candidate == "None":
        fallback = _latest_matching_artifact(pattern)
        candidate = str(fallback or "").strip()
    return Path(candidate) if candidate else None


def _all_flags_false(flags: dict[str, Any]) -> bool:
    return all(not bool(value) for value in dict(flags).values())


def _build_loop_candidate_examples(
    *,
    parser_capability: dict[str, Any],
    allowed_write_roots: list[str],
) -> list[dict[str, Any]]:
    parser_id = str(parser_capability.get("capability_id", ""))
    return [
        {
            "loop_candidate_id": "loop_candidate_governance_ledger_consistency_delta_audit",
            "loop_candidate_name": "Governance ledger consistency delta audit",
            "loop_candidate_summary": "run a distinct bounded governance-maintenance audit on governance ledger consistency rather than repeating the exact prior coherence audit shape",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "direct_governed_work",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "reversibility": "high",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "medium",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "a distinct bounded governance-maintenance artifact that adds new loop evidence without reopening capability development",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_repeat_coherence_audit_without_new_delta",
            "loop_candidate_name": "Repeat governance state coherence audit with no new delta",
            "loop_candidate_summary": "repeat the same direct-work audit shape immediately without a new state delta or new bounded idea",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "direct_governed_work",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "reversibility": "high",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "low",
            "repeats_low_yield_narrow_shape": True,
            "expected_success_signal": "another copy of the same narrow signal without meaningful new structural information",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_high_consequence_directive_review_support",
            "loop_candidate_name": "High-consequence directive review support",
            "loop_candidate_summary": "perform a bounded but decision-critical directive support task whose consequence profile requires review before loop continuation",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "direct_governed_work",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "high",
            "overlap_with_active_work": "medium",
            "reversibility": "high",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "medium",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "bounded directive-support output, but only after explicit review clears the consequence profile",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_trusted_diagnostic_bundle_summary_refresh",
            "loop_candidate_name": "Trusted diagnostic bundle summary refresh",
            "loop_candidate_summary": "continue the loop by reusing the held parser capability on a new trusted local diagnostic bundle rather than opening new direct work",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "use_existing_capability",
            "existing_capability_id": parser_id,
            "capability_family_fit": True,
            "requires_capability_use_admission": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "reversibility": "high",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "medium",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "a new trusted diagnostic bundle summary produced through held capability reuse under governance",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_local_trace_parser_new_trace_family_extension",
            "loop_candidate_name": "Local trace parser new trace-family extension",
            "loop_candidate_summary": "continue the loop by extending the paused parser capability to a new trace family",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "reopen_capability_line",
            "existing_capability_id": parser_id,
            "capability_family_fit": True,
            "requires_capability_use_admission": False,
            "requires_capability_modification": True,
            "new_bounded_use_case": True,
            "new_skill_family_required": False,
            "decision_criticality": "medium",
            "overlap_with_active_work": "low",
            "reversibility": "medium",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "unknown",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "new parser-family evidence only if a separate reopen screen clears development pressure",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_out_of_family_retrieval_need",
            "loop_candidate_name": "Out-of-family retrieval need",
            "loop_candidate_summary": "continue the loop with a need that falls outside the currently held parser capability family",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "new_skill_candidate",
            "existing_capability_id": parser_id,
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": True,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "reversibility": "medium",
            "governance_observability": "high",
            "bounded_context": True,
            "expected_incremental_value": "unknown",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "new family evidence only if a separate governed skill candidate path is opened",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "loop_candidate_id": "loop_candidate_untrusted_external_directive_exploration",
            "loop_candidate_name": "Untrusted external directive exploration",
            "loop_candidate_summary": "continue the loop via untrusted external exploration outside the current directive and bucket policy",
            "directive_relevance": "medium",
            "support_vs_drift": "drift",
            "trusted_sources": ["external_web:untrusted"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "internet"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "blocked",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "medium",
            "overlap_with_active_work": "medium",
            "reversibility": "low",
            "governance_observability": "low",
            "bounded_context": False,
            "expected_incremental_value": "unknown",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "not admissible under current trust and boundedness constraints",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": True,
        },
    ]


def _classify_loop_candidate(
    candidate: dict[str, Any],
    *,
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    allowed_write_roots: list[str],
    callable_capabilities: list[dict[str, Any]],
    current_direct_work_future_posture: str,
    plan_non_owning: bool,
    routing_deferred: bool,
) -> dict[str, Any]:
    trusted_source_report = _trusted_sources_allowed(
        list(candidate.get("trusted_sources", [])),
        directive_current,
        bucket_current,
    )
    resource_report = _resource_request_within_bucket(
        dict(candidate.get("expected_resources", {})),
        bucket_current,
    )
    write_root_report = _write_roots_allowed(
        list(candidate.get("expected_write_roots", [])),
        allowed_write_roots,
    )

    directive_relevance = str(candidate.get("directive_relevance", "none"))
    support_vs_drift = str(candidate.get("support_vs_drift", "drift"))
    decision_criticality = str(candidate.get("decision_criticality", "low"))
    overlap_with_active_work = str(candidate.get("overlap_with_active_work", "low"))
    reversibility = str(candidate.get("reversibility", "low"))
    governance_observability = str(candidate.get("governance_observability", "low"))
    existing_capability_id = str(candidate.get("existing_capability_id", ""))
    capability_family_fit = bool(candidate.get("capability_family_fit", False))
    requires_capability_use_admission = bool(candidate.get("requires_capability_use_admission", False))
    requires_capability_modification = bool(candidate.get("requires_capability_modification", False))
    new_bounded_use_case = bool(candidate.get("new_bounded_use_case", False))
    new_skill_family_required = bool(candidate.get("new_skill_family_required", False))
    bounded_context = bool(candidate.get("bounded_context", True))
    repeats_low_yield_narrow_shape = bool(candidate.get("repeats_low_yield_narrow_shape", False))
    expected_incremental_value = str(candidate.get("expected_incremental_value", "unknown"))
    expected_execution_path = str(candidate.get("expected_execution_path", ""))
    matching_capability = _find_capability(callable_capabilities, existing_capability_id) if existing_capability_id else {}

    blocked_reasons: list[str] = []
    if not trusted_source_report.get("passed", False):
        blocked_reasons.append("trusted-source policy violated")
    if not resource_report.get("passed", False):
        blocked_reasons.append("requested resources exceed current bucket limits")
    if not write_root_report.get("passed", False):
        blocked_reasons.append("requested write roots exceed currently admitted roots")
    if current_branch_state != "paused_with_baseline_held":
        blocked_reasons.append("branch state is not paused_with_baseline_held")
    if directive_relevance not in {"high", "medium"}:
        blocked_reasons.append("directive relevance is too weak")
    if support_vs_drift != "support":
        blocked_reasons.append("the candidate looks more like drift than directive support")
    if reversibility not in {"high", "medium"}:
        blocked_reasons.append("the candidate is not sufficiently reversible")
    if governance_observability not in {"high", "medium"}:
        blocked_reasons.append("governance observability is too weak")
    if not bounded_context:
        blocked_reasons.append("context exploration is not bounded enough")
    if not plan_non_owning:
        blocked_reasons.append("plan_ non-owning guard no longer holds")
    if not routing_deferred:
        blocked_reasons.append("routing is no longer deferred")
    if bool(candidate.get("touches_protected_surface", False)):
        blocked_reasons.append("protected-surface work requested")
    if bool(candidate.get("touches_downstream_selected_set", False)):
        blocked_reasons.append("downstream selected-set work requested")
    if bool(candidate.get("touches_plan_ownership", False)):
        blocked_reasons.append("plan_ ownership change requested")
    if bool(candidate.get("touches_routing", False)):
        blocked_reasons.append("routing work requested")
    if bool(candidate.get("touches_branch_state", False)):
        blocked_reasons.append("branch-state mutation requested")
    if bool(candidate.get("unbounded_contextual_exploration", False)):
        blocked_reasons.append("unbounded contextual exploration requested")

    if blocked_reasons:
        outcome = "loop_halt_or_block"
        reason = "; ".join(blocked_reasons)
    elif repeats_low_yield_narrow_shape or (
        expected_execution_path == "direct_governed_work"
        and current_direct_work_future_posture == "keep_available_but_narrow"
        and expected_incremental_value == "low"
    ):
        outcome = "loop_pause_candidate"
        reason = "the next step would mostly repeat low-yield narrow work, so the loop should pause rather than churn"
    elif requires_capability_modification or new_bounded_use_case:
        outcome = "loop_divert_to_reopen_screen"
        reason = "the candidate implies hidden capability development pressure inside a held capability family, so loop continuation must divert to a reopen screen"
    elif new_skill_family_required or (existing_capability_id and not capability_family_fit) or (
        existing_capability_id and not matching_capability and expected_execution_path != "direct_governed_work"
    ):
        outcome = "loop_divert_to_new_skill_screen"
        reason = "the candidate falls outside the currently held capability family and should divert to governed skill screening"
    elif decision_criticality in {"medium", "high"} or overlap_with_active_work in {"medium", "high"}:
        outcome = "loop_continue_with_review"
        reason = "the candidate is directive-valid but important enough to require review before loop continuation"
    elif existing_capability_id and capability_family_fit and requires_capability_use_admission:
        outcome = "loop_divert_to_capability_use"
        reason = "the cleanest next loop step is governed reuse of a held capability rather than another direct-work admission"
    else:
        outcome = "loop_continue_candidate"
        reason = "the candidate is directive-valid, distinct enough to add loop value, and eligible to continue the bounded governed work loop"

    return {
        "loop_candidate_id": str(candidate.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate.get("loop_candidate_name", "")),
        "assigned_class": outcome,
        "rationale": reason,
        "expected_execution_path": expected_execution_path,
        "directive_relevance": directive_relevance,
        "support_vs_drift": support_vs_drift,
        "decision_criticality": decision_criticality,
        "overlap_with_active_work": overlap_with_active_work,
        "expected_incremental_value": expected_incremental_value,
        "repeats_low_yield_narrow_shape": repeats_low_yield_narrow_shape,
        "trusted_source_report": trusted_source_report,
        "resource_report": resource_report,
        "write_root_report": write_root_report,
        "matching_capability_found": bool(matching_capability),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    direct_work_selection_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    direct_work_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"
    )
    direct_work_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
    )
    direct_work_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            direct_work_selection_policy_snapshot,
            direct_work_candidate_screen_snapshot,
            direct_work_admission_snapshot,
            direct_work_execution_snapshot,
            direct_work_evidence_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop policy requires the governance substrate, directive-work policy chain, direct-work evidence review, and capability-use evidence review artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop policy artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop policy artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop policy artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define a governed work loop without the already-reviewed direct-work path"},
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
            "reason": "diagnostic shadow failed: governed work-loop policy requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define a governed work loop without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if not governed_directive_work_selection_policy or not governed_capability_use_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop policy requires current directive-work and capability-use governance state",
            "observability_gain": {"passed": False, "reason": "missing governed directive-work or capability-use state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed directive-work or capability-use state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed directive-work or capability-use state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define a governed work loop without directive-work and capability-use state"},
        }

    directive_work_policy_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json",
    )
    directive_work_candidate_screen_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_*.json",
    )
    directive_work_admission_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_admission_artifact_path"),
        "memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json",
    )
    direct_work_execution_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            directive_work_policy_artifact_path,
            directive_work_candidate_screen_artifact_path,
            directive_work_admission_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_evidence_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more governed work-loop reference artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for governed work-loop policy"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for governed work-loop policy"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for governed work-loop policy"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define a governed work loop without the governing artifact chain"},
        }

    directive_work_policy_payload = _load_json_file(directive_work_policy_artifact_path)
    directive_work_candidate_screen_payload = _load_json_file(directive_work_candidate_screen_artifact_path)
    directive_work_admission_payload = _load_json_file(directive_work_admission_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)

    directive_work_policy_summary = dict(
        directive_work_policy_payload.get("governed_directive_work_selection_policy_summary", {})
    )
    directive_work_candidate_screen_summary = dict(
        directive_work_candidate_screen_payload.get("governed_directive_work_candidate_screen_summary", {})
    )
    directive_work_admission_summary = dict(
        directive_work_admission_payload.get("governed_directive_work_admission_summary", {})
    )
    direct_work_execution_summary = dict(
        direct_work_execution_payload.get("governed_direct_work_execution_summary", {})
    )
    direct_work_evidence_summary = dict(
        direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {})
    )
    capability_use_evidence_summary = dict(
        capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {})
    )
    if not all(
        [
            directive_work_policy_summary,
            directive_work_candidate_screen_summary,
            directive_work_admission_summary,
            direct_work_execution_summary,
            direct_work_evidence_summary,
            capability_use_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more governed work-loop reference summaries could not be loaded",
            "observability_gain": {"passed": False, "reason": "missing governed work-loop reference summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed work-loop reference summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed work-loop reference summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define a governed work loop without the loaded governing summaries"},
        }

    direct_work_future_posture = str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", ""))
    direct_work_evidence_triggers = dict(direct_work_evidence_summary.get("trigger_status", {}))
    current_callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))
    parser_capability = _find_capability(current_callable_capabilities, "skill_candidate_local_trace_parser_trial")
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
            "later_selection_usefulness": {"passed": False, "reason": "cannot define governed work-loop diversion logic without the current held capability record"},
        }

    ready_for_policy_layer = bool(
        dict(direct_work_evidence_summary.get("broader_project_alignment", {})).get(
            "ready_for_governed_work_loop_policy_layer",
            False,
        )
    )
    if not ready_for_policy_layer:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: direct-work evidence has not yet marked the system ready for a governed work-loop policy layer",
            "observability_gain": {"passed": False, "reason": "governed work-loop policy readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "governed work-loop policy readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "governed work-loop policy readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the reviewed direct-work path must prove broader work-loop-policy readiness before this layer is defined"},
        }

    allowed_write_roots = [
        str(intervention_data_dir()),
        str(Path(__file__).resolve().parent),
    ]
    next_template = "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1"

    policy_classes = {
        "loop_continue_candidate": {
            "meaning": "the next step can continue the bounded governed work loop because it adds distinct directive-supportive value inside the current envelope",
            "phase_1_status": "enabled_for_narrow_bounded_progression",
        },
        "loop_continue_with_review": {
            "meaning": "the loop may continue only after explicit review because the next candidate has higher consequence or overlap",
            "phase_1_status": "enabled",
        },
        "loop_pause_candidate": {
            "meaning": "the loop should pause instead of continuing because the next step would mostly repeat low-yield narrow work or because value is flattening",
            "phase_1_status": "enabled",
        },
        "loop_divert_to_capability_use": {
            "meaning": "the next step should divert into the held-capability use path rather than direct-work continuation",
            "phase_1_status": "enabled",
        },
        "loop_divert_to_reopen_screen": {
            "meaning": "the next step implies capability development pressure and must divert into a separate reopen screen",
            "phase_1_status": "enabled",
        },
        "loop_divert_to_new_skill_screen": {
            "meaning": "the next step falls outside held capability families and must divert into governed skill screening",
            "phase_1_status": "enabled",
        },
        "loop_halt_or_block": {
            "meaning": "the loop must halt or block because trust, bucket, branch, or governance guardrails do not hold",
            "phase_1_status": "enabled",
        },
    }

    work_loop_stages = {
        "candidate_identification": "form bounded directive-relevant next-step candidates without granting execution authority",
        "candidate_screening": "classify concrete next-step candidates through governance before any continuation decision",
        "work_admission": "admit direct work or divert into capability-use, reopen, new-skill, or review paths as appropriate",
        "bounded_execution": "run only the admitted bounded action in shadow with explicit envelope tracking",
        "evidence_review": "evaluate operational value, governance sufficiency, and loop-worthiness after each execution",
        "continuation_pause_defer_review_decision": "decide whether to continue narrowly, pause, defer, or require review before another step",
        "diversion_to_reopen_or_new_skill_when_needed": "divert capability-development or out-of-family pressure into separate governance-owned paths",
    }

    loop_entry_conditions = {
        "directive_validity": {
            "required": "directive initialization must remain active and aligned with self-structure state",
            "current_passed": str(directive_state.get("initialization_state", "")) == "active"
            and str(current_state_summary.get("active_directive_id", "")) == str(current_directive.get("directive_id", "")),
        },
        "governance_integrity": {
            "required": "governance substrate, directive-work selection, direct-work admission, direct-work execution, and direct-work evidence review must all already be in place",
            "current_passed": bool(current_state_summary.get("governance_substrate_in_place", False))
            and bool(current_state_summary.get("governed_directive_work_selection_policy_v1_defined", False))
            and bool(current_state_summary.get("governed_directive_work_admission_in_place", False))
            and bool(current_state_summary.get("governed_direct_work_execution_in_place", False))
            and bool(current_state_summary.get("governed_direct_work_evidence_review_in_place", False)),
        },
        "bucket_feasibility": {
            "required": "bucket state must remain readable and the last reviewed direct-work path must still have low-risk envelope compliance",
            "current_passed": bool(current_bucket)
            and bool(dict(direct_work_evidence_summary.get("envelope_compliance_assessment", {})).get("passed", False)),
        },
        "branch_state_compatibility": {
            "required": "branch must remain paused_with_baseline_held with plan_ non-owning and routing deferred",
            "current_passed": current_branch_state == "paused_with_baseline_held"
            and bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False)),
        },
        "available_governed_execution_path": {
            "required": "at least one bounded governed execution path must remain available",
            "current_passed": direct_work_future_posture in {
                "keep_available_for_direct_governed_work",
                "keep_available_but_narrow",
                "keep_available_with_review_only",
            }
            or str(dict(capability_use_evidence_summary.get("future_posture", {})).get("category", "")) in {
                "keep_available_for_governed_use",
                "keep_available_but_diagnostic_only",
                "keep_available_with_review_only",
            },
        },
    }

    continuation_conditions = {
        "prior_work_evidence_review_completed": {
            "required": "the prior admitted work item must already have a governance-owned evidence review",
            "current_passed": bool(current_state_summary.get("governed_direct_work_evidence_review_in_place", False)),
        },
        "prior_work_operationally_successful": {
            "required": "the prior work item must have succeeded in an operationally meaningful way",
            "current_passed": bool(current_state_summary.get("latest_direct_work_operational_success", False)),
        },
        "prior_work_future_posture_allows_continuation": {
            "required": "the prior work path must remain available, even if only narrowly",
            "current_passed": direct_work_future_posture in {
                "keep_available_for_direct_governed_work",
                "keep_available_but_narrow",
                "keep_available_with_review_only",
            },
        },
        "no_active_review_rollback_or_deprecation_triggers": {
            "required": "review, rollback, and deprecation triggers from the prior work item must remain inactive",
            "current_passed": _all_flags_false(dict(direct_work_evidence_triggers.get("review_trigger_status", {})))
            and _all_flags_false(dict(direct_work_evidence_triggers.get("rollback_trigger_status", {})))
            and _all_flags_false(dict(direct_work_evidence_triggers.get("deprecation_trigger_status", {}))),
        },
        "next_step_must_add_distinct_value": {
            "required": "a continuation candidate must add distinct directive-supportive value rather than looping on the same narrow low-yield shape",
            "current_passed": direct_work_future_posture == "keep_available_but_narrow",
            "current_interpretation": "repeat-the-same coherence audit without a new delta should pause rather than auto-continue",
        },
    }

    loop_exit_or_halt_conditions = {
        "directive_invalidation": {"halts_loop": True, "currently_active": str(directive_state.get("initialization_state", "")) != "active"},
        "budget_or_resource_breach": {"halts_loop": True, "currently_active": not bool(dict(direct_work_evidence_summary.get("envelope_compliance_assessment", {})).get("passed", False))},
        "trust_failure": {"halts_loop": True, "currently_active": str(dict(direct_work_evidence_summary.get("envelope_compliance_assessment", {})).get("network_mode", "")) != "none"},
        "branch_state_conflict": {"halts_loop": True, "currently_active": current_branch_state != "paused_with_baseline_held"},
        "repeated_low_value_churn": {"halts_loop": False, "pauses_loop": True, "currently_active": False},
        "hidden_capability_development_pressure": {"halts_loop": False, "diverts_loop": True, "currently_active": False},
        "review_trigger_activated": {"halts_loop": False, "review_required": True, "currently_active": not _all_flags_false(dict(direct_work_evidence_triggers.get("review_trigger_status", {})))},
        "rollback_trigger_activated": {"halts_loop": True, "currently_active": not _all_flags_false(dict(direct_work_evidence_triggers.get("rollback_trigger_status", {})))},
        "deprecation_trigger_activated": {"halts_loop": True, "currently_active": not _all_flags_false(dict(direct_work_evidence_triggers.get("deprecation_trigger_status", {})))},
    }

    sequencing_logic = {
        "priority_order": [
            "prefer a distinct bounded direct-governed-work continuation when it adds new directive-supportive value",
            "otherwise prefer held-capability reuse when a callable capability cleanly fits the next need",
            "route decision-critical or overlap-heavy candidates into review before continuation",
            "divert capability-development pressure into reopen screening instead of hiding it inside loop continuation",
            "divert out-of-family needs into new-skill screening instead of forcing a mismatch",
            "pause rather than churn when the next candidate mostly repeats low-yield narrow work",
            "halt or block when trust, bucket, branch, or governance guardrails fail",
        ],
        "avoid_low_yield_repetition_rule": "the current direct-work path is keep_available_but_narrow, so repeating the same coherence-audit shape with no new delta should not auto-continue the loop",
        "reason": "the loop should move forward only through bounded distinct value, not through automatic repetition of the last successful narrow work item",
    }

    loop_accounting_requirements = {
        "loop_identity_and_context_must_be_logged": [
            "loop_id",
            "directive_id",
            "branch_id",
            "branch_state",
            "loop_iteration",
            "prior_work_item_id",
        ],
        "current_work_state_must_be_logged": [
            "current_work_item",
            "prior_work_evidence_summary",
            "current_execution_path",
            "current_direct_work_future_posture",
            "capability_status_context",
        ],
        "resource_and_trust_position_must_be_logged": [
            "resource_budget_position",
            "trusted_sources_in_use",
            "expected_next_resource_budget",
            "expected_write_roots",
            "network_mode_expectation",
        ],
        "continuation_decision_must_be_logged": [
            "continue_pause_defer_or_divert_reason",
            "review_hooks",
            "rollback_hooks",
            "deprecation_hooks",
            "expected_next_evidence_signal",
            "diversion_target_path",
        ],
    }

    work_loop_guardrails = {
        "protected_surface_drift_forbidden": True,
        "downstream_selected_set_work_forbidden": True,
        "plan_ownership_change_forbidden": True,
        "routing_drift_forbidden": True,
        "hidden_capability_development_inside_loop_forbidden": True,
        "silent_promotion_from_narrow_to_broad_operational_path_forbidden": True,
        "unbounded_contextual_exploration_forbidden": True,
        "branch_state_mutation_forbidden": True,
        "untrusted_external_access_forbidden": True,
    }

    relationship_to_held_capabilities = {
        "reuse_held_capability_when": [
            "a held capability cleanly matches the next bounded need",
            "the use stays inside the held capability envelope",
            "capability reuse is cleaner than reopening or creating a new skill",
        ],
        "keep_paused_capability_line_paused_when": [
            "same-shape rerun pressure appears",
            "the work can be served by held capability use without development",
            "no reopen screen has been cleared for a new bounded use-case",
        ],
        "divert_to_reopen_screen_when": [
            "the next step implies capability modification",
            "the next step depends on a materially new bounded use-case within a paused capability family",
        ],
        "divert_to_new_skill_screen_when": [
            "the next step falls outside all held capability families",
            "using an existing held capability would be a workaround for a different capability need",
        ],
        "current_held_capabilities": current_callable_capabilities,
    }

    relationship_to_direct_work = {
        "direct_work_remains_narrow_when": [
            "only one successful narrow direct-work case has been reviewed so far",
            "the next candidate mostly repeats the prior work shape without new signal",
            "the current direct-work future posture remains keep_available_but_narrow",
        ],
        "direct_work_is_sufficient_to_continue_loop_when": [
            "the next direct-work candidate is distinct enough to add new directive-supportive value",
            "the next candidate remains bounded, reversible, and governance-observable",
            "review, rollback, and deprecation triggers remain inactive",
        ],
        "more_evidence_required_before_broadening": [
            "at least one more distinct admitted direct-work or governed capability-use-backed loop step",
            "continued full envelope compliance across another loop continuation",
            "continued separation between direct work, capability use, reopen, and new-skill paths",
        ],
        "current_direct_work_status": {
            "work_item_name": str(dict(governed_directive_work_selection_policy.get("last_direct_work_execution_outcome", {})).get("work_item_name", "")),
            "future_posture": direct_work_future_posture,
            "operationally_successful": bool(current_state_summary.get("latest_direct_work_operational_success", False)),
        },
    }

    sample_loop_candidates = _build_loop_candidate_examples(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    sample_loop_decisions = [
        _classify_loop_candidate(
            item,
            directive_current=current_directive,
            bucket_current=current_bucket,
            current_branch_state=current_branch_state,
            allowed_write_roots=allowed_write_roots,
            callable_capabilities=current_callable_capabilities,
            current_direct_work_future_posture=direct_work_future_posture,
            plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
            routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
        )
        for item in sample_loop_candidates
    ]
    sample_decision_counts = {
        decision_class: sum(1 for item in sample_loop_decisions if str(item.get("assigned_class", "")) == decision_class)
        for decision_class in policy_classes
    }

    broader_architecture_role = {
        "supports_self_directed_behavior_without_losing_governance": True,
        "prevents_chaos_by_making_continue_pause_divert_and_halt_explicit": True,
        "prevents_stagnation_by_allowing_distinct_bounded_next_steps": True,
        "current_state_sufficient_to_define_work_loop_policy_now": all(
            bool(dict(item).get("current_passed", False))
            for item in loop_entry_conditions.values()
        ) and ready_for_policy_layer,
        "preconditions_before_broader_governed_work_loop_execution": [
            "this policy layer must be defined",
            "concrete next-loop candidates must be screened through this policy",
            "the chosen next step must pass its own direct-work, capability-use, review, reopen, or new-skill gate",
            "another distinct bounded loop step must succeed with full envelope compliance before broader execution is considered",
            "no branch-state mutation, routing drift, or silent path broadening may occur",
        ],
        "reason": "the governed work loop provides a governance-owned way to continue, pause, divert, or halt across work items without collapsing back into one-off execution or uncontrolled autonomy",
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_policy_snapshot_v1_{proposal['proposal_id']}.json"

    governed_work_loop_policy = {
        "schema_version": "governed_work_loop_policy_v1",
        "work_loop_stages": work_loop_stages,
        "policy_classes": policy_classes,
        "loop_entry_conditions": loop_entry_conditions,
        "loop_continuation_conditions": continuation_conditions,
        "loop_exit_or_halt_conditions": loop_exit_or_halt_conditions,
        "sequencing_logic": sequencing_logic,
        "loop_accounting_requirements": loop_accounting_requirements,
        "guardrails": work_loop_guardrails,
        "relationship_to_held_capabilities": relationship_to_held_capabilities,
        "relationship_to_direct_work": relationship_to_direct_work,
        "current_loop_context": {
            "directive_id": str(current_directive.get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "latest_direct_work_item": str(dict(governed_directive_work_selection_policy.get("last_direct_work_execution_outcome", {})).get("work_item_name", "")),
            "latest_direct_work_future_posture": direct_work_future_posture,
            "latest_capability_use_future_posture": str(dict(capability_use_evidence_summary.get("future_posture", {})).get("category", "")),
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "sample_loop_decisions": sample_loop_decisions,
        "sample_decision_counts": sample_decision_counts,
        "best_next_template": next_template,
        "last_policy_artifact_path": str(artifact_path),
    }

    updated_self_structure_state = dict(self_structure_state)
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = governed_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_policy_v1_defined": True,
            "latest_governed_work_loop_policy_status": "defined",
            "latest_governed_work_loop_readiness": "ready_for_candidate_screen",
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_posture": "narrow_continuation_only_until_screened_next_candidate",
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_work_loop_policy_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_policy_snapshot_v1_materialized",
        "event_class": "governed_work_loop_policy",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "latest_direct_work_item": str(dict(governed_directive_work_selection_policy.get("last_direct_work_execution_outcome", {})).get("work_item_name", "")),
        "new_behavior_changing_branch_opened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "directive_work_selection_policy_v1": str(directive_work_policy_artifact_path),
            "directive_work_candidate_screen_v1": str(directive_work_candidate_screen_artifact_path),
            "directive_work_admission_v1": str(directive_work_admission_artifact_path),
            "direct_work_execution_v1": str(direct_work_execution_artifact_path),
            "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_policy_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_policy_snapshot_v1",
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
                direct_work_selection_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1": _artifact_reference(
                direct_work_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(
                direct_work_admission_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(
                direct_work_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_policy_summary": {
            "loop_stages": work_loop_stages,
            "entry_conditions": loop_entry_conditions,
            "continuation_conditions": continuation_conditions,
            "exit_or_halt_conditions": loop_exit_or_halt_conditions,
            "policy_classes": policy_classes,
            "sequencing_logic": sequencing_logic,
            "loop_accounting_requirements": loop_accounting_requirements,
            "guardrails": work_loop_guardrails,
            "relationship_to_held_capabilities": relationship_to_held_capabilities,
            "relationship_to_direct_work": relationship_to_direct_work,
            "readiness_reference": {
                "direct_work_future_posture": direct_work_future_posture,
                "direct_work_operational_success": bool(current_state_summary.get("latest_direct_work_operational_success", False)),
                "governed_work_loop_policy_ready": ready_for_policy_layer,
                "capability_use_future_posture": str(dict(capability_use_evidence_summary.get("future_posture", {})).get("category", "")),
            },
            "sample_loop_decisions": sample_loop_decisions,
            "sample_decision_counts": sample_decision_counts,
            "broader_architecture_role": broader_architecture_role,
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
                "reason": "work-loop control is now derived from directive, bucket, branch, self-structure, direct-work policy, direct-work evidence, and capability-use evidence artifacts rather than from one-off execution code",
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
            "reason": "the system now has a governance-owned work-loop policy layer that explicitly manages continuation, pause, diversion, and halt across work items",
            "artifact_paths": {
                "governed_work_loop_policy_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the policy clarifies how NOVALI should move from one admitted work item to the next without hiding capability development or uncontrolled execution expansion inside loop continuation",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "governed work-loop management is now separated from one-off direct work, capability use, reopen screening, and new skill creation",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the policy snapshot is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next useful layer is a concrete governed work-loop candidate screen that applies this policy to real next-step requests",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_policy_v1_defined": True,
            "current_state_sufficient_to_define_policy": bool(broader_architecture_role.get("current_state_sufficient_to_define_work_loop_policy_now", False)),
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
        "reason": "diagnostic shadow passed: governed work-loop control now has a governance-owned policy layer on top of reviewed direct-work and capability-use paths",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
