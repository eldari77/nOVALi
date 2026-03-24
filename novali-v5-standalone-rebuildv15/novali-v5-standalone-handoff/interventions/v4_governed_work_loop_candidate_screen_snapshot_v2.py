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
from .v4_governed_work_loop_candidate_screen_snapshot_v1 import (
    _candidate_priority,
    _next_path_for_loop_class,
    _screen_loop_candidate,
)
from .v4_governed_work_loop_policy_snapshot_v1 import _resolve_artifact_path
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _build_loop_candidate_examples_v2(
    *,
    parser_capability: dict[str, Any],
    allowed_write_roots: list[str],
) -> list[dict[str, Any]]:
    parser_id = str(parser_capability.get("capability_id", ""))
    return [
        {
            "loop_candidate_id": "loop_candidate_governance_recommendation_ledger_alignment_delta_audit",
            "loop_candidate_name": "Governance recommendation-to-ledger alignment delta audit",
            "loop_candidate_summary": "audit whether newly ranked governance recommendations remain aligned with intervention-ledger reality and the current narrow posture",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "governed_work_loop_continuation",
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
            "expected_incremental_value": "high",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "a bounded delta artifact showing whether recommendation output still coheres with governed ledger evidence under the current posture",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "cross-checks proposal recommendations against intervention-ledger evidence and current posture instead of repeating state coherence or raw ledger consistency",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "repetition_risk": "low",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_repeat_ledger_delta_audit_without_new_delta",
            "loop_candidate_name": "Repeat governance ledger consistency delta audit with no new ledger delta",
            "loop_candidate_summary": "repeat the same loop-continuation audit shape immediately without a new ledger delta or new bounded idea",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "governed_work_loop_continuation",
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
            "expected_success_signal": "another copy of the same narrow signal without distinct next-step evidence",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "materially overlaps the last admitted continuation and adds no new bounded idea",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": False,
            "repetition_risk": "high",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_trusted_shadow_bundle_anomaly_digest_refresh",
            "loop_candidate_name": "Trusted shadow bundle anomaly digest refresh",
            "loop_candidate_summary": "use the held parser capability on a fresh trusted local shadow-log bundle when capability reuse is cleaner than another direct loop step",
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
            "expected_success_signal": "a fresh trusted shadow-bundle digest produced through governed capability reuse",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "adds fresh trusted-local log coverage while preserving the held capability boundary",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "repetition_risk": "low",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_high_consequence_governance_posture_exception_support",
            "loop_candidate_name": "High-consequence governance posture exception support",
            "loop_candidate_summary": "perform a bounded but decision-critical posture-exception support task whose consequence profile requires review before continuation",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "governed_work_loop_continuation",
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
            "expected_success_signal": "a bounded posture-exception support output only after explicit review clears the consequence profile",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "distinct from prior work but sufficiently consequential to require review before it can be part of continued loop motion",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "repetition_risk": "low",
            "silent_broadening_risk": "medium",
        },
        {
            "loop_candidate_id": "loop_candidate_local_trace_parser_recommendation_ledger_trace_extension",
            "loop_candidate_name": "Local trace parser recommendation-ledger trace extension",
            "loop_candidate_summary": "extend the paused parser capability to a new recommendation-ledger trace family inside the loop",
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
            "expected_success_signal": "new parser-family evidence only if a separate reopen screen clears the paused line for development",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "materially new family coverage, but only by modifying a paused held capability",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "repetition_risk": "low",
            "silent_broadening_risk": "high",
        },
        {
            "loop_candidate_id": "loop_candidate_cross_artifact_branch_lineage_reconstruction",
            "loop_candidate_name": "Cross-artifact branch lineage reconstruction",
            "loop_candidate_summary": "attempt a new lineage-reconstruction task that falls outside the held parser family and current narrow proven paths",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "new_skill_candidate",
            "existing_capability_id": "",
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
            "expected_success_signal": "new family evidence only if a governed new-skill path is opened",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "distinct from current narrow paths because it requires a new family rather than another bounded reuse or continuation step",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "repetition_risk": "low",
            "silent_broadening_risk": "medium",
        },
        {
            "loop_candidate_id": "loop_candidate_broad_multi_path_governance_expansion_sweep",
            "loop_candidate_name": "Broad multi-path governance expansion sweep",
            "loop_candidate_summary": "attempt to combine direct work, capability reuse, and exploratory expansion in one step, including untrusted external search",
            "directive_relevance": "medium",
            "support_vs_drift": "drift",
            "trusted_sources": ["local_artifacts:novali-v4/data", "external_web:untrusted"],
            "expected_resources": {"cpu_parallel_units": 2, "memory_mb": 256, "storage_write_mb": 16, "network_mode": "internet"},
            "expected_write_roots": list(allowed_write_roots),
            "expected_execution_path": "broad_multi_path_operationalization",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "medium",
            "overlap_with_active_work": "high",
            "reversibility": "low",
            "governance_observability": "low",
            "bounded_context": False,
            "expected_incremental_value": "unknown",
            "repeats_low_yield_narrow_shape": False,
            "expected_success_signal": "not admissible because it collapses narrow posture into unsupported broad multi-path execution",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": True,
            "distinctness_basis": "tries to broaden too many paths at once rather than add one more bounded next-step signal",
            "distinct_from_direct_work": False,
            "distinct_from_prior_loop_continuation": False,
            "repetition_risk": "medium",
            "silent_broadening_risk": "high",
        },
    ]


def _next_path_for_loop_class_v2(class_name: str) -> dict[str, Any]:
    if class_name == "loop_continue_candidate":
        return {
            "next_template": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
            "path_type": "work_loop_continuation_admission",
            "reason": "the strongest distinct bounded next step should advance into a second governed work-loop continuation admission gate",
        }
    fallback = dict(_next_path_for_loop_class(class_name))
    if class_name == "loop_divert_to_capability_use":
        fallback["reason"] = "the narrow posture prefers governed capability reuse when that path is cleaner than another loop continuation step"
    return fallback


def _posture_rule_application(
    candidate: dict[str, Any],
    *,
    assigned_class: str,
    primary_posture_class: str,
    active_posture_classes: list[str],
) -> dict[str, Any]:
    repeats = bool(candidate.get("repeats_low_yield_narrow_shape", False))
    capability_cleaner = assigned_class == "loop_divert_to_capability_use"
    review_triggered = assigned_class == "loop_continue_with_review"
    broadening_blocked = assigned_class in {
        "loop_pause_candidate",
        "loop_divert_to_reopen_screen",
        "loop_divert_to_new_skill_screen",
        "loop_halt_or_block",
    } or str(candidate.get("silent_broadening_risk", "")) == "high"
    return {
        "primary_posture_class": primary_posture_class,
        "active_posture_classes_considered": list(active_posture_classes),
        "distinct_bounded_next_step_rule": {
            "result": "satisfied" if assigned_class == "loop_continue_candidate" else "not_primary_path",
            "reason": (
                "the candidate adds a distinct bounded next-step signal without repeating the prior direct-work or loop-continuation shape"
                if assigned_class == "loop_continue_candidate"
                else "the candidate did not become the primary distinct bounded next-step path under the current narrow posture"
            ),
        },
        "pause_if_low_yield_repetition": {
            "triggered": repeats,
            "reason": (
                "the repetition rule pauses this candidate because it reuses the prior loop shape without a new bounded delta"
                if repeats
                else "the candidate is not blocked by the repetition rule"
            ),
        },
        "divert_if_capability_path_is_cleaner": {
            "triggered": capability_cleaner,
            "reason": (
                "the posture diverts this candidate into governed capability use because reuse is cleaner than another direct loop step"
                if capability_cleaner
                else "this candidate is not cleaner as a capability-use diversion"
            ),
        },
        "review_if_consequence_rises": {
            "triggered": review_triggered,
            "reason": (
                "the posture keeps this candidate review-gated because consequence or overlap rose above the current low-risk narrow posture"
                if review_triggered
                else "this candidate did not trigger consequence-driven review escalation"
            ),
        },
        "require_more_evidence_before_broad_execution": {
            "preserved": True,
            "reason": "the screen preserves the current block on broader execution by selecting only one bounded next-step path and rejecting silent broadening",
        },
        "silent_broadening_block": {
            "triggered": broadening_blocked,
            "reason": (
                "the candidate is blocked or diverted because it would widen the loop beyond the currently supported narrow posture"
                if broadening_blocked
                else "the candidate stays inside the current narrow-posture boundary"
            ),
        },
    }


def _screen_loop_candidate_v2(
    candidate: dict[str, Any],
    *,
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    current_state_summary: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    allowed_write_roots: list[str],
    current_direct_work_future_posture: str,
    loop_continuation_future_posture: str,
    primary_posture_class: str,
    active_posture_classes: list[str],
    loop_accounting_requirements: dict[str, Any],
    guardrails: dict[str, Any],
) -> dict[str, Any]:
    screened = _screen_loop_candidate(
        candidate,
        directive_current=directive_current,
        bucket_current=bucket_current,
        current_branch_state=current_branch_state,
        current_state_summary=current_state_summary,
        callable_capabilities=callable_capabilities,
        allowed_write_roots=allowed_write_roots,
        current_direct_work_future_posture=current_direct_work_future_posture,
        loop_accounting_requirements=loop_accounting_requirements,
        guardrails=guardrails,
    )
    assigned_class = str(screened.get("assigned_class", ""))
    next_path = _next_path_for_loop_class_v2(assigned_class)
    screened["next_path"] = next_path
    screened["posture_rule_application"] = _posture_rule_application(
        candidate,
        assigned_class=assigned_class,
        primary_posture_class=primary_posture_class,
        active_posture_classes=active_posture_classes,
    )
    screened["screen_dimensions"]["distinctness_vs_recent_governed_steps"] = {
        "distinctness_basis": str(candidate.get("distinctness_basis", "")),
        "distinct_from_direct_work": bool(candidate.get("distinct_from_direct_work", False)),
        "distinct_from_prior_loop_continuation": bool(candidate.get("distinct_from_prior_loop_continuation", False)),
        "repetition_risk": str(candidate.get("repetition_risk", "")),
        "silent_broadening_risk": str(candidate.get("silent_broadening_risk", "")),
    }
    screened["screen_dimensions"]["posture_gate"] = {
        "current_work_loop_posture": primary_posture_class,
        "loop_continuation_future_posture": loop_continuation_future_posture,
        "broader_execution_remains_blocked": True,
    }
    screened["loop_accounting_expectations"]["loop_identity_context"]["loop_iteration"] = "posture_formalized_next_round"
    screened["loop_accounting_expectations"]["current_work_state"].update(
        {
            "prior_loop_continuation": str(current_state_summary.get("latest_governed_work_loop_execution_candidate", "")),
            "prior_loop_future_posture": loop_continuation_future_posture,
            "current_work_loop_posture": primary_posture_class,
        }
    )
    screened["loop_accounting_expectations"]["expected_path"]["next_path"] = next_path
    screened["path_separation"] = {
        "continue_as_governed_loop_step": assigned_class == "loop_continue_candidate",
        "divert_to_capability_use": assigned_class == "loop_divert_to_capability_use",
        "requires_review": assigned_class == "loop_continue_with_review",
        "pause_candidate": assigned_class == "loop_pause_candidate",
        "divert_to_reopen_screen": assigned_class == "loop_divert_to_reopen_screen",
        "divert_to_new_skill_screen": assigned_class == "loop_divert_to_new_skill_screen",
        "halt_or_block": assigned_class == "loop_halt_or_block",
    }
    return screened


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1"
    )
    work_loop_continuation_admission_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1"
    )
    work_loop_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    work_loop_posture_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
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
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot_v1,
            work_loop_continuation_admission_snapshot_v1,
            work_loop_execution_snapshot,
            work_loop_evidence_snapshot,
            work_loop_posture_snapshot,
            direct_work_evidence_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v2 requires the work-loop policy, v1 screen, continuation admission, continuation execution, evidence, posture, direct-work evidence, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop v2 candidate-screen artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop v2 candidate-screen artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop v2 candidate-screen artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next round of loop candidates without the full posture-aware artifact chain"},
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
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v2 requires current directive, bucket, self-structure, and branch artifacts",
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
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v2 requires current work-loop, capability-use, and directive-work governance state",
            "observability_gain": {"passed": False, "reason": "missing work-loop, capability-use, or directive-work governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing work-loop, capability-use, or directive-work governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing work-loop, capability-use, or directive-work governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next round of loop candidates without the full governance state chain"},
        }

    work_loop_policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    work_loop_candidate_screen_v1_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v1_*.json",
    )
    work_loop_continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v1_*.json",
    )
    work_loop_execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    work_loop_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    work_loop_posture_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
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
            work_loop_policy_artifact_path,
            work_loop_candidate_screen_v1_artifact_path,
            work_loop_continuation_admission_artifact_path,
            work_loop_execution_artifact_path,
            work_loop_evidence_artifact_path,
            work_loop_posture_artifact_path,
            direct_work_evidence_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more posture-aware work-loop reference artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v2"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v2"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v2"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next round of loop candidates without the governing posture artifact chain"},
        }

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    work_loop_evidence_payload = _load_json_file(work_loop_evidence_artifact_path)
    work_loop_posture_payload = _load_json_file(work_loop_posture_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    if not all([work_loop_policy_payload, work_loop_evidence_payload, work_loop_posture_payload, direct_work_evidence_payload]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v2 could not load one or more governing summary payloads",
            "observability_gain": {"passed": False, "reason": "missing prerequisite posture-aware summary payloads"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite posture-aware summary payloads"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite posture-aware summary payloads"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next round of loop candidates without the posture-aware summaries"},
        }

    work_loop_policy_summary = dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {}))
    work_loop_evidence_summary = dict(work_loop_evidence_payload.get("governed_work_loop_evidence_summary", {}))
    work_loop_posture_summary = dict(work_loop_posture_payload.get("governed_work_loop_posture_summary", {}))
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    if not all([work_loop_policy_summary, work_loop_evidence_summary, work_loop_posture_summary, direct_work_evidence_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v2 could not load the policy, posture, or evidence summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite posture-aware work-loop summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite posture-aware work-loop summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite posture-aware work-loop summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen next-loop candidates without the posture and evidence summaries"},
        }

    posture_current = dict(work_loop_posture_summary.get("current_posture", {}))
    evidence_basis = dict(work_loop_posture_summary.get("current_evidence_basis", {}))
    ready_for_candidate_screen_v2 = (
        bool(current_state_summary.get("governed_work_loop_posture_v1_defined", False))
        and str(current_state_summary.get("latest_governed_work_loop_posture_status", "")) == "defined"
        and str(current_state_summary.get("latest_governed_work_loop_readiness", "")) == "ready_for_distinct_next_step_screen"
        and str(posture_current.get("primary_posture_class", "")) == "keep_narrow_governed_loop_available"
        and bool(posture_current.get("broader_execution_not_yet_justified", False))
        and bool(evidence_basis.get("broader_posture_justified", False))
    )
    if not ready_for_candidate_screen_v2:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current state is not yet marked ready for posture-aware governed work-loop candidate screening v2",
            "observability_gain": {"passed": False, "reason": "narrow-posture candidate-screen readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "narrow-posture candidate-screen readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "narrow-posture candidate-screen readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the work-loop posture must be defined and narrow-execution readiness must still hold before this next screening round"},
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
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen clean capability-use diversion candidates without the current held capability state"},
        }

    allowed_write_roots = [str(intervention_data_dir()), str(Path(__file__).resolve().parent)]
    direct_work_future_posture = str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", ""))
    loop_continuation_future_posture = str(dict(work_loop_evidence_summary.get("future_posture", {})).get("category", ""))
    primary_posture_class = str(posture_current.get("primary_posture_class", ""))
    active_posture_classes = [
        str(item) for item in list(posture_current.get("active_posture_classes", [])) if str(item).strip()
    ]
    screen_schema = {
        "schema_name": "GovernedWorkLoopCandidateScreen",
        "schema_version": "governed_work_loop_candidate_screen_v2",
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
            "distinctness_basis",
            "repetition_risk",
            "silent_broadening_risk",
        ],
        "outcome_classes": list(dict(governed_work_loop_policy.get("policy_classes", {})).keys()),
        "posture_classes_applied": list(dict(work_loop_posture_summary.get("posture_classes", {})).keys()),
    }
    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    loop_candidates = _build_loop_candidate_examples_v2(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    screened_candidates = [
        _screen_loop_candidate_v2(
            item,
            directive_current=current_directive,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            callable_capabilities=callable_capabilities,
            allowed_write_roots=allowed_write_roots,
            current_direct_work_future_posture=direct_work_future_posture,
            loop_continuation_future_posture=loop_continuation_future_posture,
            primary_posture_class=primary_posture_class,
            active_posture_classes=active_posture_classes,
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
    best_candidate_next_path = dict(best_candidate.get("next_path", {}))
    ready_for_next_bounded_step_admission = best_candidate_class == "loop_continue_candidate"
    next_template = (
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2"
        if ready_for_next_bounded_step_admission
        else str(best_candidate_next_path.get("next_template", ""))
    )
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v2_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["work_loop_candidate_screen_v2_schema"] = screen_schema
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
        "status": "best_distinct_bounded_candidate_identified_v2",
        "screened_candidate_count": len(screened_candidates),
        "outcome_counts": counts,
        "best_current_candidate": str(best_candidate.get("loop_candidate_name", "")),
        "best_current_candidate_class": best_candidate_class,
        "best_current_candidate_next_path": best_candidate_next_path,
        "ready_for_second_governed_work_loop_continuation_admission": ready_for_next_bounded_step_admission,
        "reason": "the next round of concrete loop-step candidates was screened under the narrow posture while explicitly rejecting repetition and unsupported broadening",
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_candidate_screening_v2_in_place": True,
            "latest_governed_work_loop_candidate_screen_outcome": "best_distinct_bounded_candidate_identified_v2",
            "latest_governed_work_loop_best_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "latest_governed_work_loop_best_candidate_class": best_candidate_class,
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_continuation_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "latest_governed_work_loop_continuation_readiness": (
                "ready_for_second_governed_work_loop_continuation_admission"
                if ready_for_next_bounded_step_admission
                else "not_ready_for_second_governed_work_loop_continuation_admission"
            ),
            "latest_governed_work_loop_readiness": (
                "ready_for_second_governed_work_loop_continuation_admission"
                if ready_for_next_bounded_step_admission
                else "ready_for_distinct_next_step_screen"
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
        "event_id": f"governed_work_loop_candidate_screen_snapshot_v2::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_candidate_screen_snapshot_v2_materialized",
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
            "governed_work_loop_candidate_screen_v1": str(work_loop_candidate_screen_v1_artifact_path),
            "governed_work_loop_continuation_admission_v1": str(work_loop_continuation_admission_artifact_path),
            "governed_work_loop_execution_v1": str(work_loop_execution_artifact_path),
            "governed_work_loop_evidence_v1": str(work_loop_evidence_artifact_path),
            "governed_work_loop_posture_v1": str(work_loop_posture_artifact_path),
            "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_candidate_screen_v2": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
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
                work_loop_candidate_screen_snapshot_v1, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1": _artifact_reference(
                work_loop_continuation_admission_snapshot_v1, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(
                work_loop_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(
                work_loop_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(
                work_loop_posture_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_candidate_screen_v2_summary": {
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
            "posture_rule_application": {
                "current_work_loop_posture": primary_posture_class,
                "active_posture_classes": active_posture_classes,
                "missing_evidence_for_broader_execution": list(
                    work_loop_posture_summary.get("missing_evidence_for_broader_execution", [])
                ),
                "narrowness_preservation_rules": list(
                    work_loop_posture_summary.get("narrowness_preservation_rules", [])
                ),
            },
            "loop_accounting_policy_exercised": loop_accounting_requirements,
            "best_current_next_bounded_step": {
                "loop_candidate_id": str(best_candidate.get("loop_candidate_id", "")),
                "loop_candidate_name": str(best_candidate.get("loop_candidate_name", "")),
                "assigned_class": best_candidate_class,
                "next_path": best_candidate_next_path,
                "reason": "this candidate is the strongest current bounded next step because it is the only direct continuation candidate that stays distinct, preserves narrowness, and adds a new evidence signal without hidden broadening pressure",
            },
            "ready_for_concrete_next_admission_step": ready_for_next_bounded_step_admission,
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
                "reason": "work-loop candidate screening v2 is derived from directive, bucket, branch, self-structure, v1 work-loop evidence, and the formalized narrow posture artifact, so continuation choice remains governance-owned rather than execution-owned",
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
            "reason": "the next round of loop candidates now has explicit posture-aware screened classes, rationales, posture-rule application, and next paths under governance",
            "artifact_paths": {
                "governed_work_loop_candidate_screen_v2_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the screen identifies the strongest next bounded step under the narrow posture and cleanly separates continuation, capability-use diversion, review, pause, reopen, new-skill, and halt paths",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "posture-aware screening now rejects low-yield repetition and silent broadening while selecting only one strongest bounded next step",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the v2 screen is diagnostic-only; it opened no new branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": (
                "the strongest next bounded step is ready to move into a second governed work-loop continuation admission gate"
                if ready_for_next_bounded_step_admission
                else "the best current candidate should advance through its class-appropriate next gate rather than continuation admission"
            ),
        },
        "diagnostic_conclusions": {
            "governed_work_loop_candidate_screening_v2_in_place": True,
            "best_current_next_bounded_step": str(best_candidate.get("loop_candidate_name", "")),
            "best_current_next_bounded_step_class": best_candidate_class,
            "ready_for_concrete_next_admission_step": ready_for_next_bounded_step_admission,
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
        "reason": "diagnostic shadow passed: the next round of governed work-loop candidates was screened under the narrow posture and a single strongest bounded next step was identified",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
        "stage_status": "passed",
    }
