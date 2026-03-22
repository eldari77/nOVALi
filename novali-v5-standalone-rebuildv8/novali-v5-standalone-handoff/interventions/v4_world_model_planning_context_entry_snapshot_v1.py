from __future__ import annotations

import json
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    BENCHMARK_PACK_ROOT,
    HANDOFF_STATUS_PATH,
    PROPOSAL_LOOP_PATH,
    _benchmark_pack_summary,
    _count_config_prefixes,
    _load_json_file,
    _load_text_file,
    _projected_score,
)
from .v4_proposal_learning_loop_context_branch_snapshot_v1 import _surface_signal_report


def _label_for_score(value: float) -> str:
    if value >= 0.85:
        return "high"
    if value >= 0.55:
        return "medium"
    return "low"


def _entry_row(
    *,
    rank: int,
    design: str,
    owner_surface: str,
    supporting_surface: str,
    scope: str,
    state: str,
    reason: str,
    dependency: list[str],
    value: float,
    risk: float,
    reversibility: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rank": int(rank),
        "candidate_entry_design": str(design),
        "owner_surface": str(owner_surface),
        "supporting_surface": str(supporting_surface),
        "scope": str(scope),
        "state": str(state),
        "reason": str(reason),
        "dependency_on_carried_forward_v3_evidence": list(dependency),
        "projected_value": {"label": _label_for_score(value), "score": float(value)},
        "projected_risk": {"label": _label_for_score(risk), "score": float(risk)},
        "reversibility": {"label": _label_for_score(reversibility), "score": float(reversibility)},
        "projected_priority": _projected_score(str(state), float(value), float(risk), float(reversibility)),
        "design_evidence": dict(evidence),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

    loop_surface_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1"
    )
    architecture_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1"
    )
    landscape_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_first_hypothesis_landscape_snapshot_v1"
    )
    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    invariance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    routing_artifact = r._load_latest_diagnostic_artifact_by_template(
        "routing_rule.slice_targeted_benchmark_sweep_v1"
    )
    if not all(
        [
            loop_surface_artifact,
            architecture_artifact,
            landscape_artifact,
            hardening_artifact,
            frontier_artifact,
            invariance_artifact,
            coverage_artifact,
            routing_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the v4 wm/plan branch-entry snapshot requires the carried-forward v4 architecture, proposal-learning-loop, frontier, hardening, coverage, and routing closure artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot resolve wm/plan ownership and scope boundaries without the carried-forward diagnostic set",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)
    surface_counts = _count_config_prefixes(proposal_loop_text)
    surface_signals = _surface_signal_report(proposal_loop_text, surface_counts)
    benchmark_pack = _benchmark_pack_summary(BENCHMARK_PACK_ROOT)

    loop_conclusions = dict(loop_surface_artifact.get("diagnostic_conclusions", {}))
    architecture_conclusions = dict(architecture_artifact.get("diagnostic_conclusions", {}))
    landscape_conclusions = dict(landscape_artifact.get("diagnostic_conclusions", {}))
    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_artifact.get("diagnostic_conclusions", {}))
    invariance_conclusions = dict(invariance_artifact.get("diagnostic_conclusions", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    routing_conclusions = dict(routing_artifact.get("diagnostic_conclusions", {}))

    carried_forward_baseline = dict(handoff_status.get("carried_forward_baseline", {}))
    recovery_coverage = dict(dict(coverage_artifact.get("family_coverage_report", {})).get("recovery", {}))
    persistence_coverage = dict(dict(coverage_artifact.get("family_coverage_report", {})).get("persistence", {}))
    frontier_report = dict(frontier_artifact.get("frontier_characterization_report", {}))

    hard_discrete_frontier = (
        str(frontier_conclusions.get("frontier_classification", "")) == "hard_discrete_accounting_boundary"
    )
    under_cap_critic_exhausted = not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True))
    no_control_headroom = not bool(frontier_conclusions.get("benchmark_only_control_headroom_exists", True))
    routing_deferred = bool(frontier_conclusions.get("routing_deferred", False))
    world_model_open = bool(loop_conclusions.get("world_model_surface_open", False))
    planning_open = bool(loop_conclusions.get("planning_surface_open", False))
    self_improve_secondary = bool(loop_conclusions.get("self_improvement_surface_open_as_secondary", False))

    wm_signal = dict(surface_signals.get("wm_", {}))
    plan_signal = dict(surface_signals.get("plan_", {}))
    self_improve_signal = dict(surface_signals.get("self_improve_", {}))
    adoption_signal = dict(surface_signals.get("adoption_", {}))
    social_conf_signal = dict(surface_signals.get("social_conf_", {}))

    joint_eval_calls = int(dict(plan_signal.get("marker_counts", {})).get("planning_eval_call", 0) or 0)
    world_model_eval_calls = int(dict(wm_signal.get("marker_counts", {})).get("world_model_eval_call", 0) or 0)
    downstream_selection_markers = int(dict(adoption_signal.get("marker_counts", {})).get("selected_set_adoption", 0) or 0) + int(
        dict(social_conf_signal.get("marker_counts", {})).get("selection_score_usage", 0) or 0
    )

    candidate_rows = [
        _entry_row(
            rank=1,
            design="wm_ primary with plan_ co-owner",
            owner_surface="wm_",
            supporting_surface="plan_",
            scope="context formation plus planning-structure handoff only",
            state="open" if (world_model_open and planning_open) else "closed",
            reason="best first branch because wm_ owns the richest upstream context supply and forecasting machinery, while plan_ is already threaded through the same evaluation calls as a thin structural handoff surface; this opens a real upstream branch without re-entering downstream selected-set governance",
            dependency=[
                "under-cap critic_split work is exhausted",
                "false-safe frontier is hard discrete",
                "benchmark-only control headroom is not evidenced",
                "routing remains deferred",
                "adoption/social-confidence surfaces are closed as first-entry owners",
            ],
            value=0.98,
            risk=0.37,
            reversibility=0.85,
            evidence={
                "wm_prefix_count": int(wm_signal.get("prefix_count", 0) or 0),
                "plan_prefix_count": int(plan_signal.get("prefix_count", 0) or 0),
                "joint_eval_calls": int(joint_eval_calls),
                "world_model_eval_calls": int(world_model_eval_calls),
            },
        ),
        _entry_row(
            rank=2,
            design="pure wm_ context-supply entry",
            owner_surface="wm_",
            supporting_surface="none",
            scope="context formation only",
            state="open_secondary" if world_model_open else "closed",
            reason="open but second-best because it respects the upstream move, yet it ignores that planning is already co-passed with wm_ in the main evaluation path and risks creating a later branch-contract mismatch between supplied context and structure consumer",
            dependency=[
                "v3 closed downstream selected-set and control lines",
                "proposal_learning_loop keeps use_world_model enabled with active shadow rollout and candidate projection",
                "the best v4 entry must move above final selection rather than around it",
            ],
            value=0.88,
            risk=0.41,
            reversibility=0.83,
            evidence={
                "wm_prefix_count": int(wm_signal.get("prefix_count", 0) or 0),
                "shadow_rollout_markers": int(dict(wm_signal.get("marker_counts", {})).get("shadow_rollout", 0) or 0),
                "candidate_projection_markers": int(dict(wm_signal.get("marker_counts", {})).get("candidate_projection", 0) or 0),
            },
        ),
        _entry_row(
            rank=3,
            design="balanced wm_ + plan_ co-equal entry",
            owner_surface="wm_ + plan_",
            supporting_surface="co-equal",
            scope="context formation plus planning structure as equal owners",
            state="open_secondary" if (world_model_open and planning_open) else "closed",
            reason="open but weaker because it captures the real pair, yet it overstates the much thinner plan_ surface and risks turning the first v4 branch into a search/planning redesign instead of an upstream context-formation branch",
            dependency=[
                "planning is active but thin relative to wm_",
                "v3 exhaustion means the first v4 move must avoid renamed local-optimization work",
            ],
            value=0.79,
            risk=0.52,
            reversibility=0.78,
            evidence={
                "joint_eval_calls": int(joint_eval_calls),
                "plan_prefix_count": int(plan_signal.get("prefix_count", 0) or 0),
                "wm_prefix_count": int(wm_signal.get("prefix_count", 0) or 0),
            },
        ),
        _entry_row(
            rank=4,
            design="plan_ primary with wm_ support",
            owner_surface="plan_",
            supporting_surface="wm_",
            scope="planning-first structure branch",
            state="closed",
            reason="closed as a first entry because planning alone is too thin and too likely to become renamed local search or downstream pressure reshaping under the same exhausted false-safe frontier",
            dependency=[
                "v3 failures were not caused by missing downstream ranking pressure",
                "wm_ carries the actual upstream context-supply surface richness",
            ],
            value=0.29,
            risk=0.63,
            reversibility=0.87,
            evidence={
                "plan_prefix_count": int(plan_signal.get("prefix_count", 0) or 0),
                "planning_eval_calls": int(dict(plan_signal.get("marker_counts", {})).get("planning_eval_call", 0) or 0),
            },
        ),
        _entry_row(
            rank=5,
            design="wm_/plan_ entry with self_improve_ attached from day one",
            owner_surface="wm_",
            supporting_surface="plan_ + self_improve_",
            scope="context formation plus immediate self-adaptation support",
            state="closed",
            reason="closed as the first implementation because attaching self_improve_ immediately would blur upstream context supply with within-agent patch dynamics and recreate v3-style adaptation pressure before the new branch contract is isolated",
            dependency=[
                "self_improve_ is open only as a secondary support surface",
                "swap_C hardening found no productive under-cap critic work left",
            ],
            value=0.35,
            risk=0.66,
            reversibility=0.76,
            evidence={
                "self_improve_prefix_count": int(self_improve_signal.get("prefix_count", 0) or 0),
                "self_improve_toggle_enabled": bool(self_improve_signal.get("toggle_enabled", False)),
            },
        ),
        _entry_row(
            rank=6,
            design="adoption_ first-entry owner",
            owner_surface="adoption_",
            supporting_surface="wm_ or plan_ renamed as support",
            scope="selected-set acceptance / patch scaling branch",
            state="closed",
            reason="closed because adoption_ is downstream acceptance, scaling, cooldown, and patch application logic; used naively, it would simply recreate exhausted v3 final-selection and frontier work under a new owner label",
            dependency=[
                "swap_C is already the best safe trio under the flat frontier",
                "no productive under-cap hardening remains",
                "persistence exclusion is downstream under the fixed cap rather than upstream scarcity",
            ],
            value=0.18,
            risk=0.71,
            reversibility=0.82,
            evidence={
                "adoption_prefix_count": int(adoption_signal.get("prefix_count", 0) or 0),
                "selected_set_adoption_markers": int(dict(adoption_signal.get("marker_counts", {})).get("selected_set_adoption", 0) or 0),
            },
        ),
        _entry_row(
            rank=7,
            design="social_conf_ first-entry owner",
            owner_surface="social_conf_",
            supporting_surface="wm_ or plan_ renamed as support",
            scope="coordination / provisional gating / selection-score branch",
            state="closed",
            reason="closed because social_conf_ is downstream coordination, provisional evidence decay, and selection-score gating; using it as the first branch owner would reopen the same downstream composition/tie-break problems already flattened by the v3 frontier diagnosis",
            dependency=[
                "safe-trio invariance showed composition changes utility but not false-safe occupancy",
                "swap_C family coverage showed persistence is excluded only at final selection",
            ],
            value=0.17,
            risk=0.69,
            reversibility=0.82,
            evidence={
                "social_conf_prefix_count": int(social_conf_signal.get("prefix_count", 0) or 0),
                "selection_score_usage_markers": int(dict(social_conf_signal.get("marker_counts", {})).get("selection_score_usage", 0) or 0),
            },
        ),
    ]

    best_hypothesis = "wm_ primary with plan_ as structure co-owner, scoped to upstream context formation plus planning handoff only"
    recommended_next_family = "proposal_learning_loop"
    recommended_next_template = "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1"
    recommended_next_rationale = (
        "the first real v4 implementation should be a wm_-owned context-supply probe that uses plan_ only as the structure co-owner at existing evaluation handoff points, because that is the narrowest architecture move above the exhausted v3 downstream frontier"
    )

    branch_scope_report = {
        "recommended_in_scope": [
            "world-model context supply, candidate projection, uncertainty/context weighting, and shadow rollout observability",
            "planning structure only where it is already passed alongside evaluation and can consume wm_-supplied context",
            "benchmark-only architecture traces that expose family/seed/context differences before downstream selection",
        ],
        "must_stay_out_of_scope": [
            "adoption thresholds, patch scaling, cooldown, and selected-set acceptance",
            "social-confidence gating, provisional decay, and selection-score tie-break logic",
            "final selected-set composition, false-safe frontier handling, and trio balancing",
            "routing/control retests and any threshold relaxation",
            "self-improvement as a first-entry owner or same-step adaptation mechanism",
        ],
        "downstream_marker_pressure": {
            "downstream_selection_markers": int(downstream_selection_markers),
            "adoption_selected_set_markers": int(dict(adoption_signal.get("marker_counts", {})).get("selected_set_adoption", 0) or 0),
            "social_conf_selection_score_markers": int(dict(social_conf_signal.get("marker_counts", {})).get("selection_score_usage", 0) or 0),
        },
    }

    success_criteria_shape = {
        "primary_success_criteria": [
            "wm_-supplied context becomes explicitly observable at the existing benchmark/runtime evaluation handoff points",
            "plan_ consumes or structures that context without changing downstream adoption/social-confidence ownership",
            "the branch produces upstream context/forecast traces that vary meaningfully by family or seed/context before final selection",
            "the carried-forward swap_C safety baseline remains unchanged because downstream selection is not the success target for the first v4 branch",
        ],
        "non_goals": [
            "no requirement to increase selected_benchmark_like_count above the carried-forward baseline",
            "no requirement to alter false-safe frontier occupancy or selected-set size",
            "no routing/control activation and no benchmark-only control retest",
        ],
        "why_not_downstream_selected_set_gains": "novali-v3 already exhausted under-cap critic refinement and characterized the false-safe frontier as a hard discrete accounting boundary, so the first v4 branch should be judged by upstream context-formation observability and branch separation instead of downstream selected-set gains",
    }

    latest_snapshot_refs = {}
    for artifact in [
        loop_surface_artifact,
        architecture_artifact,
        landscape_artifact,
        hardening_artifact,
        frontier_artifact,
        invariance_artifact,
        coverage_artifact,
        routing_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        latest_snapshot_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_world_model_planning_context_entry_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": carried_forward_baseline,
        },
        "proposal_learning_loop_branch_entry_report": {
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "surface_counts": surface_counts,
            "surface_signal_report": surface_signals,
            "benchmark_pack_summary": benchmark_pack,
            "joint_eval_call_count": int(joint_eval_calls),
            "world_model_eval_call_count": int(world_model_eval_calls),
        },
        "comparison_references": {
            "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1": {
                "decision_recommendation": dict(loop_surface_artifact.get("decision_recommendation", {})),
                "diagnostic_conclusions": loop_conclusions,
            },
            "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1": {
                "decision_recommendation": dict(architecture_artifact.get("decision_recommendation", {})),
                "diagnostic_conclusions": architecture_conclusions,
            },
            "memory_summary.v4_first_hypothesis_landscape_snapshot_v1": {
                "decision_recommendation": dict(landscape_artifact.get("decision_recommendation", {})),
                "diagnostic_conclusions": landscape_conclusions,
            },
            "critic_split.swap_c_incumbent_hardening_probe_v1": {
                "diagnostic_conclusions": hardening_conclusions,
                "incumbent_robustness_report": dict(hardening_artifact.get("incumbent_robustness_report", {})),
            },
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": {
                "diagnostic_conclusions": frontier_conclusions,
                "frontier_characterization_report": frontier_report,
            },
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1": {
                "diagnostic_conclusions": invariance_conclusions,
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "diagnostic_conclusions": coverage_conclusions,
                "family_coverage_report": dict(coverage_artifact.get("family_coverage_report", {})),
            },
            "routing_rule.slice_targeted_benchmark_sweep_v1": {
                "diagnostic_conclusions": routing_conclusions,
                "benchmark_control_metrics": dict(routing_artifact.get("benchmark_control_metrics", {})),
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "legacy_recommender_bias_detected": bool(
                "critic_split" in " ".join(
                    str(item.get("template_name", ""))
                    for item in list(recommendations.get("all_ranked_proposals", []))[:8]
                    if isinstance(item, dict)
                )
            ),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
        },
        "ranked_branch_entry_designs": candidate_rows,
        "branch_scope_report": branch_scope_report,
        "surface_separation_report": {
            "world_model_context_formation": "upstream forecasting, candidate projection, uncertainty/context weighting, and shadow rollout support",
            "planning_structure": "evaluation-time trajectory/action-search shaping that should only co-own the first branch as a handoff structure",
            "self_improvement_structure": "within-agent patch generation and self-adaptation layer, reserved for later support if needed",
            "adoption_logic": "downstream selected-set acceptance, scaling, cooldown, and rollback-sensitive patch application",
            "social_confidence_coordination_logic": "downstream coordination, provisional evidence decay, and selection-score gating",
        },
        "success_criteria_shape": success_criteria_shape,
        "decision_recommendation": {
            "entry_ownership": "wm_ primary, plan_ co-owner",
            "branch_scope": "context formation plus planning-structure handoff only",
            "excluded_surfaces": ["adoption_", "social_conf_"],
            "best_first_implementation_hypothesis": str(best_hypothesis),
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommended_next_rationale),
        },
        "branch_snapshot_refs": latest_snapshot_refs,
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot resolves wm/plan ownership, scope boundaries, and first-implementation success criteria using actual proposal-learning-loop call-site evidence plus carried-forward v3 closure evidence",
            "candidate_entry_design_count": int(len(candidate_rows)),
            "joint_wm_plan_entry_still_open": bool(world_model_open and planning_open),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot distinguishes the first real wm/plan architecture opening from closed downstream ownership options that would only rename exhausted v3 work",
            "under_cap_critic_exhausted": bool(under_cap_critic_exhausted),
            "hard_discrete_frontier": bool(hard_discrete_frontier),
            "benchmark_control_headroom_exists": bool(not no_control_headroom),
            "routing_deferred": bool(routing_deferred),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.48
                    + 0.14 * int(world_model_open)
                    + 0.10 * int(planning_open)
                    + 0.08 * int(self_improve_secondary)
                    + 0.10 * int(under_cap_critic_exhausted)
                    + 0.10 * int(hard_discrete_frontier)
                )
            ),
            "reason": "the snapshot cleanly resolves entry ownership, scope, exclusions, and next-template shape instead of only ranking proposal-learning-loop surfaces",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only wm/plan branch-entry snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommended_next_rationale),
        },
        "diagnostic_conclusions": {
            "best_first_implementation_hypothesis": str(best_hypothesis),
            "entry_ownership": "wm_ primary, plan_ co-owner",
            "branch_scope": "context formation plus planning-structure handoff only",
            "pure_wm_open_as_secondary": bool(world_model_open),
            "balanced_wm_plan_open_as_secondary": bool(world_model_open and planning_open),
            "self_improve_first_move_open": False,
            "adoption_first_move_open": False,
            "social_conf_first_move_open": False,
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "routing_deferred": bool(routing_deferred),
            "persistence_upstream_health": str(persistence_coverage.get("absence_stage", "")),
            "recovery_selected_presence": str(recovery_coverage.get("absence_stage", "")),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_world_model_planning_context_entry_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: wm/plan ownership and first-implementation branch-entry scope were resolved for novali-v4",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
