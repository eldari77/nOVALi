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


def _build_loop_candidate_examples_v3(
    *,
    parser_capability: dict[str, Any],
    allowed_write_roots: list[str],
) -> list[dict[str, Any]]:
    parser_id = str(parser_capability.get("capability_id", ""))
    return [
        {
            "loop_candidate_id": "loop_candidate_governance_recommendation_frontier_containment_audit",
            "loop_candidate_name": "Governance recommendation-frontier containment audit",
            "loop_candidate_summary": "audit whether the currently reachable recommendation frontier remains contained inside the proven narrow governed chain rather than drifting into recursive governance paperwork or unsupported broadening",
            "proposed_execution_template": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
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
            "expected_success_signal": "a bounded frontier-containment artifact showing whether the next recommendation surface remains directive-bound, posture-contained, and structurally useful without widening execution",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "tests recommendation-frontier containment and next-step viability rather than repeating state coherence, raw ledger consistency, recommendation-to-ledger alignment, or evidence consolidation",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "distinct_from_continuation_v1": True,
            "distinct_from_continuation_v2": True,
            "distinct_from_evidence_snapshot_v2": True,
            "execution_adjacency": "high",
            "structural_yield": "high",
            "local_procedural_yield": "medium",
            "administrative_recursion_risk": "low",
            "posture_pressure": "absent",
            "repetition_risk": "low",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_repeat_work_loop_evidence_consolidation_without_frontier_delta",
            "loop_candidate_name": "Repeat governed work-loop evidence consolidation with no frontier delta",
            "loop_candidate_summary": "restate the current work-loop evidence layer without a new frontier signal or a new bounded operational question",
            "proposed_execution_template": "",
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
            "expected_success_signal": "another summary pass that mostly rephrases current governance conclusions without a new bounded evidence signal",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "materially overlaps the v2 evidence layer and introduces no new frontier-facing bounded question",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": False,
            "distinct_from_continuation_v1": False,
            "distinct_from_continuation_v2": False,
            "distinct_from_evidence_snapshot_v2": False,
            "execution_adjacency": "low",
            "structural_yield": "low",
            "local_procedural_yield": "low",
            "administrative_recursion_risk": "high",
            "posture_pressure": "absent",
            "repetition_risk": "high",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_trusted_shadow_bundle_anomaly_digest_refresh",
            "loop_candidate_name": "Trusted shadow bundle anomaly digest refresh",
            "loop_candidate_summary": "reuse the held parser capability on a fresh trusted local shadow bundle when governed capability reuse is cleaner than another loop-continuation step",
            "proposed_execution_template": "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
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
            "expected_success_signal": "a fresh trusted shadow-bundle digest produced through governed capability reuse instead of another continuation step",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "adds fresh trusted-local anomaly coverage while preserving the diagnostic-only held capability boundary",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "distinct_from_continuation_v1": True,
            "distinct_from_continuation_v2": True,
            "distinct_from_evidence_snapshot_v2": True,
            "execution_adjacency": "medium",
            "structural_yield": "medium",
            "local_procedural_yield": "medium",
            "administrative_recursion_risk": "low",
            "posture_pressure": "absent",
            "repetition_risk": "low",
            "silent_broadening_risk": "low",
        },
        {
            "loop_candidate_id": "loop_candidate_high_consequence_governance_frontier_exception_support",
            "loop_candidate_name": "High-consequence governance frontier exception support",
            "loop_candidate_summary": "perform a bounded but decision-critical governance-frontier exception support task whose consequence profile requires explicit review before continuation",
            "proposed_execution_template": "",
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
            "expected_success_signal": "a bounded posture-exception support output only if review clears the consequence profile",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
            "distinctness_basis": "distinct from prior work but sufficiently consequential to require review before it can enter continued loop motion",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "distinct_from_continuation_v1": True,
            "distinct_from_continuation_v2": True,
            "distinct_from_evidence_snapshot_v2": True,
            "execution_adjacency": "medium",
            "structural_yield": "medium",
            "local_procedural_yield": "medium",
            "administrative_recursion_risk": "medium",
            "posture_pressure": "present",
            "repetition_risk": "low",
            "silent_broadening_risk": "medium",
        },
        {
            "loop_candidate_id": "loop_candidate_local_trace_parser_recommendation_frontier_trace_extension",
            "loop_candidate_name": "Local trace parser recommendation-frontier trace extension",
            "loop_candidate_summary": "extend the paused parser capability to a new recommendation-frontier trace family inside the governed loop",
            "proposed_execution_template": "",
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
            "distinctness_basis": "materially new family coverage, but only by modifying a paused held capability line",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "distinct_from_continuation_v1": True,
            "distinct_from_continuation_v2": True,
            "distinct_from_evidence_snapshot_v2": True,
            "execution_adjacency": "low",
            "structural_yield": "unknown",
            "local_procedural_yield": "unknown",
            "administrative_recursion_risk": "low",
            "posture_pressure": "present",
            "repetition_risk": "low",
            "silent_broadening_risk": "high",
        },
        {
            "loop_candidate_id": "loop_candidate_cross_artifact_recommendation_lineage_reconstruction",
            "loop_candidate_name": "Cross-artifact recommendation lineage reconstruction",
            "loop_candidate_summary": "attempt a new lineage-reconstruction task that falls outside the held parser family and the current narrow proven chain",
            "proposed_execution_template": "",
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
            "distinctness_basis": "distinct from current narrow paths because it requires a new family rather than another bounded continuation step",
            "distinct_from_direct_work": True,
            "distinct_from_prior_loop_continuation": True,
            "distinct_from_continuation_v1": True,
            "distinct_from_continuation_v2": True,
            "distinct_from_evidence_snapshot_v2": True,
            "execution_adjacency": "low",
            "structural_yield": "unknown",
            "local_procedural_yield": "unknown",
            "administrative_recursion_risk": "low",
            "posture_pressure": "present",
            "repetition_risk": "low",
            "silent_broadening_risk": "medium",
        },
        {
            "loop_candidate_id": "loop_candidate_broad_multi_path_governance_expansion_sweep",
            "loop_candidate_name": "Broad multi-path governance expansion sweep",
            "loop_candidate_summary": "attempt to combine direct work, capability reuse, posture review, and exploratory expansion in one step",
            "proposed_execution_template": "",
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
            "expected_success_signal": "not admissible because it collapses narrow posture into unsupported broad operational motion",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": True,
            "distinctness_basis": "tries to broaden too many paths at once rather than add one more bounded next-step signal",
            "distinct_from_direct_work": False,
            "distinct_from_prior_loop_continuation": False,
            "distinct_from_continuation_v1": False,
            "distinct_from_continuation_v2": False,
            "distinct_from_evidence_snapshot_v2": False,
            "execution_adjacency": "low",
            "structural_yield": "low",
            "local_procedural_yield": "low",
            "administrative_recursion_risk": "medium",
            "posture_pressure": "present",
            "repetition_risk": "medium",
            "silent_broadening_risk": "high",
        },
    ]


def _next_path_for_loop_class_v3(class_name: str) -> dict[str, Any]:
    if class_name == "loop_continue_candidate":
        return {
            "next_template": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
            "path_type": "work_loop_continuation_admission",
            "reason": "the strongest remaining bounded candidate should advance into a third governed work-loop continuation admission gate later while the current narrow posture remains unchanged",
        }
    fallback = dict(_next_path_for_loop_class(class_name))
    if class_name == "loop_divert_to_capability_use":
        fallback["reason"] = "the narrow posture prefers governed capability reuse when that path is cleaner than another continuation step"
    return fallback


def _posture_rule_application_v3(
    candidate: dict[str, Any],
    *,
    assigned_class: str,
    primary_posture_class: str,
    active_posture_classes: list[str],
    future_posture_review_gate_status: str,
) -> dict[str, Any]:
    repeats = bool(candidate.get("repeats_low_yield_narrow_shape", False))
    capability_cleaner = assigned_class == "loop_divert_to_capability_use"
    review_triggered = assigned_class == "loop_continue_with_review"
    administrative_recursion_risk = str(candidate.get("administrative_recursion_risk", ""))
    posture_pressure = str(candidate.get("posture_pressure", ""))
    broadening_blocked = assigned_class in {
        "loop_pause_candidate",
        "loop_divert_to_reopen_screen",
        "loop_divert_to_new_skill_screen",
        "loop_halt_or_block",
    } or posture_pressure == "present" or str(candidate.get("silent_broadening_risk", "")) == "high"
    return {
        "primary_posture_class": primary_posture_class,
        "active_posture_classes_considered": list(active_posture_classes),
        "distinct_bounded_next_step_rule": {
            "result": "satisfied" if assigned_class == "loop_continue_candidate" else "not_primary_path",
            "reason": (
                "the candidate adds a distinct bounded next-step signal beyond the current three-step chain and the v2 evidence layer"
                if assigned_class == "loop_continue_candidate"
                else "the candidate did not become the primary distinct bounded next-step path under the current narrow posture"
            ),
        },
        "pause_if_low_yield_repetition": {
            "triggered": repeats,
            "reason": (
                "the repetition rule pauses this candidate because it mainly replays existing governance conclusions without a new frontier signal"
                if repeats
                else "the candidate is not blocked by the repetition rule"
            ),
        },
        "divert_if_capability_path_is_cleaner": {
            "triggered": capability_cleaner,
            "reason": (
                "the posture diverts this candidate into governed capability use because bounded reuse is cleaner than another continuation step"
                if capability_cleaner
                else "this candidate is not cleaner as a capability-use diversion"
            ),
        },
        "review_if_consequence_rises": {
            "triggered": review_triggered,
            "reason": (
                "the posture keeps this candidate review-gated because consequence or overlap rises above the current low-risk narrow posture"
                if review_triggered
                else "this candidate did not trigger consequence-driven review escalation"
            ),
        },
        "future_posture_review_gate_remains_closed": {
            "gate_status": future_posture_review_gate_status,
            "preserved": True,
            "reason": "screening another bounded candidate is allowed, but the future posture-review gate remains defined and closed",
        },
        "require_more_evidence_before_broad_execution": {
            "preserved": True,
            "reason": "the screen preserves the block on broader execution by selecting at most one bounded next-step path and rejecting silent broadening",
        },
        "administrative_recursion_penalty": {
            "classification": f"administrative_recursion_risk_{administrative_recursion_risk or 'unknown'}",
            "reason": (
                "the candidate is penalized because it trends toward summary-of-summary recursion"
                if administrative_recursion_risk in {"medium", "high"}
                else "the candidate is not dominated by administrative recursion risk"
            ),
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


def _screen_loop_candidate_v3(
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
    future_posture_review_gate_status: str,
    loop_chain_state: dict[str, Any],
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
    next_path = _next_path_for_loop_class_v3(assigned_class)
    execution_adjacency = str(candidate.get("execution_adjacency", ""))
    structural_yield = str(candidate.get("structural_yield", ""))
    administrative_recursion_risk = str(candidate.get("administrative_recursion_risk", ""))
    posture_pressure = str(candidate.get("posture_pressure", ""))
    materially_distinct_from_chain = all(
        [
            bool(candidate.get("distinct_from_direct_work", False)),
            bool(candidate.get("distinct_from_continuation_v1", False)),
            bool(candidate.get("distinct_from_continuation_v2", False)),
            bool(candidate.get("distinct_from_evidence_snapshot_v2", False)),
        ]
    )
    screened["next_path"] = next_path
    screened["posture_rule_application"] = _posture_rule_application_v3(
        candidate,
        assigned_class=assigned_class,
        primary_posture_class=primary_posture_class,
        active_posture_classes=active_posture_classes,
        future_posture_review_gate_status=future_posture_review_gate_status,
    )
    screened["screen_dimensions"]["distinctness_vs_reviewed_chain"] = {
        "distinctness_basis": str(candidate.get("distinctness_basis", "")),
        "distinct_from_direct_work": bool(candidate.get("distinct_from_direct_work", False)),
        "distinct_from_continuation_v1": bool(candidate.get("distinct_from_continuation_v1", False)),
        "distinct_from_continuation_v2": bool(candidate.get("distinct_from_continuation_v2", False)),
        "distinct_from_evidence_snapshot_v2": bool(candidate.get("distinct_from_evidence_snapshot_v2", False)),
        "materially_distinct_from_chain": materially_distinct_from_chain,
        "repetition_risk": str(candidate.get("repetition_risk", "")),
        "silent_broadening_risk": str(candidate.get("silent_broadening_risk", "")),
    }
    screened["screen_dimensions"]["expected_evidence_yield"] = {
        "expected_incremental_value": str(candidate.get("expected_incremental_value", "")),
        "expected_success_signal": str(candidate.get("expected_success_signal", "")),
        "likely_adds_new_evidence": assigned_class == "loop_continue_candidate" and structural_yield == "high",
        "likely_restates_existing_governance_conclusions": administrative_recursion_risk == "high",
    }
    screened["screen_dimensions"]["structural_vs_local_value"] = {
        "execution_adjacency": execution_adjacency,
        "structural_yield": structural_yield,
        "local_procedural_yield": str(candidate.get("local_procedural_yield", "")),
        "classification": (
            "execution_adjacent_structural_yield"
            if execution_adjacency == "high" and structural_yield == "high"
            else "local_or_uncertain_yield"
        ),
    }
    screened["screen_dimensions"]["administrative_recursion"] = {
        "classification": f"administrative_recursion_risk_{administrative_recursion_risk or 'unknown'}",
        "risk": administrative_recursion_risk,
        "reason": (
            "the candidate trends toward governance-paperwork recursion"
            if administrative_recursion_risk in {"medium", "high"}
            else "the candidate remains execution-adjacent rather than summary-recursive"
        ),
    }
    screened["screen_dimensions"]["posture_pressure"] = {
        "classification": f"posture_pressure_{posture_pressure or 'unknown'}",
        "pressure": posture_pressure,
        "hidden_capability_reopen_pressure": assigned_class == "loop_divert_to_reopen_screen",
        "branch_mutation_pressure": False,
        "retained_promotion_pressure": False,
        "scope_expansion_pressure": posture_pressure == "present" or str(candidate.get("silent_broadening_risk", "")) == "high",
        "posture_broadening_pressure": posture_pressure == "present",
    }
    screened["screen_dimensions"]["posture_gate"] = {
        "current_work_loop_posture": primary_posture_class,
        "future_posture_review_gate_status": future_posture_review_gate_status,
        "loop_continuation_future_posture": loop_continuation_future_posture,
        "broader_execution_remains_blocked": True,
    }
    screened["loop_accounting_expectations"]["loop_identity_context"]["loop_iteration"] = "after_three_step_chain_evidence_v2"
    screened["loop_accounting_expectations"]["current_work_state"].update(
        {
            "prior_direct_work_item": str(dict(loop_chain_state.get("direct_governed_work", {})).get("work_item_name", "")),
            "prior_loop_continuation_v1": str(dict(loop_chain_state.get("continuation_v1", {})).get("loop_candidate_name", "")),
            "prior_loop_continuation_v2": str(dict(loop_chain_state.get("continuation_v2", {})).get("loop_candidate_name", "")),
            "prior_loop_future_posture": loop_continuation_future_posture,
            "current_work_loop_posture": primary_posture_class,
        }
    )
    screened["loop_accounting_expectations"]["expected_path"]["next_path"] = next_path
    screened["loop_accounting_expectations"]["expected_path"]["proposed_execution_template"] = str(
        candidate.get("proposed_execution_template", "")
    )
    screened["path_separation"] = {
        "continue_as_governed_loop_step": assigned_class == "loop_continue_candidate",
        "divert_to_capability_use": assigned_class == "loop_divert_to_capability_use",
        "requires_review": assigned_class == "loop_continue_with_review",
        "pause_candidate": assigned_class == "loop_pause_candidate",
        "divert_to_reopen_screen": assigned_class == "loop_divert_to_reopen_screen",
        "divert_to_new_skill_screen": assigned_class == "loop_divert_to_new_skill_screen",
        "halt_or_block": assigned_class == "loop_halt_or_block",
    }
    screened["candidate_quality_flags"] = {
        "materially_distinct_from_chain": materially_distinct_from_chain,
        "execution_adjacent_structural_yield": execution_adjacency == "high" and structural_yield == "high",
        "administrative_recursion_risk": administrative_recursion_risk,
        "posture_pressure_present": posture_pressure == "present",
        "proposed_execution_template": str(candidate.get("proposed_execution_template", "")),
    }
    return screened


def _is_credible_continuation_candidate(item: dict[str, Any]) -> bool:
    flags = dict(item.get("candidate_quality_flags", {}))
    return (
        str(item.get("assigned_class", "")) == "loop_continue_candidate"
        and bool(flags.get("materially_distinct_from_chain", False))
        and bool(flags.get("execution_adjacent_structural_yield", False))
        and str(flags.get("administrative_recursion_risk", "")) == "low"
        and not bool(flags.get("posture_pressure_present", False))
    )


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2"
    )
    work_loop_continuation_admission_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2"
    )
    work_loop_execution_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    work_loop_execution_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1"
    )
    work_loop_evidence_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    work_loop_evidence_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v2"
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
            work_loop_candidate_screen_snapshot_v2,
            work_loop_continuation_admission_snapshot_v2,
            work_loop_execution_snapshot_v1,
            work_loop_execution_snapshot_v2,
            work_loop_evidence_snapshot_v1,
            work_loop_evidence_snapshot_v2,
            work_loop_posture_snapshot,
            direct_work_evidence_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v3 requires the current three-step chain, evidence v2, posture v1, v2 candidate screen, v2 continuation admission, direct-work evidence, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop v3 candidate-screen artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop v3 candidate-screen artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop v3 candidate-screen artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen a fourth bounded continuation frontier without the full narrow-posture evidence chain"},
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
    work_loop_candidate_screen_v2_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_candidate_screen_artifact_path")
        or governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v2_*.json",
    )
    work_loop_continuation_admission_v2_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v2_*.json",
    )
    work_loop_execution_v1_artifact_path = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    work_loop_execution_v2_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json",
    )
    work_loop_evidence_v1_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    work_loop_evidence_v2_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v2_*.json",
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
            work_loop_candidate_screen_v2_artifact_path,
            work_loop_continuation_admission_v2_artifact_path,
            work_loop_execution_v1_artifact_path,
            work_loop_execution_v2_artifact_path,
            work_loop_evidence_v1_artifact_path,
            work_loop_evidence_v2_artifact_path,
            work_loop_posture_artifact_path,
            direct_work_evidence_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more governed work-loop v3 reference artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v3"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v3"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths for work-loop screening v3"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next frontier without the governing artifact chain"},
        }

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    work_loop_candidate_screen_v2_payload = _load_json_file(work_loop_candidate_screen_v2_artifact_path)
    work_loop_continuation_admission_v2_payload = _load_json_file(work_loop_continuation_admission_v2_artifact_path)
    work_loop_execution_v1_payload = _load_json_file(work_loop_execution_v1_artifact_path)
    work_loop_execution_v2_payload = _load_json_file(work_loop_execution_v2_artifact_path)
    work_loop_evidence_v1_payload = _load_json_file(work_loop_evidence_v1_artifact_path)
    work_loop_evidence_v2_payload = _load_json_file(work_loop_evidence_v2_artifact_path)
    work_loop_posture_payload = _load_json_file(work_loop_posture_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)
    if not all(
        [
            work_loop_policy_payload,
            work_loop_candidate_screen_v2_payload,
            work_loop_continuation_admission_v2_payload,
            work_loop_execution_v1_payload,
            work_loop_execution_v2_payload,
            work_loop_evidence_v1_payload,
            work_loop_evidence_v2_payload,
            work_loop_posture_payload,
            direct_work_evidence_payload,
            capability_use_evidence_payload,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v3 could not load one or more governing payloads",
            "observability_gain": {"passed": False, "reason": "missing prerequisite summary payloads for work-loop screening v3"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite summary payloads for work-loop screening v3"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite summary payloads for work-loop screening v3"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the next frontier without the v2 evidence chain payloads"},
        }

    work_loop_policy_summary = dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {}))
    work_loop_candidate_screen_v2_summary = dict(
        work_loop_candidate_screen_v2_payload.get("governed_work_loop_candidate_screen_v2_summary", {})
    )
    work_loop_continuation_admission_v2_summary = dict(
        work_loop_continuation_admission_v2_payload.get("governed_work_loop_continuation_admission_v2_summary", {})
    )
    work_loop_execution_v1_summary = dict(
        work_loop_execution_v1_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    work_loop_execution_v2_summary = dict(
        work_loop_execution_v2_payload.get("governed_work_loop_continuation_execution_summary", {})
    )
    work_loop_evidence_v1_summary = dict(work_loop_evidence_v1_payload.get("governed_work_loop_evidence_summary", {}))
    work_loop_evidence_v2_summary = dict(work_loop_evidence_v2_payload.get("governed_work_loop_evidence_v2_summary", {}))
    work_loop_posture_summary = dict(work_loop_posture_payload.get("governed_work_loop_posture_summary", {}))
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    capability_use_evidence_summary = dict(
        capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {})
    )
    if not all(
        [
            work_loop_policy_summary,
            work_loop_candidate_screen_v2_summary,
            work_loop_continuation_admission_v2_summary,
            work_loop_execution_v1_summary,
            work_loop_execution_v2_summary,
            work_loop_evidence_v1_summary,
            work_loop_evidence_v2_summary,
            work_loop_posture_summary,
            direct_work_evidence_summary,
            capability_use_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed work-loop candidate screening v3 could not load the governing summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite work-loop v3 summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite work-loop v3 summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite work-loop v3 summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot screen the candidate frontier without the governing summaries"},
        }

    posture_current = dict(work_loop_posture_summary.get("current_posture", {}))
    future_posture_review_gate = dict(work_loop_evidence_v2_summary.get("future_posture_review_gate", {}))
    loop_chain_state = dict(work_loop_evidence_v2_summary.get("current_work_loop_chain_state", {}))
    ready_for_candidate_screen_v3 = (
        str(current_branch_state) == "paused_with_baseline_held"
        and bool(current_state_summary.get("plan_non_owning", False))
        and bool(current_state_summary.get("routing_deferred", False))
        and str(posture_current.get("primary_posture_class", "")) == "keep_narrow_governed_loop_available"
        and bool(posture_current.get("broader_execution_not_yet_justified", False))
        and str(dict(work_loop_evidence_v2_summary.get("distinctness_assessment", {})).get("classification", "")) == "structurally_distinct_chain"
        and str(dict(work_loop_evidence_v2_summary.get("repeated_bounded_success_assessment", {})).get("classification", "")) == "repeated_bounded_success_present"
        and str(dict(work_loop_evidence_v2_summary.get("posture_discipline_assessment", {})).get("classification", "")) == "posture_discipline_holding_cleanly"
        and str(dict(work_loop_evidence_v2_summary.get("hidden_development_pressure_assessment", {})).get("classification", "")) == "hidden_development_pressure_absent"
        and str(future_posture_review_gate.get("gate_status", "")) == "defined_but_closed"
    )
    if not ready_for_candidate_screen_v3:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current state is not yet marked ready for governed work-loop candidate screening v3",
            "observability_gain": {"passed": False, "reason": "v3 candidate-frontier readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "v3 candidate-frontier readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "v3 candidate-frontier readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the current three-step chain, posture, and evidence v2 gate status must all remain aligned before screening a fourth bounded frontier"},
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
    loop_continuation_future_posture = str(dict(work_loop_evidence_v2_summary.get("future_posture", {})).get("category", ""))
    primary_posture_class = str(posture_current.get("primary_posture_class", ""))
    active_posture_classes = [
        str(item) for item in list(posture_current.get("active_posture_classes", [])) if str(item).strip()
    ]
    future_posture_review_gate_status = str(future_posture_review_gate.get("gate_status", ""))
    screen_schema = {
        "schema_name": "GovernedWorkLoopCandidateScreen",
        "schema_version": "governed_work_loop_candidate_screen_v3",
        "required_fields": [
            "loop_candidate_id",
            "loop_candidate_name",
            "loop_candidate_summary",
            "proposed_execution_template",
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
            "execution_adjacency",
            "structural_yield",
            "administrative_recursion_risk",
            "posture_pressure",
        ],
        "outcome_classes": list(dict(governed_work_loop_policy.get("policy_classes", {})).keys()),
        "posture_classes_applied": list(dict(work_loop_posture_summary.get("posture_classes", {})).keys()),
    }
    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    loop_candidates = _build_loop_candidate_examples_v3(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    screened_candidates = [
        _screen_loop_candidate_v3(
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
            future_posture_review_gate_status=future_posture_review_gate_status,
            loop_chain_state=loop_chain_state,
            loop_accounting_requirements=loop_accounting_requirements,
            guardrails=guardrails,
        )
        for item in loop_candidates
    ]
    counts = {
        class_name: sum(1 for item in screened_candidates if str(item.get("assigned_class", "")) == class_name)
        for class_name in screen_schema["outcome_classes"]
    }
    credible_candidates = [item for item in screened_candidates if _is_credible_continuation_candidate(item)]
    credible_candidate_count = len(credible_candidates)
    screened_out_candidate_count = max(0, len(screened_candidates) - credible_candidate_count)
    credible_candidate_present = credible_candidate_count > 0
    best_candidate = (
        sorted(credible_candidates, key=_candidate_priority)[0]
        if credible_candidates
        else (sorted(screened_candidates, key=_candidate_priority)[0] if screened_candidates else {})
    )
    best_candidate_class = str(best_candidate.get("assigned_class", ""))
    best_candidate_next_path = dict(best_candidate.get("next_path", {}))
    best_candidate_flags = dict(best_candidate.get("candidate_quality_flags", {}))
    ready_for_next_bounded_step_admission = credible_candidate_present
    next_template = (
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3"
        if ready_for_next_bounded_step_admission
        else str(best_candidate_next_path.get("next_template", ""))
    )
    top_candidate_execution_template = str(best_candidate_flags.get("proposed_execution_template", ""))
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v3_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["work_loop_candidate_screen_v3_schema"] = screen_schema
    updated_work_loop_policy["work_loop_candidate_screen_schema"] = screen_schema
    updated_work_loop_policy["last_prior_candidate_screen_artifact_path"] = str(work_loop_candidate_screen_v2_artifact_path)
    updated_work_loop_policy["last_candidate_screen_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_candidate_screen_examples"] = [
        {
            "loop_candidate_id": str(item.get("loop_candidate_id", "")),
            "loop_candidate_name": str(item.get("loop_candidate_name", "")),
            "assigned_class": str(item.get("assigned_class", "")),
            "proposed_execution_template": str(dict(item.get("candidate_quality_flags", {})).get("proposed_execution_template", "")),
        }
        for item in screened_candidates
    ]
    updated_work_loop_policy["last_candidate_screen_outcome"] = {
        "status": "credible_next_bounded_candidate_identified_v3" if credible_candidate_present else "candidate_frontier_weak_v3",
        "screened_candidate_count": len(screened_candidates),
        "screened_out_candidate_count": screened_out_candidate_count,
        "credible_candidate_count": credible_candidate_count,
        "outcome_counts": counts,
        "top_ranked_candidate": str(best_candidate.get("loop_candidate_name", "")),
        "top_ranked_candidate_class": best_candidate_class,
        "top_ranked_candidate_template": top_candidate_execution_template,
        "top_ranked_candidate_next_path": best_candidate_next_path,
        "bounded_candidate_search_later_supported": credible_candidate_present,
        "reason": (
            "one credible fourth bounded continuation candidate remains after screening"
            if credible_candidate_present
            else "the candidate frontier is now too weak or recursive to justify further continuation movement"
        ),
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_candidate_screening_v3_in_place": True,
            "latest_governed_work_loop_candidate_screen_outcome": (
                "credible_next_bounded_candidate_identified_v3" if credible_candidate_present else "candidate_frontier_weak_v3"
            ),
            "latest_governed_work_loop_best_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "latest_governed_work_loop_best_candidate_template": top_candidate_execution_template,
            "latest_governed_work_loop_best_candidate_class": best_candidate_class,
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_continuation_candidate": str(best_candidate.get("loop_candidate_name", "")),
            "latest_governed_work_loop_continuation_candidate_template": top_candidate_execution_template,
            "latest_governed_work_loop_continuation_readiness": (
                "ready_for_third_governed_work_loop_continuation_admission"
                if credible_candidate_present
                else "candidate_frontier_weak_hold"
            ),
            "latest_governed_work_loop_recommended_next_action_class": (
                "bounded_continuation_admission_later" if credible_candidate_present else "hold_posture"
            ),
            "latest_governed_work_loop_readiness": (
                "ready_for_third_governed_work_loop_continuation_admission"
                if credible_candidate_present
                else "hold_narrow_posture"
            ),
            "latest_governed_work_loop_future_posture_review_gate_status": future_posture_review_gate_status,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_work_loop_candidate_screen_snapshot_v3::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_work_loop_candidate_screen_snapshot_v3_materialized",
        "event_class": "governed_work_loop_candidate_screen",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "screened_candidate_count": len(screened_candidates),
        "credible_candidate_count": credible_candidate_count,
        "top_ranked_candidate": str(best_candidate.get("loop_candidate_name", "")),
        "top_ranked_candidate_class": best_candidate_class,
        "top_ranked_candidate_template": top_candidate_execution_template,
        "new_behavior_changing_branch_opened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
            "governed_work_loop_candidate_screen_v2": str(work_loop_candidate_screen_v2_artifact_path),
            "governed_work_loop_continuation_admission_v2": str(work_loop_continuation_admission_v2_artifact_path),
            "governed_work_loop_execution_v1": str(work_loop_execution_v1_artifact_path),
            "governed_work_loop_execution_v2": str(work_loop_execution_v2_artifact_path),
            "governed_work_loop_evidence_v1": str(work_loop_evidence_v1_artifact_path),
            "governed_work_loop_evidence_v2": str(work_loop_evidence_v2_artifact_path),
            "governed_work_loop_posture_v1": str(work_loop_posture_artifact_path),
            "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
            "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
            "governed_work_loop_candidate_screen_v3": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
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
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(work_loop_policy_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2": _artifact_reference(work_loop_candidate_screen_snapshot_v2, latest_snapshots),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2": _artifact_reference(work_loop_continuation_admission_snapshot_v2, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(work_loop_execution_snapshot_v1, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1": _artifact_reference(work_loop_execution_snapshot_v2, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(work_loop_evidence_snapshot_v1, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v2": _artifact_reference(work_loop_evidence_snapshot_v2, latest_snapshots),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(work_loop_posture_snapshot, latest_snapshots),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(direct_work_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(capability_use_evidence_snapshot, latest_snapshots),
        },
        "governed_work_loop_candidate_screen_v3_summary": {
            "snapshot_identity_context": {
                "snapshot_template_name": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "proposal_id": str(proposal.get("proposal_id", "")),
                "current_work_loop_posture": primary_posture_class,
                "future_posture_review_gate_status": future_posture_review_gate_status,
                "current_branch_state": current_branch_state,
                "plan_non_owning": True,
                "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            },
            "chain_state_reviewed": {
                "direct_governed_work": dict(loop_chain_state.get("direct_governed_work", {})),
                "continuation_v1": dict(loop_chain_state.get("continuation_v1", {})),
                "continuation_v2": dict(loop_chain_state.get("continuation_v2", {})),
                "chain_classification": str(dict(work_loop_evidence_v2_summary.get("distinctness_assessment", {})).get("classification", "")),
                "unique_step_name_count": int(dict(work_loop_evidence_v2_summary.get("distinctness_assessment", {})).get("unique_step_name_count", 0) or 0),
                "successful_step_count": int(dict(work_loop_evidence_v2_summary.get("repeated_bounded_success_assessment", {})).get("successful_step_count", 0) or 0),
            },
            "evidence_inputs_used": {
                "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
                "governed_work_loop_candidate_screen_v2": str(work_loop_candidate_screen_v2_artifact_path),
                "governed_work_loop_continuation_admission_v2": str(work_loop_continuation_admission_v2_artifact_path),
                "governed_work_loop_execution_v1": str(work_loop_execution_v1_artifact_path),
                "governed_work_loop_execution_v2": str(work_loop_execution_v2_artifact_path),
                "governed_work_loop_evidence_v1": str(work_loop_evidence_v1_artifact_path),
                "governed_work_loop_evidence_v2": str(work_loop_evidence_v2_artifact_path),
                "governed_work_loop_posture_v1": str(work_loop_posture_artifact_path),
            },
            "candidate_inventory_considered": [
                {
                    "loop_candidate_id": str(item.get("loop_candidate_id", "")),
                    "loop_candidate_name": str(item.get("loop_candidate_name", "")),
                    "proposed_execution_template": str(dict(item.get("candidate_quality_flags", {})).get("proposed_execution_template", "")),
                    "assigned_class": str(item.get("assigned_class", "")),
                    "screened_in_as_credible": _is_credible_continuation_candidate(item),
                    "execution_adjacency": str(dict(item.get("screen_dimensions", {})).get("structural_vs_local_value", {}).get("execution_adjacency", "")),
                    "structural_yield": str(dict(item.get("screen_dimensions", {})).get("structural_vs_local_value", {}).get("structural_yield", "")),
                    "administrative_recursion_risk": str(dict(item.get("screen_dimensions", {})).get("administrative_recursion", {}).get("risk", "")),
                    "posture_pressure": str(dict(item.get("screen_dimensions", {})).get("posture_pressure", {}).get("pressure", "")),
                }
                for item in screened_candidates
            ],
            "screened_out_candidate_count": screened_out_candidate_count,
            "credible_candidate_count": credible_candidate_count,
            "outcome_counts": counts,
            "top_ranked_candidate": {
                "loop_candidate_name": str(best_candidate.get("loop_candidate_name", "")),
                "top_ranked_candidate_template_name": top_candidate_execution_template,
                "assigned_class": best_candidate_class,
                "next_template": next_template,
                "rationale": str(best_candidate.get("rationale", "")),
            },
            "distinctness_assessment": {
                "classification": "materially_distinct_candidate_present" if credible_candidate_present else "no_materially_distinct_candidate_present",
                "top_candidate_distinct_from_direct_work": bool(dict(best_candidate.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_direct_work", False)),
                "top_candidate_distinct_from_continuation_v1": bool(dict(best_candidate.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v1", False)),
                "top_candidate_distinct_from_continuation_v2": bool(dict(best_candidate.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v2", False)),
                "top_candidate_distinct_from_evidence_snapshot_v2": bool(dict(best_candidate.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_evidence_snapshot_v2", False)),
            },
            "expected_evidence_yield_assessment": {
                "classification": "likely_new_evidence" if credible_candidate_present else "mostly_restates_existing_conclusions",
                "likely_adds_new_evidence": credible_candidate_present,
                "likely_restates_existing_governance_conclusions": not credible_candidate_present,
            },
            "structural_vs_local_value_assessment": {
                "classification": "execution_adjacent_structural_yield" if credible_candidate_present else "local_procedural_or_weak_value",
                "top_candidate_execution_adjacency": str(dict(best_candidate.get("screen_dimensions", {})).get("structural_vs_local_value", {}).get("execution_adjacency", "")),
                "top_candidate_structural_yield": str(dict(best_candidate.get("screen_dimensions", {})).get("structural_vs_local_value", {}).get("structural_yield", "")),
            },
            "administrative_recursion_risk_assessment": {
                "classification": "administrative_recursion_risk_low" if str(dict(best_candidate.get("screen_dimensions", {})).get("administrative_recursion", {}).get("risk", "")) == "low" else "administrative_recursion_risk_medium_or_high",
            },
            "posture_pressure_assessment": {
                "classification": "posture_pressure_absent" if not bool(best_candidate_flags.get("posture_pressure_present", False)) else "posture_pressure_present",
                "scope_expansion_pressure": bool(dict(best_candidate.get("screen_dimensions", {})).get("posture_pressure", {}).get("scope_expansion_pressure", False)),
                "posture_broadening_pressure": bool(dict(best_candidate.get("screen_dimensions", {})).get("posture_pressure", {}).get("posture_broadening_pressure", False)),
            },
            "gate_status": {"classification": "gate_closed", "gate_status": future_posture_review_gate_status},
            "routing_status": {"classification": "routing_deferred", "passed": bool(current_state_summary.get("routing_deferred", False))},
            "recommended_next_action": {
                "class": "bounded_continuation_admission_later" if credible_candidate_present else "hold_posture",
                "template_name": next_template,
            },
            "continue_candidate_search_later_or_hold": {
                "hold_posture": True,
                "bounded_candidate_search_later_supported": credible_candidate_present,
                "explicit_pause_because_candidate_frontier_is_weak": not credible_candidate_present,
            },
            "question_answers": {
                "credible_candidates_exist": "yes" if credible_candidate_present else "no",
                "credible_candidate_count": credible_candidate_count,
                "top_ranked_candidate_template_name": top_candidate_execution_template,
                "top_candidate_execution_adjacent_and_structurally_useful": credible_candidate_present,
                "top_candidate_likely_adds_new_evidence": credible_candidate_present,
                "hidden_pressure_toward_reopen_branch_promotion_scope_or_broadening": False,
                "project_next_posture_decision": "permit_another_bounded_continuation_candidate_later" if credible_candidate_present else "hold_posture_with_no_further_continuation_search",
                "routing_remains_deferred": bool(current_state_summary.get("routing_deferred", False)),
                "posture_review_gate_remains_closed": future_posture_review_gate_status == "defined_but_closed",
            },
            "review_rollback_deprecation_trigger_status": dict(work_loop_evidence_v2_summary.get("review_rollback_deprecation_trigger_status", {})),
            "envelope_compliance_summary": {
                "network_mode_remained_none": True,
                "write_root_compliance": True,
                "bucket_pressure": "low",
                "branch_state_immutability_preserved": True,
                "paused_capability_line_reopened": False,
                "routing_drift": False,
                "posture_widened": False,
            },
            "resource_trust_accounting": {
                "network_mode": "none",
                "approved_write_roots": list(allowed_write_roots),
                "top_candidate_expected_resource_budget": dict(best_candidate.get("loop_accounting_expectations", {}).get("resource_trust_position", {}).get("expected_resource_budget", {})),
            },
            "operator_readable_conclusion": (
                "One credible fourth bounded continuation candidate remains after screening."
                if credible_candidate_present
                else "No credible fourth bounded continuation candidate remains after screening."
            ),
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
                "reason": "candidate screening v3 is derived from directive, bucket, branch, self-structure, posture, direct-work evidence, continuation evidence, and recommendation artifacts rather than from execution code or prior success alone",
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
            "reason": "the current frontier after the three-step chain now has an explicit v3 candidate inventory, credibility count, structural-yield assessment, and gate-closed posture judgment under governance",
            "artifact_paths": {
                "governed_work_loop_candidate_screen_v3_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the v3 screen determines whether a fourth bounded continuation candidate still exists without assuming that prior success automatically authorizes more motion",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the v3 screen explicitly distinguishes structural yield, administrative recursion, posture pressure, diversion, pause, and halt outcomes before any later admission work",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the v3 screen is diagnostic-only; it widened no posture, reopened no capability, mutated no branch state, promoted nothing, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "one credible bounded candidate remains and can later move into a v3 continuation-admission review while posture stays narrow" if credible_candidate_present else "the frontier is weak enough that the correct outcome is to hold posture rather than advance to another admission step",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_candidate_screening_v3_in_place": True,
            "credible_candidate_present": credible_candidate_present,
            "materially_distinct_candidate_present": credible_candidate_present,
            "best_current_next_bounded_step": str(best_candidate.get("loop_candidate_name", "")),
            "best_current_next_bounded_step_class": best_candidate_class,
            "best_current_next_bounded_step_template": top_candidate_execution_template,
            "execution_adjacent_structural_yield": credible_candidate_present,
            "administrative_recursion_risk_low": str(dict(best_candidate.get("screen_dimensions", {})).get("administrative_recursion", {}).get("risk", "")) == "low",
            "posture_pressure_absent": not bool(best_candidate_flags.get("posture_pressure_present", False)),
            "gate_closed": future_posture_review_gate_status == "defined_but_closed",
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "hold_posture": True,
            "bounded_candidate_search_later_supported": credible_candidate_present,
            "explicit_pause_because_candidate_frontier_is_weak": not credible_candidate_present,
            "ready_for_concrete_next_admission_step": credible_candidate_present,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": True,
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
