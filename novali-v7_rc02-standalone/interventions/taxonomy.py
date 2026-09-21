from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict


CANONICAL_EVALUATION_STAGES = [
    "static_check",
    "shadow",
    "benchmark",
    "canary_gate",
]

EVALUATION_STAGE_ALIASES = {
    "static": "static_check",
    "static_check": "static_check",
    "shadow": "shadow",
    "benchmark": "benchmark",
    "canary": "canary_gate",
    "canary_gate": "canary_gate",
}


PROMOTION_STAGES = [
    "draft",
    "static_checked",
    "shadow_evaluated",
    "benchmark_evaluated",
    "canary_eligible",
    "completed_plan",
    "failed_stage",
    "canary_active",
    "promoted",
    "reverted",
    "archived",
]


PROPOSAL_TYPE_SPECS: Dict[str, Dict[str, Any]] = {
    "score_reweight": {
        "description": "Adjust an existing score composition weight without changing benchmark semantics.",
        "evaluation_semantics": "control_changing",
        "changes": ["scoring weight", "selection weighting", "calibration scalar"],
        "safety_constraints": ["projection safety must not regress", "no unsafe overcommit drift"],
        "evaluation": ["static_check", "shadow", "benchmark"],
    },
    "critic_split": {
        "description": "Split one blended critic into more explicit components for diagnosis or routing.",
        "evaluation_semantics": "diagnostic",
        "changes": ["critic decomposition", "forecast target split"],
        "safety_constraints": ["projection veto remains primary", "rollback union remains diagnostic"],
        "evaluation": ["static_check", "shadow", "benchmark"],
    },
    "routing_rule": {
        "description": "Route a narrow candidate class through a bounded override path.",
        "evaluation_semantics": "control_changing",
        "changes": ["override gate", "routing eligibility", "variant-only live path"],
        "safety_constraints": ["baseline default unchanged", "full adopt unchanged", "projection veto unchanged"],
        "evaluation": ["static_check", "shadow", "benchmark", "canary_gate"],
    },
    "memory_summary": {
        "description": "Persist a condensed intervention memory or blocker pattern for later reuse.",
        "evaluation_semantics": "diagnostic",
        "changes": ["ledger memory", "summary heuristics", "failure memory"],
        "safety_constraints": ["no live policy mutation", "audit-only behavior"],
        "evaluation": ["static_check", "shadow"],
    },
    "proposal_learning_loop": {
        "description": "Open or inspect proposal-learning-loop architecture surfaces without changing downstream live behavior.",
        "evaluation_semantics": "diagnostic",
        "changes": ["wm-owned context trace", "plan handoff observability", "upstream architecture probe"],
        "safety_constraints": [
            "no live policy mutation",
            "no threshold relaxation",
            "no routing ownership changes",
            "frozen benchmark semantics unchanged",
            "projection-safe envelope unchanged",
        ],
        "evaluation": ["static_check", "shadow"],
    },
    "support_contract": {
        "description": "Probe benchmark-only support and runner compatibility without changing control policy defaults.",
        "evaluation_semantics": "diagnostic",
        "changes": ["support-group compatibility", "runner admission contract", "benchmark-only coverage refinement"],
        "safety_constraints": ["no live policy mutation", "projection safety framing unchanged", "benchmark semantics unchanged"],
        "evaluation": ["static_check", "shadow"],
    },
    "safety_veto_patch": {
        "description": "Patch a trusted safety veto while preserving conservative defaults.",
        "evaluation_semantics": "control_changing",
        "changes": ["trusted veto", "safety cap", "guard precedence"],
        "safety_constraints": ["must not weaken projection safety without explicit approval"],
        "evaluation": ["static_check", "shadow", "benchmark", "canary_gate"],
    },
}


def normalize_stage_name(stage_name: str) -> str:
    return str(EVALUATION_STAGE_ALIASES.get(str(stage_name), str(stage_name)))


def normalize_evaluation_plan(plan: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for stage_name in list(plan or []):
        canonical = normalize_stage_name(str(stage_name))
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def proposal_evaluation_semantics(proposal_type: str) -> str:
    spec = dict(PROPOSAL_TYPE_SPECS.get(str(proposal_type), {}))
    return str(spec.get("evaluation_semantics", "control_changing"))


def _base_record(
    *,
    proposal_type: str,
    template_name: str,
    scope: str,
    trigger_reason: str,
    intended_benefit: Dict[str, Any],
    mechanism: Dict[str, Any],
    memory_dependencies: list[str] | None = None,
    targets_blockers: list[str] | None = None,
    notes: list[str] | None = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "proposal_id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
        "branch": "novali-v4",
        "template_name": str(template_name),
        "proposal_type": str(proposal_type),
        "evaluation_semantics": str(PROPOSAL_TYPE_SPECS[proposal_type]["evaluation_semantics"]),
        "scope": str(scope),
        "trigger_reason": str(trigger_reason),
        "intended_benefit": copy.deepcopy(intended_benefit),
        "mechanism": copy.deepcopy(mechanism),
        "memory_dependencies": list(memory_dependencies or []),
        "targets_blockers": list(targets_blockers or []),
        "constraints": copy.deepcopy(PROPOSAL_TYPE_SPECS[proposal_type]["safety_constraints"]),
        "evaluation_plan": copy.deepcopy(PROPOSAL_TYPE_SPECS[proposal_type]["evaluation"]),
        "evaluation": {
            "forecast": {},
            "static": {},
            "shadow": {},
            "benchmark": {},
            "canary": {},
        },
        "failure_tags": [],
        "promotion_status": "draft",
        "stage_history": [],
        "notes": list(notes or []),
    }


def build_proposal_template(template_name: str) -> Dict[str, Any]:
    name = str(template_name)
    if name == "routing_rule.targeted_gain_goal_proj_margin_01":
        from runtime_config import available_live_policy_variants

        if "targeted_gain_goal_proj_margin_01" not in available_live_policy_variants():
            raise ValueError("Live policy variant targeted_gain_goal_proj_margin_01 is not available.")
        return _base_record(
            proposal_type="routing_rule",
            template_name=name,
            scope="candidate_canary",
            trigger_reason="benchmark-approved smallest-change routing refinement for gain_goal_conflict undercommitment",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "expected_provisional_got_reject",
                "secondary_family": "projection",
                "secondary_metric": "policy_match_rate",
            },
            mechanism={
                "component": "projection override margin",
                "old_value": 0.24,
                "new_value": 0.25,
                "reference_variant": "targeted_gain_goal_safe_window",
                "benchmark_variant": "targeted_gain_goal_proj_margin_01",
                "live_policy_variant": "targeted_gain_goal_proj_margin_01",
                "strict_projection_max": 0.48,
                "min_pred_gain_sign_prob": 0.20,
                "max_pred_gain_bad_prob": 0.62,
                "min_projected_score": 0.32,
                "max_persistence_streak": 0,
                "max_retained_evidence": 0.05,
                "max_moving_average": 0.05,
            },
            memory_dependencies=[
                "benchmark_policy_sweep_summary",
                "diagnostic_memory.override_dormancy_snapshot",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "First end-to-end intervention exercise.",
                "Uses the benchmark-approved smallest-change variant without changing default live policy.",
            ],
        )
    if name == "score_reweight.gain_goal_conflict_probe":
        record = _base_record(
            proposal_type="score_reweight",
            template_name=name,
            scope="shadow_only",
            trigger_reason="refine gain-goal discrimination inside the critic-v2 safe slice without weakening projection safety",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "slice_benchmark_like_retention",
                "secondary_family": "calibration",
                "secondary_metric": "slice_projection_safety",
            },
            mechanism={
                "component": "gain_goal_slice_score",
                "old_value": "critic_split_v2_score",
                "new_value": "gain_goal_reweighted_slice_score",
                "probe_only": True,
                "comparison_reference": "critic_split.projection_gain_goal_v2",
                "reweighted_signals": [
                    "gain_goal_critic_v2",
                    "confidence",
                    "gain",
                    "pred_post_gain",
                    "benchmark_distance",
                    "projection_level_critic",
                    "projection_shape_critic",
                    "stability_critic_v2",
                    "segment_label",
                    "blocker_group",
                ],
                "blocker_sensitive_rules": [
                    "preserve critic-v2 projection-safe envelope before any gain-goal ranking change",
                    "boost benchmark_adjacent and gain_structure_shifted rows when benchmark proximity is strong",
                    "penalize benchmark-distance drift inside the safe slice",
                    "keep stability_sensitive and projection_far_shifted rows suppressed",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "gain-goal score probe only",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Builds directly on critic_split.projection_gain_goal_v2.",
            "Targets gain_goal_conflict discrimination inside the current broad-but-safe critic slice.",
        ]
        return record
    if name == "critic_split.projection_gain_goal_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="separate projection-sensitive safety from gain/goal promise so the exposed slice can be tested under a cleaner critic structure",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "slice_projection_safety",
                "secondary_family": "calibration",
                "secondary_metric": "slice_benchmark_like_retention",
            },
            mechanism={
                "component": "critic_targets",
                "old_value": "blended_gain_projection_goal",
                "new_value": "split_projection_gain_goal",
                "probe_only": True,
                "comparison_reference": "routing_rule.activation_window_probe",
                "split_signals": [
                    "pred_projection_bad_prob",
                    "pred_projection_error",
                    "confidence",
                    "gain",
                    "pred_post_gain",
                    "benchmark_distance",
                    "blocker_group",
                    "segment_label",
                ],
                "blocker_sensitive_rules": [
                    "projection critic sharply penalizes projection_guard risk and projection_error drift",
                    "stability_sensitive rows receive an extra safety-side penalty",
                    "gain/goal critic preserves gain_structure_shifted promise while keeping benchmark_adjacent bonuses narrow",
                    "projection_far_shifted remains excluded from slice targeting",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.score_reweight.blocker_sensitive_projection_probe",
                "diagnostic_memory.routing_rule.activation_window_probe",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "critic split is probe-only in this phase",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Compares directly against the latest routing activation probe.",
            "Focuses on score decomposition rather than routing-window relaxation.",
        ]
        return record
    if name == "critic_split.projection_gain_goal_v2":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="refine critic decomposition so projection level, projection shape, and gain-goal promise form a broader but still safe slice",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "slice_benchmark_alignment",
                "secondary_family": "calibration",
                "secondary_metric": "slice_projection_safety",
            },
            mechanism={
                "component": "critic_targets",
                "old_value": "split_projection_gain_goal_v1",
                "new_value": "split_projection_shape_level_gain_goal_v2",
                "probe_only": True,
                "comparison_reference": "critic_split.projection_gain_goal_v1",
                "split_signals": [
                    "pred_projection_bad_prob",
                    "boundary_distance",
                    "pred_projection_error",
                    "pred_projection_explosion_prob",
                    "confidence",
                    "gain",
                    "pred_post_gain",
                    "benchmark_distance",
                    "blocker_group",
                    "segment_label",
                ],
                "blocker_sensitive_rules": [
                    "projection level critic captures distance above safe boundary without collapsing all borderline rows",
                    "projection shape critic isolates error-shape mismatch separately from projection level",
                    "gain-goal critic preserves gain_structure_shifted and benchmark_adjacent promise",
                    "stability critic soft-excludes persistence/recovery-sensitive rows only when safety evidence is weak",
                    "projection_far_shifted remains excluded from the viable slice",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "critic split remains probe-only in this phase",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Builds on critic_split v1 and the failed slice-targeted benchmark sweep.",
            "Targets broader safe slice formation before any routing reconsideration.",
        ]
        return record
    if name == "critic_split.safe_slice_purity_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="improve benchmark-like retention inside the critic-v2 safe slice without collapsing coverage or undoing projection safety",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_benchmark_like_retention",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_benchmark_coverage",
            },
            mechanism={
                "component": "safe_slice_purity_critic",
                "old_value": "critic_split_v2_safe_slice_score",
                "new_value": "safe_slice_purity_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.projection_gain_goal_v2",
                "refined_signal_groups": [
                    "benchmark_distance",
                    "projection_shape_features",
                    "projection_level_features",
                    "gain_goal_promise_features",
                    "stability_sensitive_indicators",
                    "segment_label",
                    "blocker_group",
                ],
                "interaction_terms": [
                    "benchmark_distance_x_projection_shape",
                    "benchmark_distance_x_gain_goal_promise",
                    "safe_slice_status_x_segment_label",
                ],
                "blocker_sensitive_rules": [
                    "operate only inside the critic-v2 safe slice",
                    "preserve strong exclusion of clearly projection-unsafe cases",
                    "reward low benchmark-distance and low projection-shape drift jointly",
                    "favor gain_structure_shifted and benchmark_adjacent rows only when safe-slice purity evidence is strong",
                    "keep stability_sensitive rows penalized unless both projection-shape drift and benchmark-distance drift stay low",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.score_reweight.gain_goal_conflict_probe",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "safe-slice purity probe only",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Builds on the broader safe slice from critic_split.projection_gain_goal_v2.",
            "Targets purity-vs-coverage inside the safe slice rather than family-only emphasis.",
        ]
        return record
    if name == "critic_split.benchmark_distance_retention_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="test whether benchmark-distance-focused ranking can improve benchmark-like retention inside the critic-v2 safe slice without sacrificing useful coverage",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_benchmark_retention",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_benchmark_coverage",
            },
            mechanism={
                "component": "benchmark_distance_retention_critic",
                "old_value": "critic_split_v2_safe_slice_score",
                "new_value": "benchmark_distance_retention_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.projection_gain_goal_v2",
                "refined_signal_groups": [
                    "benchmark_distance",
                    "benchmark_distance_x_gain_goal_promise",
                    "benchmark_distance_x_projection_shape",
                    "projection_shape_features",
                    "projection_level_features",
                    "gain_goal_promise_features",
                    "stability_sensitive_indicators",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "two_stage_safe_slice",
                "blocker_sensitive_rules": [
                    "safe-slice admission remains identical to critic-v2",
                    "benchmark-distance-first ranking is applied only after safe-slice admission",
                    "reward low benchmark-distance with low projection-shape drift",
                    "reward low benchmark-distance with gain-goal promise when projection safety is already satisfied",
                    "keep stability_sensitive rows penalized unless safe-slice evidence is unusually strong",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.safe_slice_purity_probe_v1",
                "diagnostic_memory.critic_split.benchmark_distance_retention_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "benchmark-distance retention probe only",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Builds on critic_split.projection_gain_goal_v2 and critic_split.safe_slice_purity_probe_v1.",
            "Targets benchmark-like retention inside the already safe slice, not routing or broader family emphasis.",
        ]
        return record
    if name == "critic_split.benchmark_alignment_critic_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="analyze subtype and context structure inside the critic-v2 safe slice to explain retention failures, especially the seed-2 collapse",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_benchmark_retention",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_context_stability",
            },
            mechanism={
                "component": "benchmark_alignment_critic",
                "old_value": "critic_split_v2_safe_slice_score",
                "new_value": "benchmark_alignment_context_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.projection_gain_goal_v2",
                "refined_signal_groups": [
                    "safe_slice_subtype",
                    "stability_context_interaction",
                    "context_conditioned_gain_goal_interaction",
                    "context_conditioned_projection_shape_interaction",
                    "seed_local_candidate_scarcity",
                    "benchmark_distance_context",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "context_conditioned_safe_slice",
                "blocker_sensitive_rules": [
                    "safe-slice admission remains identical to critic-v2",
                    "subtype/context analysis happens only inside the already safe slice",
                    "seed-fragile scarcity and subtype mismatch are modeled explicitly",
                    "stability-sensitive rows stay penalized unless context and subtype support retention",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.safe_slice_purity_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "benchmark-alignment critic probe only",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Builds on critic_split.projection_gain_goal_v2 and critic_split.safe_slice_purity_probe_v1.",
            "Targets subtype/context structure inside the safe slice rather than another distance-only retry.",
        ]
        return record
    if name == "critic_split.benchmark_alignment_critic_v2":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="shadow_only",
            trigger_reason="follow up availability-focused diagnostic memory with a benchmark-alignment critic that models when benchmark-like candidates are present inside the safe slice",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_pool_benchmark_like_availability_retention",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_context_stability",
            },
            mechanism={
                "component": "benchmark_alignment_critic",
                "old_value": "benchmark_alignment_context_score_v1",
                "new_value": "benchmark_alignment_context_score_v2",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_alignment_critic_v1",
                "refined_signal_groups": [
                    "safe_pool_benchmark_like_availability",
                    "subtype_availability_interaction",
                    "scarcity_conditioned_alignment",
                    "context_conditioned_benchmark_distance",
                    "context_conditioned_projection_shape",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "availability_conditioned_safe_slice",
                "blocker_sensitive_rules": [
                    "safe-slice admission remains identical to critic-v2",
                    "availability/context modeling happens only inside the already safe slice",
                    "seed-collapse availability loss is modeled before any routing reconsideration",
                    "stability-sensitive rows stay penalized unless availability evidence supports retention",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.safe_slice_purity_probe_v1",
                "diagnostic_memory.critic_split.benchmark_distance_retention_probe_v1",
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v1",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v1",
                "diagnostic_memory.benchmark_context_availability_snapshot",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "benchmark-alignment critic probe only",
            "benchmark pack semantics unchanged",
        ]
        record["notes"] = [
            "Reserved follow-up to benchmark-context availability memory.",
            "Intended to model when benchmark-like candidates are present inside the safe slice before any routing reconsideration.",
        ]
        return record
    if name == "critic_split.benchmark_transfer_alignment_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="repair benchmark-transfer collapse inside the frozen benchmark control path after routing retest showed zero safe-pool materialization despite healthy critic baselines",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "benchmark_transfer_safe_pool_materialization",
                "secondary_family": "projection",
                "secondary_metric": "benchmark_transfer_projection_safety",
            },
            mechanism={
                "component": "benchmark_transfer_alignment_critic",
                "old_value": "routing_rule.slice_targeted_benchmark_sweep_v1 benchmark gate",
                "new_value": "benchmark_transfer_alignment_score_v1",
                "probe_only": True,
                "comparison_reference": "routing_rule.slice_targeted_benchmark_sweep_v1",
                "refined_signal_groups": [
                    "benchmark_transfer_support_compatibility",
                    "benchmark_transfer_stability_alignment",
                    "retained_like_profile_preservation",
                    "projection_borderline_overfire_reduction",
                    "benchmark_adjacent_transfer_alignment",
                    "stability_sensitive_support_extension",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "benchmark_transfer_alignment_safe_slice",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "support compatibility is only expanded inside frozen benchmark transfer analysis",
                    "stability_guard relaxation is only allowed for retained-like or benchmark-adjacent cases that stay projection-safe",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "diagnostic_memory.memory_summary.benchmark_transfer_blocker_snapshot_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "persistence_guard", "recovery_guard"],
            notes=[
                "Benchmark-only critic/score probe; not a routing retry.",
                "Targets support coverage and stability overfire inside the frozen benchmark transfer path.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "support_contract.benchmark_stability_sensitive_compat_probe_v1":
        record = _base_record(
            proposal_type="support_contract",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="repair benchmark-path support and runner compatibility for stability-sensitive persistence and recovery cases after benchmark-transfer alignment materialized a safe pool but left support blocks unchanged",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "benchmark_support_compatibility",
                "secondary_family": "recovery",
                "secondary_metric": "benchmark_support_compatibility",
            },
            mechanism={
                "component": "benchmark_stability_sensitive_support_contract",
                "old_value": "benchmark_transfer_alignment_score_v1",
                "new_value": "benchmark_stability_sensitive_support_contract_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_transfer_alignment_probe_v1",
                "refined_signal_groups": [
                    "support_group_mapping_precision",
                    "stage_aware_support_contract",
                    "stability_sensitive_runner_compatibility",
                    "persistence_guard_support_alignment",
                    "recovery_guard_support_alignment",
                    "projection_safe_transfer_selection",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "benchmark_support_contract_safe_slice",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "support compatibility refinement is benchmark-only",
                    "stability-sensitive persistence and recovery handling must stay stage-aware and auditable",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "diagnostic_memory.critic_split.benchmark_transfer_alignment_probe_v1",
                "diagnostic_memory.memory_summary.benchmark_transfer_blocker_snapshot_v1",
                "intervention_analytics",
            ],
            targets_blockers=["persistence_guard", "recovery_guard", "projection_guard"],
            notes=[
                "Benchmark-only support/runner compatibility probe; not a routing retry.",
                "Targets stability-sensitive persistence and recovery support coverage while preserving projection-safety framing.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "support_contract.recovery_runner_contract_fix_v1":
        record = _base_record(
            proposal_type="support_contract",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="repair family-asymmetric benchmark transfer after persistence clears the late benchmark-like path but recovery still fails in the runner/contract path",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "benchmark_transfer_contract_compatibility",
                "secondary_family": "persistence",
                "secondary_metric": "benchmark_transfer_pattern_reuse",
            },
            mechanism={
                "component": "recovery_runner_contract_fix",
                "old_value": "runner_path_incompatibility recovery skew",
                "new_value": "recovery_runner_contract_fix_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_like_transfer_alignment_probe_v1",
                "refined_signal_groups": [
                    "recovery_guard_support_group_mapping",
                    "recovery_post_support_validation",
                    "family_aware_contract_selection",
                    "subtype_conditioned_transfer_bridge",
                    "projection_safe_transfer_preservation",
                ],
                "ranking_mode": "benchmark_recovery_contract_fix",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "benchmark semantics remain frozen",
                    "fix scope is limited to recovery-specific runner and contract handling",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.recovery_transfer_asymmetry_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.memory_summary.runner_path_incompatibility_snapshot_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only support/runner fix candidate; not a routing change.",
                "Intended to generalize the persistence transfer success pattern into recovery without weakening projection safety.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.benchmark_like_transfer_alignment_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="repair late benchmark-like transfer collapse after runner-path diagnostics showed support resolution can materialize a safe pool but benchmark-like scoring still fails for stability-sensitive transfer cases",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "benchmark_like_transfer_alignment",
                "secondary_family": "recovery",
                "secondary_metric": "benchmark_like_transfer_alignment",
            },
            mechanism={
                "component": "benchmark_like_transfer_alignment_critic",
                "old_value": "benchmark_stability_sensitive_support_contract_v1",
                "new_value": "benchmark_like_transfer_alignment_score_v1",
                "probe_only": True,
                "comparison_reference": "support_contract.benchmark_stability_sensitive_compat_probe_v1",
                "refined_signal_groups": [
                    "resolved_support_transfer_alignment",
                    "benchmark_like_scoring_repair",
                    "benchmark_family_interpretation_alignment",
                    "stability_sensitive_subtype_rescue",
                    "non_benchmark_like_selection_suppression",
                    "projection_safe_transfer_selection",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "benchmark_like_transfer_alignment",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "support admission remains benchmark-only and stage-aware",
                    "late transfer alignment focuses on resolved persistence/recovery cases without broad routing changes",
                    "final selection must prefer benchmark-like rows and suppress cosmetic safe-pool gains",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.benchmark_transfer_alignment_probe_v1",
                "diagnostic_memory.support_contract.benchmark_stability_sensitive_compat_probe_v1",
                "diagnostic_memory.memory_summary.runner_path_incompatibility_snapshot_v1",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["persistence_guard", "recovery_guard", "projection_guard"],
            notes=[
                "Benchmark-only critic-transfer probe; not a routing retry.",
                "Targets late benchmark-like scoring collapse after support resolution rather than broadening admission.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.benchmark_like_scoring_preservation_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="preserve benchmark-like identity through late scoring after the benchmark family-balance probe widened safe-pool volume but erased persistence/recovery benchmark-like survivors",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "late_stage_benchmark_like_preservation",
                "secondary_family": "persistence",
                "secondary_metric": "safe_pool_admission_restoration",
            },
            mechanism={
                "component": "benchmark_like_scoring_preservation_critic",
                "old_value": "benchmark_family_balance_score_v1",
                "new_value": "benchmark_like_scoring_preservation_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_like_transfer_alignment_probe_v1",
                "refined_signal_groups": [
                    "verified_benchmark_like_survivor_preservation",
                    "recovery_late_scoring_identity_preservation",
                    "persistence_safe_pool_reentry",
                    "benchmark_like_label_protection",
                    "non_benchmark_like_selection_suppression",
                ],
                "ranking_mode": "benchmark_like_scoring_preservation",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "benchmark semantics remain frozen",
                    "scope is limited to benchmark-only late scorer preservation for persistence and recovery",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only critic/scoring-preservation probe; not a routing change.",
                "Preserves previously verified benchmark-like survivors instead of broadening admission.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.benchmark_like_scoring_preservation_probe_v2":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="stabilize the remaining late benchmark-like scoring failures after the first scorer-preservation probe kept three survivors but recovery_03 and persistence_12 still collapsed at scoring",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "residual_benchmark_like_scoring_stability",
                "secondary_family": "persistence",
                "secondary_metric": "persistence_safe_pool_benchmark_like_preservation",
            },
            mechanism={
                "component": "benchmark_like_scoring_preservation_critic",
                "old_value": "benchmark_like_scoring_preservation_score_v1",
                "new_value": "benchmark_like_scoring_preservation_score_v2",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_like_scoring_preservation_probe_v1",
                "refined_signal_groups": [
                    "current_survivor_set_freeze",
                    "residual_case_anchor_matching",
                    "late_benchmark_like_label_stabilization",
                    "selection_budget_hold_for_drift_control",
                    "non_benchmark_like_selection_suppression",
                ],
                "ranking_mode": "residual_benchmark_like_scoring_stabilization",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "benchmark semantics remain frozen",
                    "scope is limited to benchmark-only residual scorer stabilization for persistence and recovery",
                    "the currently selected survivor set is preserved so false-safe drift does not widen during the probe",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v1",
                "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only residual scorer-stabilization probe; not a routing or threshold change.",
                "Preserves the current selected survivors while testing whether the remaining late-scoring failures can keep benchmark-like identity.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.recovery_benchmark_like_alignment_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="refine late benchmark-like transfer alignment for recovery after the recovery runner/contract fix lets some recovery cases reach scoring but recovery-family interpretation mismatch still blocks survivors",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "benchmark_like_transfer_alignment",
                "secondary_family": "persistence",
                "secondary_metric": "benchmark_like_transfer_path_preservation",
            },
            mechanism={
                "component": "recovery_benchmark_like_alignment_critic",
                "old_value": "support_contract.recovery_runner_contract_fix_v1",
                "new_value": "recovery_benchmark_like_alignment_score_v1",
                "probe_only": True,
                "comparison_reference": "support_contract.recovery_runner_contract_fix_v1",
                "refined_signal_groups": [
                    "recovery_family_interpretation_alignment",
                    "late_benchmark_like_scoring_bridge",
                    "recovery_case_similarity_to_survivors",
                    "persistence_path_preservation",
                    "non_benchmark_like_selection_suppression",
                    "projection_safe_transfer_selection",
                ],
                "ranking_mode": "recovery_benchmark_like_alignment",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "benchmark semantics remain frozen",
                    "refinement scope is limited to recovery-family late benchmark-like alignment",
                    "final selection must not use non-benchmark-like rows as cosmetic gains",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.memory_summary.recovery_transfer_asymmetry_snapshot_v1",
                "diagnostic_memory.memory_summary.runner_path_incompatibility_snapshot_v1",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only recovery-family critic-transfer probe; not a routing change.",
                "Targets late benchmark-family interpretation mismatch after support resolution rather than widening admission.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.benchmark_family_balance_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="restore cross-family benchmark-like selection balance after recovery-family late transfer gains begin to displace persistence-family survivors at final selection",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "cross_family_benchmark_like_balance",
                "secondary_family": "persistence",
                "secondary_metric": "benchmark_like_selection_preservation",
            },
            mechanism={
                "component": "benchmark_family_balance_critic",
                "old_value": "recovery_benchmark_like_alignment_score_v1",
                "new_value": "benchmark_family_balance_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.recovery_benchmark_like_alignment_probe_v1",
                "refined_signal_groups": [
                    "cross_family_selection_budget_balance",
                    "persistence_survivor_preservation",
                    "recovery_gain_preservation",
                    "benchmark_like_family_mix_regularization",
                    "final_selection_tie_break_alignment",
                    "projection_safe_transfer_selection",
                ],
                "ranking_mode": "benchmark_family_balance",
                "blocker_sensitive_rules": [
                    "live default policy remains untouched",
                    "projection-safe envelope remains identical to the current critic lineage",
                    "benchmark semantics remain frozen",
                    "refinement scope is limited to cross-family balance inside benchmark-only late transfer selection",
                    "must preserve real recovery-family gains without displacing persistence through cosmetic budget competition",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only cross-family critic-transfer probe; not a routing change.",
                "Intended to preserve recovery gains while restoring persistence-family benchmark-like selection balance.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "memory_summary.override_dormancy_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="persist dormant override blocker distribution for later proposal conditioning",
            intended_benefit={
                "target_family": "calibration",
                "target_metric": "live_override_activation_visibility",
            },
            mechanism={
                "component": "intervention_memory",
                "old_value": "none",
                "new_value": "override_activation_summary_v1",
            },
            memory_dependencies=["intervention_ledger", "intervention_analytics"],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
        )
    if name == "memory_summary.live_distribution_gap_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="summarize how live rejected candidates differ from benchmark-safe routing opportunities",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "live_distribution_gap_visibility",
                "secondary_family": "calibration",
                "secondary_metric": "live_override_activation_visibility",
            },
            mechanism={
                "component": "live_distribution_gap_snapshot",
                "old_value": "none",
                "new_value": "live_vs_benchmark_gap_summary_v1",
                "focus": "live_reject_vs_benchmark_safe_candidates",
            },
            memory_dependencies=[
                "diagnostic_memory.override_dormancy_snapshot",
                "intervention_analytics",
                "ledger_routing_history",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to explain why benchmark-safe routing opportunities do not activate live.",
            ],
        )
    if name == "memory_summary.seed_context_shift_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="summarize safe-slice collapse conditions across seeds and contexts so future critic probes can model retention stability better",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_collapse_visibility",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_context_stability",
            },
            mechanism={
                "component": "seed_context_shift_snapshot",
                "old_value": "none",
                "new_value": "safe_slice_context_shift_summary_v1",
                "focus": "safe_slice_collapse_vs_non_collapse_context",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.safe_slice_purity_probe_v1",
                "diagnostic_memory.critic_split.benchmark_distance_retention_probe_v1",
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to explain seed/context collapse conditions inside the critic-v2 safe slice.",
            ],
        )
    if name == "memory_summary.benchmark_context_availability_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="summarize when benchmark-like candidates are present versus absent inside the already safe pool so future benchmark-alignment critics can model availability under context",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_pool_benchmark_like_availability_visibility",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_context_availability",
            },
            mechanism={
                "component": "benchmark_context_availability_snapshot",
                "old_value": "none",
                "new_value": "safe_pool_benchmark_like_availability_summary_v1",
                "focus": "safe_pool_benchmark_like_presence_vs_absence",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.safe_slice_purity_probe_v1",
                "diagnostic_memory.critic_split.benchmark_distance_retention_probe_v1",
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v1",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v1",
                "diagnostic_memory.seed_context_shift_snapshot",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to explain benchmark-like candidate availability inside the safe pool before any benchmark-alignment critic v2 work.",
            ],
        )
    if name == "memory_summary.safe_slice_selection_gap_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="explain why stability-context retention v2 preserved safe-pool benchmark-like availability but narrowed total selected benchmark-like count relative to benchmark-alignment critic v2",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_selection_gap_visibility",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_selection_stability",
            },
            mechanism={
                "component": "safe_slice_selection_gap_snapshot",
                "old_value": "none",
                "new_value": "safe_slice_selection_gap_summary_v1",
                "focus": "benchmark_alignment_v2_vs_stability_context_retention_v2",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.benchmark_context_availability_snapshot",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to isolate whether the remaining loss is upstream retention or selector narrowing inside the already safe slice.",
            ],
        )
    if name == "memory_summary.benchmark_transfer_blocker_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="explain why the repaired critic slice fails to transfer into any usable frozen-benchmark routing slice even after selector reliability was restored",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "benchmark_transfer_blocker_visibility",
                "secondary_family": "projection",
                "secondary_metric": "benchmark_transfer_stability_visibility",
            },
            mechanism={
                "component": "benchmark_transfer_blocker_snapshot",
                "old_value": "none",
                "new_value": "benchmark_transfer_blocker_summary_v1",
                "focus": "routing_rule.slice_targeted_benchmark_sweep_v1 zero-slice collapse attribution",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to separate benchmark support/contract blockers from true critic-transfer blockers after routing retest collapse.",
            ],
        )
    if name == "memory_summary.runner_path_incompatibility_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="explain exactly where benchmark-path runner incompatibility still breaks transfer for stability-sensitive persistence and recovery after support-contract probing created a cosmetic safe pool without benchmark-like transfer",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "runner_path_incompatibility_visibility",
                "secondary_family": "recovery",
                "secondary_metric": "runner_path_incompatibility_visibility",
            },
            mechanism={
                "component": "runner_path_incompatibility_snapshot",
                "old_value": "none",
                "new_value": "runner_path_incompatibility_summary_v1",
                "focus": "support-contract benchmark transfer stage tracing",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.benchmark_transfer_blocker_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_transfer_alignment_probe_v1",
                "diagnostic_memory.support_contract.benchmark_stability_sensitive_compat_probe_v1",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["persistence_guard", "recovery_guard", "projection_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to separate runner-path incompatibility from later benchmark-like scoring collapse inside the benchmark-only transfer path.",
            ],
        )
    if name == "memory_summary.recovery_transfer_asymmetry_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="explain why persistence now clears the late benchmark-like transfer path while recovery remains blocked earlier in the benchmark runner path",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "transfer_asymmetry_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "transfer_success_pattern_visibility",
            },
            mechanism={
                "component": "recovery_transfer_asymmetry_snapshot",
                "old_value": "runner_path_incompatibility_summary_v1",
                "new_value": "recovery_transfer_asymmetry_summary_v1",
                "focus": "persistence success versus recovery early runner-path failure",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.runner_path_incompatibility_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.support_contract.benchmark_stability_sensitive_compat_probe_v1",
                "diagnostic_memory.critic_split.benchmark_transfer_alignment_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to localize the exact stage divergence between persistence and recovery inside benchmark transfer.",
            ],
        )
    if name == "memory_summary.benchmark_family_balance_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="localize where benchmark-like identity collapses after the benchmark_family_balance_probe_v1 reranked the late transfer path",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "late_stage_benchmark_like_balance_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "persistence_recovery_benchmark_like_displacement_visibility",
            },
            mechanism={
                "component": "benchmark_family_balance_snapshot",
                "old_value": "benchmark_family_balance_score_v1",
                "new_value": "benchmark_family_balance_collapse_snapshot_v1",
                "focus": "stage-by-stage benchmark-like collapse localization after the balance probe widened the safe pool but erased benchmark-like identity",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to distinguish benchmark-like relabeling collapse from true final-selection displacement after the balance probe.",
            ],
        )
    if name == "memory_summary.final_selection_false_safe_margin_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="localize the final-selection false-safe frontier after stability_context_retention_probe_v2 preserved the safe benchmark-like pool but could not safely add either residual case",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "final_selection_false_safe_margin_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "add_vs_replace_benchmark_like_frontier_visibility",
            },
            mechanism={
                "component": "final_selection_false_safe_margin_snapshot",
                "old_value": "stability_context_retention_score_v2",
                "new_value": "final_selection_false_safe_margin_snapshot_v1",
                "focus": "diagnose whether residual benchmark-like rows fail because of shared selected-set frontier pressure, add-vs-replace guardrail coupling, or family-specific late penalties",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to explain why residual benchmark-like rows breach the false-safe cap only at final selection and whether safe replacement exists.",
            ],
        )
    if name == "memory_summary.swap_c_family_coverage_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="diagnose whether the confirmed swap_C incumbent is a reusable structural improvement or a fixed-cap family-compression patch after safe-trio confirmation",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "swap_c_family_coverage_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "selected_set_compression_vs_upstream_availability_visibility",
            },
            mechanism={
                "component": "swap_c_family_coverage_snapshot",
                "old_value": "safe_trio_incumbent_confirmation_v1",
                "new_value": "swap_c_family_coverage_snapshot_v1",
                "focus": "localize whether persistence-family exclusion under the confirmed incumbent is caused by upstream scarcity or downstream selected-set compression under the fixed false-safe cap",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Compares safe-pool family coverage against the confirmed swap_C selected set without reopening routing or changing the envelope.",
            ],
        )
    if name == "memory_summary.safe_trio_false_safe_invariance_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="diagnose whether the current safe-trio false-safe frontier is effectively invariant across size-3 trios or whether any composition-sensitive headroom remains under the same cap",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "safe_trio_false_safe_frontier_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "cap_preserving_family_balance_headroom_visibility",
            },
            mechanism={
                "component": "safe_trio_false_safe_invariance_snapshot",
                "old_value": "swap_c_family_coverage_snapshot_v1",
                "new_value": "safe_trio_false_safe_invariance_snapshot_v1",
                "focus": "separate trio-size and guardrail discretization effects from composition-sensitive utility differences across the currently safe benchmark-like trios",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1",
                "diagnostic_memory.critic_split.persistence_balanced_safe_trio_probe_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.memory_summary.final_selection_false_safe_margin_snapshot_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Intended to explain why all currently safe size-3 trios share the same false-safe delta and whether any critic-accessible headroom remains under the fixed cap.",
            ],
        )
    if name == "memory_summary.false_safe_frontier_control_characterization_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="characterize whether the exhausted false-safe frontier behaves as a hard discrete accounting boundary or whether any benchmark-only control headroom remains after swap_C incumbency and under-cap critic exhaustion",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "false_safe_frontier_control_headroom_visibility",
                "secondary_family": "persistence",
                "secondary_metric": "post_critic_branch_pause_vs_control_characterization_clarity",
            },
            mechanism={
                "component": "false_safe_frontier_control_characterization_snapshot",
                "old_value": "safe_trio_false_safe_invariance_snapshot_v1",
                "new_value": "false_safe_frontier_control_characterization_snapshot_v1",
                "focus": "compare the flat safe-trio frontier against the last benchmark-only control evidence to determine whether any safe control headroom exists beyond the exhausted critic line",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1",
                "diagnostic_memory.critic_split.persistence_balanced_safe_trio_probe_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Distinguishes a hard discrete false-safe frontier from any remaining benchmark-only control headroom without reopening routing or critic changes.",
            ],
        )
    if name == "memory_summary.v4_first_hypothesis_landscape_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="rank the first open novali-v4 hypothesis outside the exhausted novali-v3 under-cap critic line, using the carried-forward swap_C baseline and the hard-boundary frontier conclusion",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "v4_first_hypothesis_direction_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "branch_open_closed_landscape_visibility",
            },
            mechanism={
                "component": "v4_first_hypothesis_landscape_snapshot",
                "old_value": "false_safe_frontier_control_characterization_snapshot_v1",
                "new_value": "v4_first_hypothesis_landscape_snapshot_v1",
                "focus": "separate closed novali-v3 continuation lines from the first open novali-v4 branch direction and identify the safest owner family/template for that move",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.seed_context_shift_snapshot",
                "diagnostic_memory.benchmark_context_availability_snapshot",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Designed to choose the first substantive novali-v4 hypothesis without reopening the exhausted novali-v3 critic/control line.",
            ],
        )
    if name == "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="rank the first architecture-level upstream/context branch to open in novali-v4, explicitly outside the exhausted novali-v3 critic/control line",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "v4_architecture_branch_direction_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_vs_architecture_branch_separation",
            },
            mechanism={
                "component": "v4_architecture_upstream_context_branch_snapshot",
                "old_value": "v4_first_hypothesis_landscape_snapshot_v1",
                "new_value": "v4_architecture_upstream_context_branch_snapshot_v1",
                "focus": "separate repo-native architecture/context openings from renamed novali-v3 continuation lines and choose the first exact v4 architecture-owned next template",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.seed_context_shift_snapshot",
                "diagnostic_memory.benchmark_context_availability_snapshot",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Designed to identify the first architecture-level novali-v4 branch without reopening exhausted novali-v3 tuning or control lines.",
            ],
        )
    if name == "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="rank the proposal_learning_loop architecture/context surfaces and identify the best first real branch entry point for novali-v4 outside exhausted novali-v3 lines",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "proposal_learning_loop_branch_entry_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_surface_vs_downstream_governance_separation",
            },
            mechanism={
                "component": "v4_proposal_learning_loop_context_branch_snapshot",
                "old_value": "v4_architecture_upstream_context_branch_snapshot_v1",
                "new_value": "v4_proposal_learning_loop_context_branch_snapshot_v1",
                "focus": "separate world-model/planning context-formation surfaces from self-improvement/adoption/social-confidence surfaces and choose the first exact v4 branch entry template",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Designed to identify the first proposal_learning_loop entry surface without reopening exhausted novali-v3 critic/control lines.",
            ],
        )
    if name == "memory_summary.v4_world_model_planning_context_entry_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="resolve wm_/plan_ branch-entry ownership, scope, exclusions, and first implementation success criteria for novali-v4 without reopening exhausted novali-v3 lines",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_plan_branch_entry_design_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_scope_vs_downstream_boundary_clarity",
            },
            mechanism={
                "component": "v4_world_model_planning_context_entry_snapshot",
                "old_value": "v4_proposal_learning_loop_context_branch_snapshot_v1",
                "new_value": "v4_world_model_planning_context_entry_snapshot_v1",
                "focus": "choose exact wm_/plan_ entry ownership and scope, explicitly exclude downstream adoption/social-confidence ownership, and specify the first implementation template for novali-v4",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Designed to resolve the first real wm_/plan_ implementation boundary without reopening exhausted novali-v3 critic/control lines.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="open the first real novali-v4 proposal-learning-loop branch through wm_ as the primary owner with plan_ limited to the existing planning-structure handoff points",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_plan_context_observability",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_handoff_visibility_without_downstream_drift",
            },
            mechanism={
                "component": "v4_wm_primary_plan_structure_probe",
                "old_value": "v4_world_model_planning_context_entry_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "focus": "enable wm-owned upstream context tracing at existing wm_/plan_ evaluation handoff points, keep plan_ as structure co-owner only, and preserve downstream adoption/social-confidence boundaries",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "First real novali-v4 proposal-learning-loop probe.",
                "wm_ is the primary owner; plan_ is limited to handoff structure only.",
                "adoption_, social_conf_, and self_improve_ ownership remain out of scope.",
            ],
        )
    if name == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the new wm_->plan_ traces are informative enough across seed/context conditions to support the first behavior-changing proposal_learning_loop intervention in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_plan_trace_signal_quality",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_discrimination_clarity",
            },
            mechanism={
                "component": "v4_wm_plan_context_trace_quality_snapshot",
                "old_value": "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "new_value": "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "focus": "measure trace signal quality, seed/context variation, wm-vs-plan distinctness, and readiness for the next behavior-changing proposal_learning_loop branch step",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Designed to evaluate whether the new wm_->plan_ traces are strong enough for the next real proposal_learning_loop intervention.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the first behavior-changing novali-v4 proposal-learning-loop probe using wm-owned context discrimination while keeping plan_ non-owning and preserving downstream ownership boundaries",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_upstream_context_discrimination",
                "secondary_family": "persistence",
                "secondary_metric": "context_candidate_separation_without_downstream_drift",
            },
            mechanism={
                "component": "v4_wm_context_signal_discrimination_probe",
                "old_value": "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "focus": "use validated wm-owned trace features to reshape only the projected candidate score path, keep plan_ non-owning, and preserve adoption/social-confidence boundaries",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "First behavior-changing proposal_learning_loop probe in novali-v4.",
                "wm_ is the only owning lever in this step.",
                "plan_ remains non-owning; adoption_, social_conf_, and self_improve_ remain out of scope.",
            ],
        )
    if name == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="explain why the first wm-only behavior-changing probe produced a real discrimination signal but still failed to beat the baseline pre-gate separation path in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_signal_overlap_headroom_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_branch_next_step_precision",
            },
            mechanism={
                "component": "v4_wm_plan_context_trace_quality_snapshot",
                "old_value": "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "new_value": "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "focus": "diagnose redundancy, baseline-path subsumption, mixing dilution, and seed/context sensitivity before attempting a second wm-only behavior-changing probe",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Explains why the first wm-only behavior-changing probe stayed safe but failed to improve useful pre-gate separation.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the second behavior-changing novali-v4 proposal-learning-loop probe using a narrower residualized wm-owned context signal while keeping plan_ non-owning and preserving downstream ownership boundaries",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_residual_context_discrimination",
                "secondary_family": "persistence",
                "secondary_metric": "distinct_upstream_context_separation_without_downstream_drift",
            },
            mechanism={
                "component": "v4_wm_context_residual_signal_probe",
                "old_value": "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "new_value": "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "focus": "use a narrower residualized wm-only subset around context and projection-quality features, remove baseline-dominant positive reuse, keep plan_ non-owning, and preserve adoption/social-confidence boundaries",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Second behavior-changing proposal_learning_loop probe in novali-v4.",
                "wm_ is the only owning lever in this step.",
                "plan_ remains non-owning; adoption_, social_conf_, and self_improve_ remain out of scope.",
                "Reduces direct baseline-dominant reuse from pred_gain_sign_prob and calibrated_projected.",
            ],
        )
    if name == "memory_summary.v4_wm_context_signal_overlap_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="measure how much useful wm-owned signal is already absorbed by the incumbent baseline pre-gate path and determine whether any distinct headroom remains before another wm-only behavior-changing step in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_baseline_overlap_headroom_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "upstream_context_branch_next_step_precision",
            },
            mechanism={
                "component": "v4_wm_context_signal_overlap_snapshot",
                "old_value": "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "new_value": "memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "focus": "quantify baseline absorption, residual distinct headroom, and whether the next move should be hybrid-boundary characterization or a pause of the pure wm-only line",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Measures how much useful wm-owned signal is already carried by baseline pre-gate.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define a viable hybrid boundary between useful wm-owned signal and the incumbent baseline pre-gate path before any wm/baseline redesign probe in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "wm_baseline_hybrid_boundary_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "proposal_learning_loop_next_step_precision",
            },
            mechanism={
                "component": "v4_wm_baseline_hybrid_boundary_snapshot",
                "old_value": "memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "new_value": "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "focus": "separate boundary-kept overlap from destructive duplication and over-residualization so the next step can test a boundary-aware hybrid redesign instead of another pure wm-only probe",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Defines the wm/baseline hybrid boundary before any hybrid redesign probe.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the first behavior-changing hybrid wm/baseline novali-v4 proposal-learning-loop probe using baseline-owned ranking carriers with wm-owned context-conditioned modulation while keeping plan_ non-owning and preserving downstream ownership boundaries",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "hybrid_wm_boundary_context_separation",
                "secondary_family": "persistence",
                "secondary_metric": "useful_upstream_separation_without_destructive_absorption",
            },
            mechanism={
                "component": "v4_wm_baseline_hybrid_boundary_probe",
                "old_value": "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "focus": "keep baseline-owned ranking carriers in place, add wm-owned context-conditioned modulation only, avoid duplicate positive reuse of baseline-dominant features, and preserve plan_ as a non-owning handoff layer",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "First hybrid wm/baseline behavior-changing proposal_learning_loop probe in novali-v4.",
                "Baseline keeps ranking carriers; wm contributes context-conditioned modulation only.",
                "plan_ remains non-owning; adoption_, social_conf_, and self_improve_ remain out of scope.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the next behavior-changing novali-v4 hybrid wm/baseline probe by keeping the successful hybrid boundary intact but scoping its application toward the strongest supported context slices while damping weak low-context high-risk rows and preserving plan_ as non-owning",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "context_scoped_hybrid_upstream_separation",
                "secondary_family": "persistence",
                "secondary_metric": "supported_slice_gain_without_weak_slice_harm",
            },
            mechanism={
                "component": "v4_wm_hybrid_context_scoped_probe",
                "old_value": "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "new_value": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "focus": "keep baseline-owned ranking carriers and the successful hybrid boundary design, but scope the wm modulation toward high_context_low_risk rows while remaining cautious in low_context_high_risk rows",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Context-scoped hybrid wm/baseline behavior-changing probe in novali-v4.",
                "Emphasizes high_context_low_risk slices and damps low_context_high_risk slices.",
                "plan_ remains non-owning; adoption_, social_conf_, and self_improve_ remain out of scope.",
            ],
        )
    if name == "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the next behavior-changing novali-v4 scoped-hybrid stabilization probe by preserving the current hybrid boundary and targeted context scope while improving weak-seed consistency without widening ownership",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_hybrid_consistency_stabilization",
                "secondary_family": "persistence",
                "secondary_metric": "weak_seed_correction_without_weak_slice_activation",
            },
            mechanism={
                "component": "v4_wm_hybrid_context_stabilization_probe",
                "old_value": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "new_value": "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "focus": "preserve the supported-slice hybrid boundary, keep low_context_high_risk protected, and stabilize weaker seeds through small upstream scope-multiplier adjustments only",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Scoped-hybrid stabilization probe in novali-v4.",
                "Keeps the current hybrid boundary and context scope intact while targeting weak-seed consistency.",
                "plan_ remains non-owning; adoption_, social_conf_, and self_improve_ remain out of scope.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="map exactly where the successful hybrid wm/baseline boundary is helping before deciding whether to broaden it or keep it context-scoped in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "hybrid_effect_localization_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "proposal_learning_loop_next_step_scope_precision",
            },
            mechanism={
                "component": "v4_wm_hybrid_probe_effect_snapshot",
                "old_value": "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "new_value": "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
                "focus": "localize the hybrid benefit by row, seed, and context slice so the next proposal-learning-loop move can be broader, stabilized, or context-scoped for the right reason",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Maps where the hybrid wm/baseline boundary helps and where it does not.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decompose exactly how much of the scoped hybrid wm/baseline win comes from the base hybrid boundary, the scope multipliers, and their interaction before broadening or stabilizing the branch",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_hybrid_effect_decomposition_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "next_step_scope_vs_broadening_precision",
            },
            mechanism={
                "component": "v4_wm_hybrid_context_scope_effect_snapshot",
                "old_value": "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "new_value": "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "focus": "separate the base hybrid-boundary contribution from the extra context-scope contribution and classify whether the effect should be broadened, stabilized, or kept narrowly targeted",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Measures how much of the scoped hybrid win comes from the boundary, the scope multipliers, and their interaction.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="test whether the narrowly targeted scoped-hybrid gain is stable enough across seeds and context slices to build on or whether it remains too uneven",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_hybrid_stability_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "weak_region_risk_resolution",
            },
            mechanism={
                "component": "v4_wm_hybrid_context_scope_stability_snapshot",
                "old_value": "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "new_value": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
                "focus": "classify seed stability, slice stability, and especially seed-2 weakness so the next move can be stabilization, continued narrow targeting, another diagnostic, or pause",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Resolves whether the scoped-hybrid gain is stable narrow targeting, fragile local improvement, or only a promising diagnostic signal.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="determine whether the scoped-hybrid stabilization layer adds real repeatable value beyond the current scoped-hybrid probe or only small metric drift",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_vs_stabilized_repeatability_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "seed_2_correction_significance_resolution",
            },
            mechanism={
                "component": "v4_wm_hybrid_context_scope_stability_snapshot",
                "old_value": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
                "new_value": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
                "focus": "compare the scoped-hybrid and stabilization artifacts directly, distinguish repeatable improvement from drift, and decide which narrow configuration should remain the working baseline",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Compares the scoped-hybrid and stabilization probes directly to decide whether stabilization adds real repeatable value.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="formalize the current scoped-hybrid probe as the working narrow baseline and define the exact criteria a future challenger must beat to count as real improvement",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_hybrid_working_baseline_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "future_probe_improvement_standardization",
            },
            mechanism={
                "component": "v4_wm_hybrid_scoped_working_baseline_snapshot",
                "old_value": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
                "new_value": "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
                "focus": "codify the scoped-hybrid configuration as the narrow working baseline, record acceptable weak regions, and define what future improvement must look like to count as more than drift",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Formalizes proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1 as the current narrow working baseline if the evidence supports it.",
                "Keeps plan_ non-owning unless the diagnostic proves otherwise.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="formalize a clean branch pause around the current scoped-hybrid working baseline, including what is held fixed, what can reopen the branch, and what next steps are explicitly closed",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "scoped_hybrid_branch_pause_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "reopen_trigger_and_invalid_step_guarding",
            },
            mechanism={
                "component": "v4_wm_hybrid_branch_pause_snapshot",
                "old_value": "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
                "new_value": "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1",
                "focus": "hold the current scoped-hybrid probe fixed as the narrow baseline, codify pause conditions, define reopen triggers, and explicitly close low-yield follow-on churn",
            },
            memory_dependencies=[
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic snapshot only.",
                "Formalizes paused-with-baseline-held status for the current scoped-hybrid branch.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_substrate_v1_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize Governance Substrate v1 as the governed self-structure foundation for novali-v4 while the current wm-hybrid branch remains paused-with-baseline-held",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governance_substrate_foundation_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "phase_1_gatekept_autonomy_enforcement_readiness",
            },
            mechanism={
                "component": "governance_substrate_v1",
                "old_value": "branch_pause_only_governance",
                "new_value": "durable_governance_substrate_v1",
                "focus": "materialize immutable-core policy, directive and bucket state, hybrid self-structure registry, branch registry, admissibility gate, and governed skill subsystem without changing live behavior",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic substrate implementation only.",
                "Writes durable governance artifacts into novali-v4/data without reopening novali-v3 or changing branch behavior.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_memory_authority_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize a canonical governance-memory authority surface so future agents can reconstruct current novali-v4 posture from persisted artifacts rather than runtime loop code",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governance_memory_authority_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "binding_decision_recoverability",
            },
            mechanism={
                "component": "governance_memory_authority_v1",
                "old_value": "fragmented_governance_memory_surface",
                "new_value": "canonical_governance_memory_authority_v1",
                "focus": "roll up directive, bucket, branch, self-structure, held baseline, reopen eligibility, capability boundaries, and selector-frontier conclusions into one stable authority file without changing behavior",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_hold_position_closeout_v1",
                "diagnostic_memory.memory_summary.final_selection_false_safe_margin_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Architecture-and-memory consolidation only.",
                "Makes persisted governance memory the primary control surface without reopening routing, thresholds, or behavior-changing lines.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_screening_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the latest queued blocked-governed action against the canonical reopen bar so reopen handling becomes explicit, queryable, and non-authoritative",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governance_reopen_screening_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "reopen_bar_reproducibility",
            },
            mechanism={
                "component": "governance_reopen_screening_v1",
                "old_value": "queued_reopen_intake_without_explicit_screening_result",
                "new_value": "explicit_non_authoritative_reopen_screening_snapshot_v1",
                "focus": "screen queued reopen intake against canonical authority, branch triggers, selector-frontier conclusions, and recent evidence without changing execution behavior or authority",
            },
            memory_dependencies=[
                "intervention_analytics",
                "proposal_recommendations_latest",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "diagnostic_memory.memory_summary.final_selection_false_safe_margin_snapshot_v1",
                "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
                "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1",
                "governance_reopen_intake_ledger",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Governance workflow hardening only.",
                "Turns queued blocked actions into explicit screened results without changing authority, routing, or execution behavior.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_review_submission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn a screened_reopen_candidate into an explicit non-authoritative governance-review submission packet so review handoff becomes queryable and promotion remains explicit",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governance_review_handoff_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "reopen_review_provenance",
            },
            mechanism={
                "component": "governance_reopen_review_submission_v1",
                "old_value": "screened_candidate_without_explicit_review_submission_packet",
                "new_value": "explicit_non_authoritative_governance_review_submission_packet_v1",
                "focus": "submit only screened reopen candidates into a governed review packet with provenance, rollback trace, and explicit promotion handoff rules without changing authority or execution behavior",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_screening_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "governance_reopen_screening_ledger",
                "governance_reopen_intake_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Governance review handoff only.",
                "Prevents unscreened or screened-out requests from entering governance review while keeping submission non-authoritative until separate review outcome and promotion.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_review_outcome_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide a submitted governance-review packet explicitly so review rejection, promotion-path approval, and non-authoritative state remain queryable before the existing promotion gate",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governance_review_outcome_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "promotion_handoff_provenance",
            },
            mechanism={
                "component": "governance_reopen_review_outcome_v1",
                "old_value": "submitted_review_packet_without_explicit_review_decision_record",
                "new_value": "explicit_non_authoritative_governance_review_outcome_snapshot_v1",
                "focus": "turn only submitted governance-review packets into explicit rejected or promotion-path-approved outcomes with provenance and promotion handoff metadata, without mutating canonical authority",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_review_submission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_screening_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "governance_reopen_review_ledger",
                "governance_reopen_screening_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Governance review outcome only.",
                "Prevents unscreened, screened-out, or unsubmitted requests from receiving approved review outcomes and keeps authority mutation inside the separate promotion gate.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn a governance-review-approved outcome into an explicit non-authoritative promotion handoff so promotion-path readiness becomes queryable before the existing promotion gate executes",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "promotion_handoff_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "promotion_candidate_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_handoff_v1",
                "old_value": "review_approved_outcome_without_explicit_promotion_handoff_record",
                "new_value": "explicit_non_authoritative_promotion_handoff_snapshot_v1",
                "focus": "turn only governance-review-approved outcomes into promotion-pending handoffs with promotion-gate input metadata, provenance, and rollback trace without mutating canonical authority",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_review_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_review_submission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "governance_reopen_review_outcome_ledger",
                "governance_reopen_review_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Promotion handoff only.",
                "Prevents unscreened, screened-out, unsubmitted, or review-rejected requests from entering the promotion path and keeps canonical mutation inside the separate promotion gate.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide a promotion-pending handoff explicitly so promotion under-review, rejection, noop, and applied-authority states become queryable without creating a second authority path",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "promotion_outcome_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "authority_before_after_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_outcome_v1",
                "old_value": "promotion_pending_handoff_without_explicit_gate_decision_record",
                "new_value": "explicit_governed_promotion_outcome_snapshot_v1",
                "focus": "turn only promotion-pending approved handoffs into explicit under-review, rejected, noop, or applied promotion outcomes with gate checks and authority before/after references",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_review_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "governance_reopen_promotion_handoff_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Promotion outcome only.",
                "Prevents malformed, repeated, or not-yet-approved handoffs from producing fresh binding authority incorrectly and keeps the existing promotion gate as the sole canonical mutation path.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="verify that a promotion-applied authority mutation propagated cleanly across canonical authority, resolver state, self-structure mirror, and execution-governance reads",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "post_promotion_reconciliation_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "rollback_ready_reference_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_v1",
                "old_value": "promotion_applied_without_explicit_post_apply_convergence_record",
                "new_value": "explicit_governed_promotion_reconciliation_snapshot_v1",
                "focus": "turn only promotion_applied_as_binding_authority outcomes into explicit reconciliation_verified or reconciliation_mismatch_detected records with propagation checks and rollback-ready metadata",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_memory_authority_snapshot_v1",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Promotion reconciliation only.",
                "Prevents post-apply propagation from being assumed silently and keeps rollback or repair outside this observational layer.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize DirectiveSpec Initialization Flow v1 as the governed partial-intake, clarification, validation, and activation path while the current wm-hybrid branch remains paused-with-baseline-held",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "directive_initialization_governance_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "validated_directive_activation_guard_readiness",
            },
            mechanism={
                "component": "directive_spec_initialization_flow_v1",
                "old_value": "static_directive_schema_only",
                "new_value": "durable_directive_init_state_machine_v1",
                "focus": "support partial directive intake, generate clarification requirements, normalize a full DirectiveSpec, validate against governance constraints, and block activation until validation succeeds",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic governance flow implementation only.",
                "Writes durable directive-init state and history into novali-v4/data without reopening novali-v3 or changing branch behavior.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn only reconciliation mismatches into explicit remediation-or-rollback review candidates without invoking rollback or repair automatically",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "reconciliation_mismatch_escalation_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "rollback_review_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_escalation_v1",
                "old_value": "reconciliation_mismatch_without_explicit_escalation_candidate",
                "new_value": "explicit_reconciliation_mismatch_escalation_candidate_v1",
                "focus": "turn only reconciliation_mismatch_detected cases into explicit remediation_or_rollback_review_candidate artifacts with mismatch surfaces and rollback-ready reference metadata",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Escalation candidate only.",
                "Prevents reconciliation mismatches from becoming silent dead ends while still forbidding automatic rollback or repair.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn only remediation-or-rollback review candidates into explicit remediation-review submission packets without invoking rollback or repair automatically",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "remediation_review_submission_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "rollback_review_packet_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_remediation_review_submission_v1",
                "old_value": "reconciliation_escalation_without_explicit_remediation_review_packet",
                "new_value": "explicit_remediation_review_submission_packet_v1",
                "focus": "turn only remediation_or_rollback_review_candidate cases into explicit submitted_for_remediation_review packets with mismatch evidence, rollback-ready reference metadata, and requested remediation scope",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "governance_reopen_promotion_reconciliation_escalation_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Remediation-review submission only.",
                "Prevents mismatch escalations from becoming implicit repair triggers while preserving explicit review-packet provenance.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn only submitted remediation-review packets into explicit remediation-review outcomes without invoking rollback or repair automatically",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "remediation_review_outcome_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "rollback_or_repair_handoff_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_remediation_review_outcome_v1",
                "old_value": "submitted_remediation_review_without_explicit_decision_artifact",
                "new_value": "explicit_remediation_review_outcome_artifact_v1",
                "focus": "turn only submitted_for_remediation_review packets into explicit remediation_review_rejected or remediation_review_approved_for_existing_rollback_or_repair_path outcomes with non-mutating follow-on handoff metadata",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "governance_reopen_remediation_review_ledger",
                "governance_reopen_promotion_reconciliation_escalation_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Remediation-review outcome only.",
                "Prevents remediation-review submissions from becoming implicit rollback or repair triggers while preserving explicit decision provenance.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn only remediation-review-approved mismatch cases into explicit rollback-or-repair handoff packets without invoking any existing follow-on path automatically",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "rollback_or_repair_handoff_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "existing_path_input_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_v1",
                "old_value": "remediation_review_approval_without_explicit_existing_path_handoff",
                "new_value": "explicit_rollback_or_repair_handoff_packet_v1",
                "focus": "turn only remediation_review_approved_for_existing_rollback_or_repair_path outcomes into explicit rollback_or_repair_handoff_pending packets with existing-path candidate metadata, rollback-ready provenance, and no automatic invocation",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "governance_reopen_remediation_review_outcome_ledger",
                "governance_reopen_remediation_review_ledger",
                "governance_reopen_promotion_reconciliation_escalation_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Rollback-or-repair handoff only.",
                "Prevents approved remediation-review outcomes from becoming implicit rollback or repair triggers while preserving explicit existing-path handoff provenance.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn only approved rollback-or-repair handoff candidates into explicit existing-path outcomes without invoking rollback or repair automatically by default",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "rollback_or_repair_outcome_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "authority_before_after_provenance",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_v1",
                "old_value": "rollback_or_repair_handoff_without_explicit_existing_path_decision_artifact",
                "new_value": "explicit_rollback_or_repair_outcome_artifact_v1",
                "focus": "turn only rollback_or_repair_candidate_under_existing_path packets into explicit under-review, rejected, noop, or applied existing-path outcomes while keeping canonical mutation inside the existing authority-promotion rollback path when explicitly selected",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
                "governance_reopen_rollback_or_repair_handoff_ledger",
                "governance_reopen_remediation_review_outcome_ledger",
                "governance_reopen_remediation_review_ledger",
                "governance_reopen_promotion_reconciliation_escalation_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Rollback-or-repair outcome only.",
                "Prevents explicit handoffs from collapsing into implicit existing-path mutation while preserving a single governed decision surface.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="turn explicit rollback-or-repair outcomes into explicit mismatch-case lifecycle closure states without assuming resolution or creating a second apply path",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "mismatch_case_closure_clarity",
                "secondary_family": "governance_memory",
                "secondary_metric": "follow_on_reconciliation_legibility",
            },
            mechanism={
                "component": "governance_reopen_promotion_reconciliation_mismatch_case_closure_v1",
                "old_value": "rollback_or_repair_outcome_requires_manual_lifecycle_stitching",
                "new_value": "explicit_mismatch_case_closure_artifact_v1",
                "focus": "classify rollback_or_repair outcomes into closed_rejected, pending_follow_on_reconciliation, closed_verified_resolved, or open_requires_further_governance while reusing current authority and reconciliation artifacts as source truth",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
                "governance_reopen_rollback_or_repair_outcome_ledger",
                "governance_reopen_rollback_or_repair_handoff_ledger",
                "governance_reopen_remediation_review_outcome_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_memory_promotion_ledger",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Mismatch-case closure only.",
                "Keeps rejected and justified noop cases explicit, and requires distinct follow-on reconciliation before applied cases can close as verified resolved.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_case_registry_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize governance reopen cases as explicit lifecycle objects with stable case IDs, latest artifact pointers, and portfolio visibility without replaying every ledger manually",
            intended_benefit={
                "target_family": "governance_memory",
                "target_metric": "case_registry_visibility",
                "secondary_family": "recovery",
                "secondary_metric": "mismatch_case_portfolio_legibility",
            },
            mechanism={
                "component": "governance_reopen_case_registry_v1",
                "old_value": "manual_case_stitching_across_many_governance_artifacts",
                "new_value": "explicit_governance_reopen_case_registry_artifact_v1",
                "focus": "index reopen governance cases by stable root reference, latest lifecycle stage, latest artifact pointer, and portfolio visibility while remaining observational only",
            },
            memory_dependencies=[
                "governance_reopen_intake_ledger",
                "governance_reopen_screening_ledger",
                "governance_reopen_review_ledger",
                "governance_reopen_review_outcome_ledger",
                "governance_reopen_promotion_handoff_ledger",
                "governance_reopen_promotion_outcome_ledger",
                "governance_reopen_promotion_reconciliation_ledger",
                "governance_reopen_promotion_reconciliation_escalation_ledger",
                "governance_reopen_remediation_review_ledger",
                "governance_reopen_remediation_review_outcome_ledger",
                "governance_reopen_rollback_or_repair_handoff_ledger",
                "governance_reopen_rollback_or_repair_outcome_ledger",
                "governance_reopen_mismatch_case_closure_ledger",
                "governance_memory_authority_latest",
                "self_structure_state_latest",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Case-registry visibility only.",
                "Separates per-case lifecycle state, latest artifact pointer, and portfolio summary without creating a second authority path or a new decision-making surface.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_case_triage_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize governance reopen portfolio triage as explicit attention classes and next-action recommendations without asking future agents to infer priority from raw registry rows",
            intended_benefit={
                "target_family": "governance_memory",
                "target_metric": "case_triage_visibility",
                "secondary_family": "recovery",
                "secondary_metric": "portfolio_actionability_legibility",
            },
            mechanism={
                "component": "governance_reopen_case_triage_v1",
                "old_value": "manual_attention_inference_from_case_registry_rows",
                "new_value": "explicit_governance_reopen_case_triage_artifact_v1",
                "focus": "classify registry cases into no-action, monitor, review-attention, follow-on reconciliation, or stale/archive candidates while remaining observational only",
            },
            memory_dependencies=[
                "governance_reopen_case_registry_ledger",
                "governance_memory_authority_latest",
                "self_structure_state_latest",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Case-triage visibility only.",
                "Separates lifecycle state, portfolio visibility, triage category, and next-action class without creating a second authority path or decision-making surface.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_reopen_case_queue_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize governance reopen portfolio queue inclusion and ordering as explicit queue classes so future agents do not have to infer surfacing order from raw triage rows",
            intended_benefit={
                "target_family": "governance_memory",
                "target_metric": "case_queue_visibility",
                "secondary_family": "recovery",
                "secondary_metric": "portfolio_execution_readiness_legibility",
            },
            mechanism={
                "component": "governance_reopen_case_queue_v1",
                "old_value": "manual_queue_inference_from_case_triage_rows",
                "new_value": "explicit_governance_reopen_case_queue_artifact_v1",
                "focus": "classify triaged cases into active review, monitor, follow-on reconciliation, closed excluded, or stale excluded queue classes with explicit priority bands and ordering metadata while remaining observational only",
            },
            memory_dependencies=[
                "governance_reopen_case_triage_ledger",
                "governance_memory_authority_latest",
                "self_structure_state_latest",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Case-queue visibility only.",
                "Separates lifecycle state, triage category, queue class, and ordering metadata without creating a second authority path or decision-making surface.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governance_portfolio_brief_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize the current NOVALI posture, case inventory, triage view, queue view, and next governance action into one operator-readable handoff artifact",
            intended_benefit={
                "target_family": "governance_memory",
                "target_metric": "portfolio_brief_legibility",
                "secondary_family": "recovery",
                "secondary_metric": "operator_handoff_readiness",
            },
            mechanism={
                "component": "governance_portfolio_brief_v1",
                "old_value": "manual_project_status_reconstruction_from_many_governance_artifacts",
                "new_value": "explicit_governance_portfolio_brief_artifact_v1",
                "focus": "separate canonical posture facts, observational portfolio summaries, and non-binding next-action commentary in one governed handoff snapshot while remaining observational only",
            },
            memory_dependencies=[
                "governance_memory_authority_latest",
                "governance_reopen_case_registry_ledger",
                "governance_reopen_case_triage_ledger",
                "governance_reopen_case_queue_ledger",
                "self_structure_state_latest",
                "intervention_analytics",
                "proposal_recommendations_latest",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Portfolio-brief visibility only.",
                "Separates canonical posture, observational portfolio state, and non-binding next-action commentary without creating a second authority path or decision-making surface.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="materialize Governed Candidate Admission v1 as the governance-owned reopen-candidate screen for the paused wm-hybrid branch before any new challenger can be admitted",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governed_reopen_candidate_screen_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "paused_branch_admission_discipline",
            },
            mechanism={
                "component": "governed_candidate_admission_v1",
                "old_value": "paused_branch_without_governed_candidate_screen",
                "new_value": "paused_branch_governed_candidate_screen_v1",
                "focus": "screen future challengers against directive relevance, governance legality, branch-state compatibility, and held-baseline plausibility before any reopen is allowed",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic governance admission implementation only.",
                "Keeps the paused wm-hybrid branch paused unless a future challenger clears the governed reopen bar.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define Governed Skill Acquisition Flow v1 at governance level before any sandboxed skill trial or behavior-changing skill branch can be admitted in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governed_skill_acquisition_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "skill_subsystem_governance_discipline",
            },
            mechanism={
                "component": "governed_skill_acquisition_v1",
                "old_value": "sample_skill_schema_only",
                "new_value": "durable_governed_skill_acquisition_flow_v1",
                "focus": "define the phase-1 skill lifecycle, valid skill classes, action governance, retention rules, and rollback conditions from existing directive, branch, bucket, and self-structure governance context",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic governance flow implementation only.",
                "Defines the governed skill-acquisition flow before any actual skill-building branch is opened.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen concrete governed skill candidates against the active directive, bucket, branch, trust-boundary, and skill-governance rules before any real skill-building branch can be admitted in novali-v4",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governed_skill_candidate_screen_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "pre_branch_skill_admission_discipline",
            },
            mechanism={
                "component": "governed_skill_candidate_screen_v1",
                "old_value": "skill_flow_definition_without_concrete_candidate_screen",
                "new_value": "concrete_governed_skill_candidate_screen_v1",
                "focus": "screen example candidate skills against directive relevance, trust-boundary, bucket feasibility, branch-state compatibility, skill-class validity, duplication risk, and bounded evidence before any skill branch can be opened",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic governance gate implementation only.",
                "Screens concrete skill candidates without opening a behavior-changing skill branch.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_trial_admission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the strongest sandbox-first governed skill candidate can be admitted into a tightly bounded governed trial without opening a real skill branch",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "governed_skill_trial_admission_clarity",
                "secondary_family": "persistence",
                "secondary_metric": "pre_branch_skill_trial_discipline",
            },
            mechanism={
                "component": "governed_skill_trial_admission_v1",
                "old_value": "sandbox_candidate_screen_only",
                "new_value": "explicit_governed_skill_trial_admission_gate_v1",
                "focus": "decide whether the best sandbox-first candidate is admissible for a bounded governed trial, remains diagnostic-only, or stays blocked while the paused wm-hybrid branch remains paused",
            },
            memory_dependencies=[
                "intervention_analytics",
                "intervention_ledger",
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Diagnostic governance gate implementation only.",
                "Evaluates trial admissibility for the best sandbox-first candidate without opening a behavior-changing skill branch.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the first bounded governed skill execution in novali-v4 by executing the admitted Local trace parser trial inside the approved sandbox envelope while keeping the wm-hybrid branch paused",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_governed_skill_execution_utility",
                "secondary_family": "recovery",
                "secondary_metric": "governed_local_trace_observability_without_branch_reopen",
            },
            mechanism={
                "component": "v4_governed_skill_local_trace_parser_trial",
                "old_value": "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "focus": "execute the admitted local trace parser only as a sandboxed, shadow-only, governance-owned skill trial that reads trusted local logs and diagnostic artifacts without mutating branch state or promoting retention",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "First bounded governed skill execution in novali-v4.",
                "Runs only inside the admitted sandbox envelope: local log parsing, trusted diagnostic-memory reads, shadow-only evidence collection.",
                "No retained promotion, no branch-state mutation, no plan_ ownership change, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the first real governed capability invocation by using the admitted Trusted diagnostic bundle summary request strictly inside its approved diagnostic-only invocation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_capability_use_execution_utility",
                "secondary_family": "recovery",
                "secondary_metric": "governed_capability_reuse_without_reopen",
            },
            mechanism={
                "component": "v4_governed_capability_use_trusted_diagnostic_bundle_invocation",
                "old_value": "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "focus": "invoke the held local trace parser for trusted local diagnostic bundle summarization only, with full invocation accounting and no capability development or branch reopen",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "First real governed capability invocation in novali-v4.",
                "Runs only inside the admitted diagnostic-only invocation envelope: trusted local shadow-log bundle summarization, trusted governance-context reads, and bounded shadow-only reporting.",
                "No capability modification, no branch-state mutation, no retained promotion, no plan_ ownership change, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the first admitted direct governed work item by running a bounded governance-state coherence audit refresh inside the approved direct-work envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_direct_work_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "governance_state_coherence_observability",
            },
            mechanism={
                "component": "v4_governed_directive_work_governance_state_coherence_audit_refresh",
                "old_value": "memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "focus": "execute bounded shadow-only direct work across trusted local governance artifacts while keeping direct work separate from capability use, paused-line reopen, and new-skill creation",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "First direct governed work execution in novali-v4.",
                "Runs only inside the admitted direct-work envelope: trusted local governance artifacts, bounded governance-state coherence audit, and shadow-only reporting.",
                "No capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the bounded local trace parser trial evidence and decide whether the skill should remain sandbox-only, become admissible for provisional handling, or stop short of escalation",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_trial_evidence_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "governed_escalation_readiness_without_branch_reopen",
            },
            mechanism={
                "component": "v4_governed_skill_trial_evidence_review",
                "old_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "new_value": "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "focus": "review bounded trial evidence quality, envelope compliance, directive fit, duplication risk, and escalation readiness before any move toward provisional handling",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Does not promote retention and does not mutate branch state.",
                "Keeps plan_ non-owning and routing deferred while deciding whether provisional handling is justified.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the local trace parser skill should be admitted into governance-owned provisional handling with an explicit provisional envelope, evidence obligations, rollback triggers, and retained-promotion prerequisites while keeping the wm-hybrid branch paused",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_admission_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_skill_escalation_without_branch_reopen",
            },
            mechanism={
                "component": "v4_governed_skill_provisional_admission_review",
                "old_value": "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "new_value": "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "focus": "decide whether the bounded local trace parser should move into provisional handling under explicit governance-owned constraints while still blocking retained promotion and branch-state mutation",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines the exact provisional envelope, evidence obligations, rollback triggers, and retained-promotion prerequisites.",
                "Does not promote retention, does not mutate branch state, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run the admitted local trace parser inside the approved provisional envelope to verify continued provisional stability, usefulness, and governance compliance without drifting toward retained promotion or branch reopen",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_execution_stability",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_local_trace_utility_under_provisional_handling",
            },
            mechanism={
                "component": "v4_governed_skill_local_trace_parser_provisional_probe",
                "old_value": "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "focus": "execute the admitted local trace parser as a bounded provisional-handling run that rechecks evidence obligations, envelope compliance, duplication risk, directive relevance, and rollback/deprecation trigger status while keeping retained promotion blocked",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Bounded governed provisional probe only.",
                "Runs strictly inside the approved provisional envelope: local trusted parsing, shadow-only evidence, bounded writes, no branch-state mutation, no retained promotion.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the provisional evidence trend for the admitted local trace parser skill and decide whether continued provisional handling remains worthwhile, stable, and clearly below the retained-promotion threshold",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_evidence_trend_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "governed_capability_growth_alignment",
            },
            mechanism={
                "component": "v4_governed_skill_provisional_evidence_review",
                "old_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "new_value": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
                "focus": "compare bounded trial evidence with provisional-run evidence, classify the trend, check ongoing obligation and envelope compliance, and decide whether the line remains a good governed-skill-growth exemplar while still blocking retained promotion",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Determines whether provisional handling remains justified and whether the line is accumulating meaningful governed capability rather than safe local churn.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review whether repeated flat provisional stability for the admitted local trace parser is still accumulating enough structural value to justify continued provisional handling or has reached a plateau",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_plateau_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "governed_capability_growth_signal_quality",
            },
            mechanism={
                "component": "v4_governed_skill_provisional_evidence_review_v2",
                "old_value": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
                "new_value": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
                "focus": "compare trial, provisional probe v1, and provisional probe v2 together, classify whether the line is strengthening, flat, weakening, or plateauing-low-growth, and decide whether another same-shape provisional pass is justified",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Determines whether repeated provisional flatness is still structurally useful or has plateaued enough to pause pending a new idea.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="formalize a pause on further same-shape provisional reruns for the local trace parser while preserving it as a governed provisional capability",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_pause_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_capability_hold_governance_quality",
            },
            mechanism={
                "component": "v4_governed_skill_provisional_pause_snapshot",
                "old_value": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
                "new_value": "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "focus": "hold the local trace parser as a governed provisional capability, stop repeated same-shape reruns, and define bounded reopen conditions and continued obligations",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Formalizes a held provisional capability state and explicitly pauses identical reruns until a new bounded use-case or materially strengthening idea appears.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_capability_use_policy_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define the governance-owned policy layer for invoking held capabilities in service of the active directive without reopening paused capability lines or forcing unnecessary new-skill work",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_capability_use_policy_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "governed_capability_reuse_alignment",
            },
            mechanism={
                "component": "v4_governed_capability_use_policy_snapshot",
                "old_value": "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "new_value": "memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "focus": "separate capability use from capability acquisition, define invocation classes and accounting, and keep paused capability lines paused unless a separate reopen gate clears them",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines when held governed capabilities may be directly invoked, when a paused line must stay paused, and when reopen or new-skill screening is required instead of direct use.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen concrete capability-invocation requests against Governed Capability-Use Policy v1 so held capabilities can be reused under governance without reopening paused development lines",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_capability_use_candidate_screen_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "held_capability_reuse_decision_quality",
            },
            mechanism={
                "component": "v4_governed_capability_use_candidate_screen_snapshot",
                "old_value": "memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "new_value": "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "focus": "classify concrete invocation requests as direct use, gated use, forbidden use, reopen-required, or new-skill-required while keeping paused capability lines paused",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens concrete held-capability invocation requests without reopening paused development lines or opening a new behavior-changing branch.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the best screened direct-use request can be admitted for actual governed capability use under an explicit invocation envelope without reopening paused development",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_capability_use_invocation_admission_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "held_capability_invocation_safety_alignment",
            },
            mechanism={
                "component": "v4_governed_capability_use_invocation_admission_snapshot",
                "old_value": "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "new_value": "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "focus": "admit the best direct-use request only if it stays inside the held capability envelope, preserves accounting and rollback review, and keeps development paused",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits direct use of a held capability only under an explicit bounded invocation envelope and keeps paused development lines paused.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_capability_use_evidence_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the first real governed capability invocation to determine whether the use path is operationally meaningful, sufficiently governed, and ready to support directive-work selection without reopening development",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_capability_use_operational_meaningfulness",
                "secondary_family": "recovery",
                "secondary_metric": "directive_work_selection_readiness_clarity",
            },
            mechanism={
                "component": "v4_governed_capability_use_evidence_snapshot",
                "old_value": "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "new_value": "memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "focus": "review operational usefulness, governance sufficiency, control-envelope adequacy, and future posture for the first real governed capability-use path",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Evaluates whether the first real held-capability invocation was operationally meaningful and sufficiently governed to preserve as a future use path.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define the governance-owned policy layer for selecting the next directive-relevant work item under current directive, bucket, branch, and held-capability state",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_directive_work_selection_policy_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "directive_work_path_selection_alignment",
            },
            mechanism={
                "component": "v4_governed_directive_work_selection_policy_snapshot",
                "old_value": "memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "new_value": "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "focus": "separate directive-work selection from capability use and acquisition, define selection classes and accounting, and keep use, reopen, new-skill, and defer paths explicit",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines how directive-valid work should be chosen among direct execution, held-capability use, paused-line reopen, new-skill acquisition, or defer or block outcomes.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen concrete directive-work candidates through Governed Directive-Work Selection Policy v1 so the best current next work item can be identified without blurring direct work, held-capability use, reopen, new-skill, review, or defer paths",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_directive_work_candidate_screen_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "best_next_work_item_selection_quality",
            },
            mechanism={
                "component": "v4_governed_directive_work_candidate_screen_snapshot",
                "old_value": "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "new_value": "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "focus": "classify concrete directive-work items through the work-selection policy and identify the strongest current next-step candidate and its correct next gate",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens concrete directive-work candidates and identifies the strongest current next work item while keeping direct-use, capability-use, reopen, new-skill, review, and defer paths separate.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_directive_work_admission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the best screened directive-work candidate can be admitted for actual governed direct work under the current directive, bucket, branch, and governance state",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_directive_work_admission_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "first_direct_governed_work_path_readiness",
            },
            mechanism={
                "component": "v4_governed_directive_work_admission_snapshot",
                "old_value": "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "new_value": "memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "focus": "define the exact direct-work envelope, accounting, and active review or rollback posture for the strongest screened directive-work candidate while keeping direct work separate from capability use, reopen, and new-skill paths",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Evaluates whether the strongest current directive-work candidate can be admitted for bounded shadow-only direct work.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_direct_work_evidence_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the first real direct governed work execution to determine whether the path is operationally meaningful, sufficiently governed, and ready to support a broader governed work loop",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_direct_work_operational_stability",
                "secondary_family": "recovery",
                "secondary_metric": "governed_work_loop_readiness",
            },
            mechanism={
                "component": "v4_governed_direct_work_evidence_snapshot",
                "old_value": "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "new_value": "memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "focus": "evaluate whether the first direct governed work execution was operationally meaningful, governance-sufficient, and strong enough to preserve as a bounded execution path while determining readiness for a broader governed work loop",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Reviews the first real direct governed work execution for operational value, governance sufficiency, envelope compliance, and broader governed-work-loop readiness.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_policy_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define the governance-owned policy layer for how bounded directive-relevant work continues, pauses, diverts, or halts over time after the first reviewed direct governed work execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_control_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_work_loop_continuation_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_policy_snapshot",
                "old_value": "memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "new_value": "memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "focus": "define loop stages, continuation and halt logic, diversion paths, accounting requirements, and guardrails for bounded governance-owned work sequencing",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines the work-loop control layer above one-off direct work, while keeping direct-work, capability-use, reopen, and new-skill paths explicitly separated.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen concrete governed work-loop continuation candidates through the new work-loop policy to identify the strongest bounded next path after the first successful direct governed work execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_candidate_selection_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "first_loop_continuation_admission_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot",
                "old_value": "memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "focus": "screen concrete next-loop-step candidates, classify them into continuation, capability-use diversion, review, pause, reopen, new-skill, or halt paths, and identify the best current next continuation candidate",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens concrete next-loop-step candidates through the work-loop policy while keeping direct-work, capability-use, review, pause, reopen, new-skill, and halt paths explicitly separated.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the next round of governed work-loop candidates under the formalized narrow work-loop posture to identify the strongest distinct bounded next step without slipping into repetition or unsupported broadening",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "narrow_work_loop_next_step_selection_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "second_loop_continuation_admission_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v2",
                "old_value": "memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "focus": "screen a fresh next round of loop-step candidates through both the work-loop policy and the narrow posture, reject repetition and silent broadening, and identify one strongest bounded next step",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens a fresh next round of loop-step candidates under the narrow posture while keeping continuation, capability-use diversion, review, pause, reopen, new-skill, and halt paths explicitly separated.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the post-evidence-v2 work-loop frontier under the closed narrow posture to determine whether a fourth bounded continuation candidate still exists without widening execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_continuation_frontier_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "narrow_posture_hold_vs_next_candidate_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v3",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "focus": "screen whether any materially distinct, execution-adjacent, structurally useful fourth bounded continuation candidate remains after the current three-step chain and evidence v2",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens the next candidate frontier after the three-step governed chain and evidence v2 while keeping the posture-review gate closed and routing deferred.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the post-evidence-v3 work-loop frontier under the closed narrow posture to determine whether any further bounded continuation candidate still exists without widening execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_continuation_frontier_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "hold_vs_next_candidate_decision_quality_after_four_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v4",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "focus": "screen whether any materially distinct, execution-adjacent, structurally useful next bounded continuation candidate remains after the strengthened four-step chain and evidence v3",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens the next candidate frontier after the strengthened four-step governed chain and evidence v3 while keeping the posture-review gate closed and routing deferred.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the post-evidence-v4 work-loop frontier under the closed narrow posture to determine whether any further bounded continuation candidate still exists without widening execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_continuation_frontier_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "hold_vs_next_candidate_decision_quality_after_five_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v5",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "focus": "screen whether any materially distinct, execution-adjacent, structurally useful next bounded continuation candidate remains after the strengthened five-step chain and evidence v4",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens the next candidate frontier after the strengthened five-step governed chain and evidence v4 while keeping the posture-review gate closed and routing deferred.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the post-evidence-v5 work-loop frontier under the closed narrow posture to determine whether any further bounded continuation candidate still exists without widening execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_continuation_frontier_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "hold_vs_next_candidate_decision_quality_after_six_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v6",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "focus": "screen whether any materially distinct, execution-adjacent, structurally useful next bounded continuation candidate remains after the strengthened six-step chain and evidence v5",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens the next candidate frontier after the strengthened six-step governed chain and evidence v5 while keeping the posture-review gate closed and routing deferred.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="screen the post-evidence-v6 work-loop frontier under the closed narrow posture to determine whether any further bounded continuation candidate still exists without widening execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "bounded_continuation_frontier_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "hold_vs_next_candidate_decision_quality_after_seven_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_candidate_screen_snapshot_v7",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "new_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "focus": "screen whether any materially distinct, execution-adjacent, structurally useful next bounded continuation candidate remains after the strengthened seven-step chain and evidence v6 while explicitly checking diminishing-return and circularity pressure",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Screens the next candidate frontier after the strengthened seven-step governed chain and evidence v6 while keeping the posture-review gate closed and routing deferred.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the best screened work-loop continuation candidate can be admitted for a first bounded governed continuation step under the current directive, bucket, branch, and governance state",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_loop_continuation_execution_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "focus": "admit only a distinct bounded next loop step with an explicit continuation envelope, accounting burden, and trigger posture while keeping pause, capability-use, reopen, new-skill, and halt paths separate",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only a first bounded governed work-loop continuation candidate and preserves explicit separation among continuation, pause, capability-use diversion, review, reopen, new-skill, and halt paths.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the newly selected best bounded loop-step candidate can be admitted for governed work-loop continuation under the current narrow posture",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v2_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "second_bounded_loop_execution_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v2",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "focus": "admit only the selected next bounded loop step under the narrow posture, with explicit distinctness checks, continuation envelope, accounting burden, and trigger posture",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only the selected next bounded loop step under the narrow posture while keeping repetition, capability-use, reopen, new-skill, review, and halt paths explicitly separate.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="evaluate whether the single surviving frontier-containment candidate can be admitted as a future bounded governed work-loop continuation under the current narrow posture",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v3_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "frontier_containment_execution_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v3",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "focus": "admit only the single surviving frontier-containment candidate under the narrow posture while keeping the future posture-review gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits or blocks only the single surviving frontier-containment candidate under the current narrow posture.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide whether the single surviving recommendation-frontier stability candidate is admissible now as a future bounded continuation under the current narrow governed envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v4_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_execution_readiness_after_strengthened_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v4",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "focus": "admit only the single surviving frontier-stability candidate under the narrow posture, with explicit distinctness, evidence-yield, envelope, accounting, and gate-closure checks",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only the single surviving frontier-stability candidate under the narrow posture while keeping repetition, capability-use, reopen, new-skill, review, and halt paths explicitly separate.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide whether the single surviving recommendation-frontier persistence candidate is admissible now as a future bounded continuation under the current narrow governed envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v5_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_execution_readiness_after_five_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v5",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "focus": "admit only the single surviving frontier-persistence candidate under the narrow posture while keeping the future posture-review gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only the single surviving frontier-persistence candidate under the current narrow posture.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide whether the single surviving recommendation-frontier recursion-boundary candidate is admissible now as a future bounded continuation under the current narrow governed envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v6_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_execution_readiness_after_six_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v6",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "focus": "admit only the single surviving frontier-recursion-boundary candidate under the narrow posture while keeping the future posture-review gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only the single surviving frontier-recursion-boundary candidate under the current narrow posture.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="decide whether the single surviving recommendation-frontier circularity-boundary candidate is admissible now as a future bounded continuation under the current narrow governed envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_admission_v7_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_execution_readiness_after_seven_step_chain",
            },
            mechanism={
                "component": "v4_governed_work_loop_continuation_admission_snapshot_v7",
                "old_value": "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "new_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "focus": "admit only the single surviving frontier-circularity candidate under the narrow posture while explicitly failing if diminishing-return, circularity, or posture pressure is too strong",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Admits only the single surviving frontier-circularity-boundary candidate under the current narrow posture.",
                "Explicitly fails if diminishing-return pressure, circularity pressure, or posture pressure is stronger than the screen suggested.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the first real governed work-loop continuation execution to determine whether bounded loop continuation is operationally meaningful, sufficiently governed, and ready to support a broader governed work-loop posture layer",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_evidence_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "broader_work_loop_posture_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "focus": "review operational usefulness, governance sufficiency, envelope compliance, and distinct continuation value after the first governed work-loop continuation execution",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Reviews the first admitted work-loop continuation execution separately from direct work, capability use, paused-line reopen, and new-skill creation.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v2":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="review the direct governed work plus continuation v1 plus continuation v2 chain to determine whether repeated bounded governed-loop advancement is real, whether narrow posture should remain unchanged, and whether a future posture-review gate can be defined without opening it",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_repeated_bounded_success_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "future_posture_review_gate_definition_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v2",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "focus": "consolidate direct governed work plus continuation v1 plus continuation v2 into a bounded governance-owned evidence artifact that keeps posture narrow while defining future posture-review gate criteria only",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines whether repeated bounded governed-loop advancement is now real while keeping posture narrow and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v3":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="consolidate the successful frontier-containment continuation into the governed work-loop chain to determine whether the chain is still accumulating distinct structural evidence under the narrow envelope or approaching diminishing-return governance recursion",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_chain_level_evidence_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_next_step_vs_hold_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v3",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "focus": "consolidate the four-step governed work-loop chain into a bounded governance-owned evidence artifact that tests structural yield versus diminishing-return recursion while keeping posture narrow and the gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Consolidates the four-step governed chain after frontier containment while keeping posture narrow, routing deferred, and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v4":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="consolidate the successful frontier-stability continuation into the governed work-loop chain to determine whether the chain is still accumulating distinct structural evidence under the narrow envelope or approaching diminishing-return governance recursion",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_chain_level_evidence_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_next_step_vs_hold_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v4",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "focus": "consolidate the five-step governed work-loop chain into a bounded governance-owned evidence artifact that tests structural yield versus diminishing-return recursion while keeping posture narrow and the gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Consolidates the five-step governed chain after frontier stability while keeping posture narrow, routing deferred, and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v5":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="consolidate the successful frontier-persistence continuation into the governed work-loop chain to determine whether the chain is still accumulating distinct structural evidence under the narrow envelope or approaching diminishing-return governance recursion",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_chain_level_evidence_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_next_step_vs_hold_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v5",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "focus": "consolidate the six-step governed work-loop chain into a bounded governance-owned evidence artifact that tests structural yield versus diminishing-return recursion while keeping posture narrow and the gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Consolidates the six-step governed chain after frontier persistence while keeping posture narrow, routing deferred, and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v6":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="consolidate the successful frontier-recursion continuation into the governed work-loop chain to determine whether the chain is still accumulating distinct structural evidence under the narrow envelope or nearing diminishing-return governance recursion or circularity",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_chain_level_evidence_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_next_step_vs_hold_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v6",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "focus": "consolidate the seven-step governed work-loop chain into a bounded governance-owned evidence artifact that tests structural yield versus diminishing-return recursion and circularity while keeping posture narrow and the gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Consolidates the seven-step governed chain after frontier recursion while keeping posture narrow, routing deferred, and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v7":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="consolidate the successful frontier-circularity continuation into the governed work-loop chain to determine whether the chain is still accumulating distinct structural evidence under the narrow envelope or nearing diminishing-return governance recursion or circularity",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_chain_level_evidence_quality_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_next_step_vs_hold_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v7",
                "old_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
                "focus": "consolidate the eight-step governed work-loop chain into a bounded governance-owned evidence artifact that tests structural yield versus diminishing-return recursion and circularity while keeping posture narrow and the gate closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Consolidates the eight-step governed chain after frontier circularity while keeping posture narrow, routing deferred, and any future posture-review gate closed.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v8":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="perform a pause-aware governed work-loop evidence review after the frontier-circularity execution to determine whether the loop should remain on hold, stop continuation, or only narrowly re-open future continuation consideration if a concrete fresh trigger later appears",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "pause_aware_governed_work_loop_reentry_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "hold_vs_stop_vs_triggered_reentry_decision_quality",
            },
            mechanism={
                "component": "v4_governed_work_loop_evidence_snapshot_v8",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
                "new_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v8",
                "focus": "review the eight-step governed work-loop chain without extending it by momentum, preserving a hold-by-default posture unless amber concerns improve and a concrete fresh bounded trigger appears",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Performs a pause-aware evidence checkpoint after frontier circularity and defaults to hold posture unless a concrete fresh trigger and amber improvement appear in the local governed evidence.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_hold_position_closeout_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="record a governed work-loop hold-position closeout after the pause-aware v8 review so the line is preserved as meaningful governance memory without permitting automatic continuation",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_hold_position_memory_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "reentry_trigger_and_no_auto_continue_clarity",
            },
            mechanism={
                "component": "v4_governed_work_loop_hold_position_closeout_v1",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v8",
                "new_value": "memory_summary.v4_governed_work_loop_hold_position_closeout_v1",
                "focus": "archive what the governed work-loop line demonstrated, why hold posture is correct now, what re-entry would require, and what remains explicitly closed",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v8",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance closeout only.",
                "Preserves the governed work-loop line as meaningful while explicitly forbidding automatic continuation without fresh evidence.",
                "Does not mutate branch state, does not promote retention, keeps plan_ non-owning, and keeps routing deferred.",
            ],
        )
    if name == "memory_summary.v4_governed_work_loop_posture_snapshot_v1":
        return _base_record(
            proposal_type="memory_summary",
            template_name=name,
            scope="audit_only",
            trigger_reason="define the current broader governed work-loop posture after the first reviewed continuation so NOVALI can progress without silently broadening into unsupported execution",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_posture_clarity",
                "secondary_family": "recovery",
                "secondary_metric": "execution_adjacent_next_step_readiness",
            },
            mechanism={
                "component": "v4_governed_work_loop_posture_snapshot",
                "old_value": "memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "new_value": "memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "focus": "formalize what broader work-loop posture allows now, what remains blocked, what evidence still blocks broader execution, and which next step remains execution-adjacent",
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Diagnostic governance review only.",
                "Defines the current broader governed work-loop posture without widening into unsupported execution.",
                "Keeps direct work, loop continuation, capability use, review, reopen, and new-skill diversion paths explicitly separated.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the first admitted governed work-loop continuation item by running a bounded governance ledger consistency delta audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "governance_ledger_delta_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_ledger_consistency_delta_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "focus": "execute a distinct bounded shadow-only work-loop continuation audit across trusted local governance artifacts while keeping continuation separate from prior direct-work repetition, capability use, paused-line reopen, and new-skill creation",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
                "diagnostic_memory.memory_summary.v4_governed_directive_work_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "First governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted continuation envelope: trusted local governance artifacts, bounded governance-ledger delta audit, and shadow-only reporting.",
                "No capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v2 governed work-loop continuation item by running a bounded recommendation-to-ledger alignment delta audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "second_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_ledger_alignment_delta_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "focus": "execute a second distinct bounded shadow-only work-loop continuation audit across trusted local governance artifacts while keeping continuation separate from prior direct work, prior continuation replay, capability use, paused-line reopen, and new-skill creation",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Second distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v2 continuation envelope: trusted local governance artifacts, bounded recommendation-to-ledger alignment delta audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v3 governed work-loop continuation item by running a bounded recommendation-frontier containment audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "third_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_frontier_containment_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_frontier_containment_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "focus": "execute a third distinct bounded shadow-only work-loop continuation audit across trusted local governance artifacts while testing whether the current recommendation frontier remains contained, distinct, and posture-safe",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Third distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v3 continuation envelope: trusted local governance artifacts, bounded recommendation-frontier containment audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v4 governed work-loop continuation item by running a bounded recommendation-frontier stability delta audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "fourth_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_frontier_stability_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "focus": "execute a bounded shadow-only work-loop continuation audit across trusted local governance artifacts while testing whether the current recommendation frontier remains stable, materially distinct, and posture-safe relative to the prior frontier-containment execution",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Fourth distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v4 continuation envelope: trusted local governance artifacts, bounded recommendation-frontier stability delta audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v5 governed work-loop continuation item by running a bounded recommendation-frontier persistence boundary audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "fifth_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_frontier_persistence_boundary_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "focus": "execute a bounded shadow-only work-loop continuation audit across trusted local governance artifacts while testing whether the current recommendation frontier remains persistence-bounded, materially distinct, and posture-safe relative to the prior frontier-containment and frontier-stability executions",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Fifth distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v5 continuation envelope: trusted local governance artifacts, bounded recommendation-frontier persistence boundary audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v6 governed work-loop continuation item by running a bounded recommendation-frontier recursion boundary audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "sixth_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_frontier_recursion_boundary_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "focus": "execute a bounded shadow-only work-loop continuation audit across trusted local governance artifacts while testing whether the current recommendation frontier remains recursion-bounded, materially distinct, and posture-safe relative to the prior frontier-containment, frontier-stability, and frontier-persistence executions",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Sixth distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v6 continuation envelope: trusted local governance artifacts, bounded recommendation-frontier recursion boundary audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="execute the admitted v7 governed work-loop continuation item by running a bounded recommendation-frontier circularity boundary audit inside the approved continuation envelope",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "seventh_distinct_governed_work_loop_continuation_operational_proof",
                "secondary_family": "recovery",
                "secondary_metric": "recommendation_frontier_circularity_boundary_observability",
            },
            mechanism={
                "component": "v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit",
                "old_value": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "new_value": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
                "focus": "execute a bounded shadow-only work-loop continuation audit across trusted local governance artifacts while testing whether the current recommendation frontier remains circularity-bounded, materially distinct, and posture-safe relative to the prior frontier-containment, frontier-stability, frontier-persistence, and frontier-recursion executions",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_policy_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_posture_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
                "diagnostic_memory.memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
                "diagnostic_memory.memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Seventh distinct governed work-loop continuation execution in novali-v4.",
                "Runs only inside the admitted v7 continuation envelope: trusted local governance artifacts, bounded recommendation-frontier circularity boundary audit, and shadow-only reporting.",
                "No capability use, no capability modification, no paused-capability reopen, no new skill creation, no branch-state mutation, no retained promotion, and routing remains deferred.",
            ],
        )
    if name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2":
        return _base_record(
            proposal_type="proposal_learning_loop",
            template_name=name,
            scope="shadow_only",
            trigger_reason="run one more bounded provisional pass for the admitted local trace parser to determine whether the evidence trend stays stable-flat or begins to strengthen toward later retention-readiness while keeping the wm-hybrid branch paused",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "governed_skill_provisional_execution_trend_signal",
                "secondary_family": "recovery",
                "secondary_metric": "bounded_local_trace_utility_accumulation",
            },
            mechanism={
                "component": "v4_governed_skill_local_trace_parser_provisional_probe_v2",
                "old_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "new_value": "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
                "focus": "execute one more admitted provisional-handling run and compare the resulting evidence against both the original trial and provisional probe v1 while keeping retained promotion blocked",
                "probe_only": True,
            },
            memory_dependencies=[
                "diagnostic_memory.memory_summary.v4_governance_substrate_v1_snapshot",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
                "diagnostic_memory.proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
                "diagnostic_memory.memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
                "intervention_analytics",
                "intervention_ledger",
            ],
            targets_blockers=["persistence_guard", "recovery_guard"],
            notes=[
                "Bounded governed provisional probe only.",
                "Runs strictly inside the approved provisional envelope with local trusted parsing, shadow-only evidence, bounded writes, no branch-state mutation, and no retained promotion.",
                "Keeps plan_ non-owning and routing deferred.",
            ],
        )
    if name == "critic_split.final_selection_false_safe_guardrail_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="test swap-aware final-selection composition after the false-safe margin snapshot showed that residual benchmark-like rows can survive scoring but breach the shared false-safe frontier only when added on top of the incumbent trio",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "final_selection_guardrail_safe_swap_utility",
                "secondary_family": "persistence",
                "secondary_metric": "benchmark_like_capacity_preservation_without_drift",
            },
            mechanism={
                "component": "final_selection_false_safe_guardrail_critic",
                "old_value": "benchmark_like_scoring_preservation_score_v2",
                "new_value": "swap_aware_final_selection_guardrail_score_v1",
                "probe_only": True,
                "comparison_reference": "memory_summary.final_selection_false_safe_margin_snapshot_v1",
                "refined_signal_groups": [
                    "protected_anchor_preservation",
                    "swap_aware_selected_set_composition",
                    "false_safe_guardrail_margin_preservation",
                    "context_robustness_tie_break",
                    "double_swap_rejection_under_fixed_cap",
                ],
                "ranking_mode": "swap_aware_final_selection_guardrail",
                "blocker_sensitive_rules": [
                    "recovery_02 remains the protected anchor for all evaluated trios",
                    "projection-safe envelope remains identical to the scorer-preservation lineage",
                    "no additive promotion is accepted if it exceeds the current false-safe cap",
                    "only swap-aware final-selection composition is evaluated; earlier scoring rescue is untouched",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "diagnostic_memory.memory_summary.final_selection_false_safe_margin_snapshot_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only critic probe focused on final-selection composition, not earlier scoring rescue.",
                "Evaluates incumbent, safe swaps, and double-swap alternatives under the frozen false-safe cap.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "projection-safe envelope remains unchanged",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.safe_trio_incumbent_confirmation_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="confirm whether swap_C should replace the old incumbent safe trio baseline after the final-selection false-safe guardrail probe found a safe trio with the same cap and better benchmark utility",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "safe_trio_incumbent_confirmation",
                "secondary_family": "persistence",
                "secondary_metric": "baseline_composition_stability_under_fixed_cap",
            },
            mechanism={
                "component": "safe_trio_incumbent_confirmation_critic",
                "old_value": "old_safe_trio_baseline",
                "new_value": "swap_c_candidate_incumbent_confirmation_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.final_selection_false_safe_guardrail_probe_v1",
                "refined_signal_groups": [
                    "protected_anchor_confirmation",
                    "incumbent_vs_swap_c_direct_replay",
                    "false_safe_cap_confirmation",
                    "policy_match_delta_confirmation",
                    "context_robustness_confirmation",
                ],
                "ranking_mode": "safe_trio_incumbent_confirmation",
                "blocker_sensitive_rules": [
                    "recovery_02 remains the protected anchor in both compared trios",
                    "comparison stays strictly inside the current safe envelope",
                    "no routing or threshold changes are introduced",
                    "candidate incumbent must not exceed the current false-safe cap",
                    "only old-incumbent vs swap_C confirmation is evaluated",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only confirmation probe.",
                "Determines whether swap_C should replace the old incumbent trio as the working safe baseline.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "projection-safe envelope remains unchanged",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.persistence_balanced_safe_trio_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="test whether any persistence-inclusive safe trio can remain inside the current false-safe cap while becoming competitive enough with swap_C to justify cap-preserving selected-set balancing",
            intended_benefit={
                "target_family": "persistence",
                "target_metric": "cap_preserving_persistence_balanced_viability",
                "secondary_family": "recovery",
                "secondary_metric": "swap_c_competitive_gap_visibility",
            },
            mechanism={
                "component": "persistence_balanced_safe_trio_critic",
                "old_value": "swap_c_safe_trio_baseline",
                "new_value": "persistence_balanced_safe_trio_probe_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "refined_signal_groups": [
                    "protected_anchor_preservation",
                    "persistence_inclusive_safe_trio_comparison",
                    "fixed_false_safe_cap_preservation",
                    "policy_match_gap_to_swap_c",
                    "context_robustness_gap_to_swap_c",
                ],
                "ranking_mode": "persistence_balanced_safe_trio_comparison",
                "blocker_sensitive_rules": [
                    "recovery_02 remains the protected anchor in every evaluated trio",
                    "comparison stays strictly inside the current safe envelope",
                    "no routing or threshold changes are introduced",
                    "all trios must stay within the current false-safe cap to count as viable",
                    "the incumbent baseline is swap_C and is not weakened during the probe",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only persistence-balancing probe.",
                "Compares persistence-inclusive safe trios directly against confirmed swap_C under the frozen cap.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "projection-safe envelope remains unchanged",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.swap_c_incumbent_hardening_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="test whether the confirmed swap_C incumbent remains stable and whether any under-cap incumbent-hardening gain still exists under the flat false-safe frontier",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "swap_c_incumbent_robustness_confirmation",
                "secondary_family": "persistence",
                "secondary_metric": "residual_watch_under_same_cap",
            },
            mechanism={
                "component": "swap_c_incumbent_hardening_critic",
                "old_value": "swap_c_confirmed_structural_incumbent",
                "new_value": "swap_c_incumbent_hardening_probe_v1",
                "probe_only": True,
                "comparison_reference": "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "refined_signal_groups": [
                    "incumbent_direct_replay",
                    "historical_consistency_check",
                    "recovery_case_stability_confirmation",
                    "persistence_residual_watch_under_same_cap",
                    "under_cap_hardening_headroom_detection",
                ],
                "ranking_mode": "swap_c_incumbent_hardening_confirmation",
                "blocker_sensitive_rules": [
                    "swap_C remains the compared incumbent selected set",
                    "no persistence balancing is attempted",
                    "no additive expansion above trio size 3 is attempted",
                    "comparison stays strictly inside the current safe envelope",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1",
                "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1",
                "diagnostic_memory.critic_split.persistence_balanced_safe_trio_probe_v1",
                "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1",
                "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only incumbent-hardening probe.",
                "Confirms whether swap_C remains stable and whether any productive under-cap hardening headroom is still available without reopening balancing.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "projection-safe envelope remains unchanged",
            "frozen benchmark pack semantics unchanged",
        ]
        return record
    if name == "routing_rule.activation_window_probe":
        record = _base_record(
            proposal_type="routing_rule",
            template_name=name,
            scope="shadow_only",
            trigger_reason="probe whether the score-exposed benchmark-like slice can activate safely under a narrow routing window",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "slice_activation_visibility",
                "secondary_family": "calibration",
                "secondary_metric": "slice_projection_safety",
            },
            mechanism={
                "component": "activation_window_probe",
                "reference_variant": "targeted_gain_goal_proj_margin_01",
                "benchmark_variant": "targeted_gain_goal_proj_margin_01",
                "live_policy_variant": "targeted_gain_goal_proj_margin_01",
                "activation_probe_mode": True,
                "requires_manual_variant_definition": True,
                "probe_window_source": "diagnostic_memory.score_reweight.blocker_sensitive_projection_probe",
            },
            memory_dependencies=[
                "diagnostic_memory.score_reweight.blocker_sensitive_projection_probe",
                "diagnostic_memory.routing_rule.candidate_distribution_aware_probe",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard"],
            notes=[
                "Probe only; not a broad live-policy retry.",
                "Only tests the narrow slice exposed by the latest score-probe artifact.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "slice-targeted probe only",
            "benchmark pack semantics unchanged",
        ]
        record["mechanism"].update(
            {
                "probe_only": True,
                "slice_targeting_rules": [
                    "only score-probe top-slice candidates",
                    "only benchmark_adjacent or gain_structure_shifted segments",
                    "exclude projection_far_shifted and stability_sensitive segments",
                    "retain only projection_guard blocker class for activation routing",
                ],
                "comparison_reference": "score_probe_benchmark_like_slice",
            }
        )
        return record
    if name == "routing_rule.slice_targeted_benchmark_sweep_v1":
        record = _base_record(
            proposal_type="routing_rule",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="benchmark-only control retest after critic alignment and selector-reliability probes repair the safe slice without reopening live routing",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "policy_match_rate",
                "secondary_family": "projection",
                "secondary_metric": "false_safe_projection_rate",
            },
            mechanism={
                "component": "slice_targeted_benchmark_sweep",
                "reference_variant": "targeted_gain_goal_proj_margin_01",
                "benchmark_variant": "targeted_gain_goal_proj_margin_01",
                "live_policy_variant": "targeted_gain_goal_proj_margin_01",
                "requires_manual_variant_definition": True,
                "slice_source": "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard"],
            notes=[
                "Benchmark-only routing retest downstream of critic success; not a live default change.",
            ],
        )
        record["evaluation_plan"] = ["static_check", "benchmark"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "benchmark-only slice-targeted override",
            "no default live-policy mutation",
            "no threshold relaxation",
            "benchmark pack semantics unchanged",
        ]
        record["mechanism"].update(
            {
                "probe_only": True,
                "slice_targeting_rules": [
                    "only baseline rejects inside the repaired critic-cleaned safe slice",
                    "only reject-to-provisional overrides",
                    "preserve the current projection-safe envelope",
                    "preserve non-slice benchmark behavior exactly",
                    "do not broaden beyond the selector-reliability repaired slice",
                ],
                "comparison_reference": "critic_split.safe_slice_selection_reliability_probe_v1",
            }
        )
        return record
    if name == "routing_rule.candidate_distribution_aware_probe":
        record = _base_record(
            proposal_type="routing_rule",
            template_name=name,
            scope="shadow_only",
            trigger_reason="probe routing behavior conditioned on live candidate distribution mismatch rather than retrying the same dormant rule",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "live_distribution_gap_visibility",
                "secondary_family": "projection",
                "secondary_metric": "policy_match_rate",
            },
            mechanism={
                "component": "candidate_distribution_aware_probe",
                "reference_variant": "targeted_gain_goal_proj_margin_01",
                "benchmark_variant": "targeted_gain_goal_proj_margin_01",
                "live_policy_variant": "targeted_gain_goal_proj_margin_01",
                "requires_manual_variant_definition": True,
                "probe_window_source": "diagnostic_memory.live_distribution_gap_snapshot",
            },
            memory_dependencies=[
                "diagnostic_memory.live_distribution_gap_snapshot",
                "diagnostic_memory.override_dormancy_snapshot",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Probe only; intended to test live-vs-benchmark distribution mismatch.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "diagnostic artifact only",
            "benchmark pack semantics unchanged",
        ]
        record["mechanism"]["probe_only"] = True
        record["mechanism"]["segment_method"] = "deterministic_bucket_v1"
        record["mechanism"]["comparison_reference"] = "benchmark_undercommit_target_family"
        return record
    if name == "score_reweight.blocker_sensitive_projection_probe":
        record = _base_record(
            proposal_type="score_reweight",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="probe whether projection-sensitive score reweighting helps when projection_guard dominates live non-activation",
            intended_benefit={
                "target_family": "projection",
                "target_metric": "policy_match_rate",
                "secondary_family": "gain_goal_conflict",
                "secondary_metric": "expected_provisional_got_reject",
            },
            mechanism={
                "component": "projection_sensitive_score_probe",
                "old_value": "baseline_selection_mix",
                "new_value": "projection_guard_sensitive_mix_v1",
            },
            memory_dependencies=[
                "diagnostic_memory.override_dormancy_snapshot",
                "diagnostic_memory.live_distribution_gap_snapshot",
                "diagnostic_memory.routing_rule.candidate_distribution_aware_probe",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard"],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "diagnostic ranking probe only",
            "benchmark pack semantics unchanged",
        ]
        record["mechanism"].update(
            {
                "probe_only": True,
                "reweighted_signals": [
                    "pred_projection_bad_prob",
                    "pred_projection_error",
                    "confidence",
                    "gain",
                    "pred_post_gain",
                    "blocker_group",
                    "segment_label",
                ],
                "blocker_sensitive_rules": [
                    "projection_guard => stronger projection_bad and projection_error penalties",
                    "stability_sensitive => extra stability penalty",
                    "gain_structure_shifted => preserve gain/confidence while softening projection penalty slightly",
                ],
                "comparison_reference": "benchmark_undercommit_target_family",
            }
        )
        return record
    if name == "safety_veto_patch.projection_guard_recheck":
        return _base_record(
            proposal_type="safety_veto_patch",
            template_name=name,
            scope="shadow_only",
            trigger_reason="audit whether projection guard thresholding should remain hard-primary after more intervention traffic",
            intended_benefit={
                "target_family": "projection",
                "target_metric": "false_safe_projection_rate",
            },
            mechanism={
                "component": "projection_primary_veto",
                "old_value": "hard_primary",
                "new_value": "hard_primary_recheck",
            },
            memory_dependencies=["diagnostic_memory.override_dormancy_snapshot"],
            targets_blockers=["projection_guard"],
        )
    if name == "critic_split.stability_context_retention_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="audit_only",
            trigger_reason="refine safe-slice retention using stability/context structure discovered in seed-context collapse memory",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "safe_slice_benchmark_retention",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_context_stability",
            },
            mechanism={
                "component": "stability_context_retention_critic",
                "old_value": "benchmark_alignment_context_score_v1",
                "new_value": "stability_context_retention_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_alignment_critic_v1",
                "refined_signal_groups": [
                    "stability_context_interaction",
                    "safe_slice_subtype",
                    "context_conditioned_gain_goal_interaction",
                    "context_conditioned_projection_shape_interaction",
                    "safe_pool_scarcity",
                    "benchmark_distance_context",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "stability_context_conditioned_safe_slice",
                "blocker_sensitive_rules": [
                    "safe-slice admission remains identical to critic-v2",
                    "context-stability refinement happens only inside the already safe slice",
                    "scarcity and subtype-loss precursors are modeled explicitly",
                    "stability-sensitive rows stay penalized unless context evidence supports retention",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.seed_context_shift_snapshot",
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v1",
                "diagnostic_memory.critic_split.projection_gain_goal_v2",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Follow-up probe only; not a routing retry.",
                "Targets stability/context retention after seed-context collapse analysis.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "stability/context retention probe only",
            "benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.stability_context_retention_probe_v2":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="benchmark_only",
            trigger_reason="test whether the scorer-preservation benchmark-like set can survive and be exploited under stability/context pressure without losing the current survivors or widening safety drift",
            intended_benefit={
                "target_family": "recovery",
                "target_metric": "stability_conditioned_benchmark_like_exploitation",
                "secondary_family": "persistence",
                "secondary_metric": "safe_pool_benchmark_like_preservation_under_context",
            },
            mechanism={
                "component": "stability_context_retention_critic",
                "old_value": "benchmark_like_scoring_preservation_score_v2",
                "new_value": "stability_context_retention_score_v2",
                "probe_only": True,
                "comparison_reference": "critic_split.benchmark_like_scoring_preservation_probe_v2",
                "refined_signal_groups": [
                    "current_survivor_preservation",
                    "residual_context_pressure_selection",
                    "stability_sensitive_case_retention",
                    "adverse_context_guardrailed_exploitation",
                    "projection_safe_transfer_selection",
                    "non_benchmark_like_selection_suppression",
                ],
                "ranking_mode": "stability_context_exploitation_after_scorer_preservation",
                "blocker_sensitive_rules": [
                    "the scorer-preservation safe pool remains the outer envelope for this probe",
                    "projection-safe constraints remain unchanged and routing logic is not reintroduced",
                    "currently selected benchmark-like survivors are preserved before any residual context test is attempted",
                    "at most one additional residual benchmark-like row may be exploited when drift guardrails stay unchanged",
                    "non-benchmark-like rows are never promoted as cosmetic gains",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2",
                "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1",
                "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1",
                "diagnostic_memory.critic_split.benchmark_like_transfer_alignment_probe_v1",
                "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1",
                "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1",
                "intervention_analytics",
            ],
            targets_blockers=["recovery_guard", "persistence_guard"],
            notes=[
                "Benchmark-only critic refinement focused on stability/context exploitation after scorer-preservation succeeds.",
                "Compares directly against critic_split.benchmark_like_scoring_preservation_probe_v2 before any routing reconsideration.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "benchmark_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "no routing changes",
            "stability/context exploitation probe only",
            "benchmark pack semantics unchanged",
        ]
        return record
    if name == "critic_split.safe_slice_selection_reliability_probe_v1":
        record = _base_record(
            proposal_type="critic_split",
            template_name=name,
            scope="audit_only",
            trigger_reason="refine selection reliability inside the already safe slice after diagnostic memory shows selector narrowing rather than upstream retention loss",
            intended_benefit={
                "target_family": "gain_goal_conflict",
                "target_metric": "selected_benchmark_like_reliability",
                "secondary_family": "calibration",
                "secondary_metric": "safe_slice_selection_stability",
            },
            mechanism={
                "component": "safe_slice_selection_reliability_critic",
                "old_value": "stability_context_retention_score_v2",
                "new_value": "safe_slice_selection_reliability_score_v1",
                "probe_only": True,
                "comparison_reference": "critic_split.stability_context_retention_probe_v2",
                "refined_signal_groups": [
                    "selection_margin_reliability",
                    "safe_slice_ranking_consistency",
                    "context_conditioned_selection",
                    "subtype_conditioning_inside_safe_slice",
                    "benchmark_like_selection_preservation",
                    "segment_label",
                    "blocker_group",
                ],
                "ranking_mode": "safe_slice_selection_reliability",
                "blocker_sensitive_rules": [
                    "safe-slice admission remains identical to benchmark_alignment_critic_v2",
                    "refinement acts only on ranking and selection inside the already safe slice",
                    "projection-safety framing remains unchanged",
                    "no routing or threshold changes are introduced",
                ],
            },
            memory_dependencies=[
                "diagnostic_memory.critic_split.benchmark_alignment_critic_v2",
                "diagnostic_memory.critic_split.stability_context_retention_probe_v2",
                "diagnostic_memory.safe_slice_selection_gap_snapshot",
                "intervention_analytics",
            ],
            targets_blockers=["projection_guard", "confidence_gain_precondition"],
            notes=[
                "Reserved follow-up after the safe-slice selection-gap diagnostic.",
                "Intended to recover lost benchmark-like selections without broadening routing or safety admission.",
            ],
        )
        record["evaluation_semantics"] = "diagnostic"
        record["evaluation_plan"] = ["static_check", "shadow"]
        record["scope"] = "audit_only"
        record["constraints"] = [
            "no default live-policy mutation",
            "no threshold relaxation",
            "selection-reliability probe only",
            "benchmark pack semantics unchanged",
        ]
        return record
    raise ValueError(f"Unknown intervention template: {name}")


def list_available_proposal_templates() -> list[str]:
    return [
        "routing_rule.targeted_gain_goal_proj_margin_01",
        "score_reweight.gain_goal_conflict_probe",
        "critic_split.projection_gain_goal_v1",
        "critic_split.projection_gain_goal_v2",
        "critic_split.safe_slice_purity_probe_v1",
        "critic_split.benchmark_distance_retention_probe_v1",
        "critic_split.benchmark_alignment_critic_v1",
        "critic_split.benchmark_alignment_critic_v2",
        "critic_split.benchmark_transfer_alignment_probe_v1",
        "support_contract.benchmark_stability_sensitive_compat_probe_v1",
        "support_contract.recovery_runner_contract_fix_v1",
        "critic_split.benchmark_like_transfer_alignment_probe_v1",
        "critic_split.benchmark_like_scoring_preservation_probe_v1",
        "critic_split.benchmark_like_scoring_preservation_probe_v2",
        "critic_split.final_selection_false_safe_guardrail_probe_v1",
        "critic_split.safe_trio_incumbent_confirmation_probe_v1",
        "critic_split.persistence_balanced_safe_trio_probe_v1",
        "critic_split.swap_c_incumbent_hardening_probe_v1",
        "critic_split.recovery_benchmark_like_alignment_probe_v1",
        "critic_split.benchmark_family_balance_probe_v1",
        "memory_summary.override_dormancy_snapshot",
        "memory_summary.live_distribution_gap_snapshot",
        "memory_summary.seed_context_shift_snapshot",
        "memory_summary.benchmark_context_availability_snapshot",
        "memory_summary.safe_slice_selection_gap_snapshot",
        "memory_summary.benchmark_transfer_blocker_snapshot_v1",
        "memory_summary.runner_path_incompatibility_snapshot_v1",
        "memory_summary.recovery_transfer_asymmetry_snapshot_v1",
        "memory_summary.benchmark_family_balance_snapshot_v1",
        "memory_summary.final_selection_false_safe_margin_snapshot_v1",
        "memory_summary.swap_c_family_coverage_snapshot_v1",
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
        "memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
        "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
        "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1",
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
        "memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
        "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
        "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
        "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1",
        "memory_summary.v4_governance_substrate_v1_snapshot",
        "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
        "memory_summary.v4_governance_reopen_screening_snapshot_v1",
        "memory_summary.v4_governance_reopen_review_submission_snapshot_v1",
        "memory_summary.v4_governance_reopen_review_outcome_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1",
        "memory_summary.v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1",
        "memory_summary.v4_governance_reopen_case_registry_snapshot_v1",
        "memory_summary.v4_governance_reopen_case_triage_snapshot_v1",
        "memory_summary.v4_governance_reopen_case_queue_snapshot_v1",
        "memory_summary.v4_governance_portfolio_brief_snapshot_v1",
        "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
        "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1",
        "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
        "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
        "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
        "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
        "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
        "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
        "memory_summary.v4_governed_capability_use_policy_snapshot_v1",
        "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1",
        "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1",
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1",
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1",
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1",
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1",
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6",
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v2",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v3",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v4",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v5",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v6",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v8",
        "memory_summary.v4_governed_work_loop_hold_position_closeout_v1",
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1",
        "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
        "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
        "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
        "routing_rule.activation_window_probe",
        "routing_rule.slice_targeted_benchmark_sweep_v1",
        "routing_rule.candidate_distribution_aware_probe",
        "score_reweight.blocker_sensitive_projection_probe",
        "critic_split.stability_context_retention_probe_v1",
        "critic_split.stability_context_retention_probe_v2",
        "critic_split.safe_slice_selection_reliability_probe_v1",
        "safety_veto_patch.projection_guard_recheck",
    ]


def validate_proposal_structure(proposal: Dict[str, Any]) -> Dict[str, Any]:
    proposal_type = str(proposal.get("proposal_type", ""))
    if proposal_type not in PROPOSAL_TYPE_SPECS:
        return {"passed": False, "reason": f"unknown proposal_type={proposal_type}"}
    required_top = [
        "proposal_id",
        "created_at",
        "branch",
        "proposal_type",
        "scope",
        "trigger_reason",
        "intended_benefit",
        "mechanism",
        "evaluation",
        "promotion_status",
    ]
    missing = [key for key in required_top if key not in proposal]
    if missing:
        return {"passed": False, "reason": f"missing fields: {missing}"}
    mechanism = dict(proposal.get("mechanism", {}))
    if "component" not in mechanism:
        return {"passed": False, "reason": "mechanism.component missing"}
    return {"passed": True, "reason": "proposal structure valid"}
